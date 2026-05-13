from fastapi.testclient import TestClient

from api.app import create_app


def test_public_site_serves_html_for_browsers():
    app = create_app(lifespan_enabled=False)
    client = TestClient(app)

    response = client.get("/", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Free Claude Code Anywhere" in response.text
    assert "/assets/site.css" in response.text
    assert "/assets/site.js" in response.text


def test_public_site_assets_are_served():
    app = create_app(lifespan_enabled=False)
    client = TestClient(app)

    css = client.get("/assets/site.css")
    js = client.get("/assets/site.js")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
