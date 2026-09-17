from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.shared.frontend_static import FrontendStaticFiles


def test_frontend_routes_preserve_api_health_and_asset_errors(tmp_path):
    (tmp_path / "index.html").write_text("<html>Java APEX</html>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('ready');", encoding="utf-8")
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.mount("/", FrontendStaticFiles(directory=tmp_path, html=True))
    client = TestClient(app)
    headers = {"Accept": "text/html"}
    assert client.get("/health", headers=headers).json() == {"status": "ok"}
    for route in ("/", "/signin", "/report", "/discovery/"):
        response = client.get(route, headers=headers)
        assert response.status_code == 200
        assert "Java APEX" in response.text
    for route in ("/api/missing", "/api/v1/missing", "/assets/missing", "/missing.js"):
        response = client.get(route, headers=headers)
        assert response.status_code == 404, (route, response.status_code, response.text)
    assert client.get("/app.js").status_code == 200
    assert client.get("/missing", headers={"Accept": "application/json"}).status_code == 404
    assert client.post("/signin", headers=headers).status_code == 405
    assert client.head("/signin", headers=headers).status_code == 200
