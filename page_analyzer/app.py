from flask import Flask, render_template


def create_app():
    app = Flask(__name__)
    return create_app


app = create_app()


@app.route('/')
def hello_world():
    return render_template("index.html")
