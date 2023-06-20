import os
from page_analyzer import app


def test_index():
    os.environ['CONFIG_TYPE'] = 'config.TestingConfig'
    with app.test_client() as client:
        response = client.get("/")
        assert '<h1 class="display-3">Анализатор страниц</h1>' in response.text
