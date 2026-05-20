import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.middleware import AuditMiddleware, AuthMiddleware, get_audit_actor
from src.api.server import create_app


def build_app():
    app = FastAPI()
    app.state.protected_calls = 0
    app.add_middleware(AuditMiddleware)
    app.add_middleware(AuthMiddleware)

    @app.get("/api/v2/probe")
    async def protected_probe(request: Request):
        app.state.protected_calls += 1
        return {
            "actor": get_audit_actor(),
            "state_actor": getattr(request.state, "audit_actor", None),
        }

    @app.get("/api/v2/crash")
    async def protected_crash():
        raise RuntimeError("downstream failure")

    @app.get("/public/probe")
    async def public_probe(request: Request):
        return {
            "actor": get_audit_actor(),
            "state_actor": getattr(request.state, "audit_actor", None),
        }

    return app


def test_attaches_audit_actor_after_successful_auth_only():
    app = build_app()
    client = TestClient(app)

    response = client.get(
        "/api/v2/probe",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Actor-ID": "user-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"actor": "user-123", "state_actor": "user-123"}
    assert response.headers["X-Audit-Decision"] == "accepted"
    assert response.headers["X-Audit-Actor"] == "attached"
    assert "secret-token" not in str(response.headers)

    follow_up = client.get("/public/probe")
    assert follow_up.status_code == 200
    assert follow_up.json() == {"actor": None, "state_actor": None}


def test_rejects_before_handler_without_audit_actor():
    app = build_app()
    client = TestClient(app)

    response = client.get("/api/v2/probe")

    assert response.status_code == 401
    assert response.text == "Unauthorized"
    assert response.headers["X-Audit-Decision"] == "rejected"
    assert "X-Audit-Actor" not in response.headers
    assert app.state.protected_calls == 0
    assert get_audit_actor() is None


def test_audit_middleware_fails_closed_without_auth_state():
    app = FastAPI()
    app.state.protected_calls = 0
    app.add_middleware(AuditMiddleware)

    @app.get("/api/v2/probe")
    async def protected_probe():
        app.state.protected_calls += 1
        return {"actor": get_audit_actor()}

    client = TestClient(app)
    response = client.get(
        "/api/v2/probe",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 401
    assert response.headers["X-Audit-Decision"] == "rejected"
    assert app.state.protected_calls == 0
    assert get_audit_actor() is None


def test_clears_audit_actor_after_downstream_exception(caplog):
    client = TestClient(build_app(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="src.api.middleware"):
        response = client.get(
            "/api/v2/crash",
            headers={"Authorization": "Bearer secret-token"},
        )

    assert response.status_code == 500
    assert get_audit_actor() is None
    assert "audit middleware failed for GET /api/v2/crash" in caplog.text
    assert "secret-token" not in caplog.text


def test_create_app_runs_auth_before_audit():
    client = TestClient(create_app())

    response = client.get(
        "/api/v2/agents",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Actor-ID": "api-user",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Audit-Decision"] == "accepted"
    assert response.headers["X-Audit-Actor"] == "attached"
    assert "secret-token" not in str(response.headers)
