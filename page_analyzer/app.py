from flask import Flask, render_template, request, flash, redirect, url_for, g
from flask import get_flashed_messages
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2.extras import DictCursor
import validators
from datetime import datetime
from psycopg2.errors import UniqueViolation
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')


@app.before_request
def before_request():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    g.conn = conn


@app.route('/')
def index():
    messages = get_flashed_messages(with_categories=True)
    return render_template("index.html", messages=messages)


@app.get('/urls')
def get_urls():
    messages = get_flashed_messages(with_categories=True)
    with g.conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute(('SELECT urls.id, name, '
                        '(select created_at AS last_check FROM url_checks'
                        ' WHERE url_id=urls.id ORDER BY created_at '
                        'DESC LIMIT 1),'
                        '(SELECT status_code FROM url_checks'
                        ' WHERE url_id=urls.id ORDER BY created_at '
                        'DESC LIMIT 1)'
                        ' FROM urls '
                        'ORDER BY created_at DESC;'))
        urls = cursor.fetchall()
        return render_template("urls/index.html", urls=urls, messages=messages)


@app.get('/urls/<id>/')
def get_url(id):
    messages = get_flashed_messages(with_categories=True)
    with g.conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute('SELECT * FROM urls WHERE id=%s', (id))
        url = cursor.fetchone()
        cursor.execute(('SELECT * FROM url_checks '
                        'WHERE url_id=%s ORDER BY created_at DESC'), (id))
        checks = cursor.fetchall()
        return render_template("urls/show.html",
                               url=url,
                               checks=checks,
                               messages=messages)


@app.post('/urls')
def add_url():
    data = request.form.to_dict()
    if not validators.url(data['url']):
        flash('Некорректный URL', 'danger')
        messages = get_flashed_messages(with_categories=True)
        return render_template("index.html", messages=messages), 422
    if len(data['url']) > 255:
        flash('URL превышает 255 символов', 'danger')
        messages = get_flashed_messages(with_categories=True)
        return render_template("index.html", messages=messages), 422
    url_data = urlparse(data['url'])
    url = f"{url_data.scheme}://{url_data.netloc}"
    with g.conn.cursor() as cursor:
        try:
            cursor.execute(("INSERT INTO urls (name, created_at)"
                            " VALUES (%s, %s) RETURNING id"),
                           (url, datetime.now()))
            flash('Страница успешно добавлена', 'success')
        except UniqueViolation:
            flash('Страница уже существует', 'info')
            cursor.execute('SELECT id FROM urls WHERE name=%s', (url,))
        id = cursor.fetchone()
        g.conn.commit()
    return redirect(url_for('get_url', id=id[0]))


@app.post('/urls/<id>/checks')
def check_url(id):
    with g.conn.cursor(cursor_factory=DictCursor) as cursor:
        cursor.execute("SELECT name FROM urls WHERE id =%s", (id))
        url = cursor.fetchone()["name"]
        try:
            r = requests.get(url)
            r.raise_for_status()
            r_soup = BeautifulSoup(r.text, 'html.parser')
            h1 = r_soup.h1.string if r_soup.h1 else ""
            title = r_soup.title.string if r_soup.title else ""
            meta_desc = r_soup.find("meta", {"name": "description"})
            description = meta_desc["content"] if meta_desc else ""
            cursor.execute(("INSERT INTO url_checks "
                            "(url_id, status_code, h1, title, description, created_at)"
                            " VALUES (%s, %s, %s, %s, %s, %s)"),
                           (id, r.status_code, h1, title, description, datetime.now()))
        except Exception:
            flash('Произошла ошибка при проверке', 'danger')
        return redirect(url_for('get_url', id=id))


@app.after_request
def after_request(response):
    if g.conn is not None:
        g.conn.close()
    return response
