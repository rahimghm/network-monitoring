import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app import auth
from app.main import app


ALL_ACTIONS = {
    "health.read",
    "config.read",
    "auth.me",
    "auth.change_password",
    "auth.logout",
    "equipment.read",
    "equipment.manage",
    "diagnostic.run",
    "monitoring.control",
    "monitoring.snapshot.create",
    "monitoring.snapshot.manage",
    "monitoring.snapshot.delete",
    "monitoring.receive",
    "history.read",
    "history.export",
    "threshold.read",
    "threshold.manage",
    "users.manage",
    "audit.read",
}

ROLE_EXPECTATIONS = {
    "admin": ALL_ACTIONS,
    "technician": {
        "health.read", "config.read", "auth.me", "auth.change_password", "auth.logout",
        "equipment.read", "monitoring.control", "monitoring.snapshot.create",
        "monitoring.receive", "history.read",
        "history.export", "threshold.read",
    },
    "supervisor": {
        "health.read", "config.read", "auth.me", "auth.change_password", "auth.logout",
        "equipment.read", "equipment.manage", "diagnostic.run", "monitoring.control",
        "monitoring.snapshot.create", "monitoring.snapshot.manage",
        "monitoring.snapshot.delete", "monitoring.receive", "history.read",
        "history.export", "threshold.read", "threshold.manage",
    },
}


@pytest.mark.parametrize("role", auth.ROLES)
@pytest.mark.parametrize("action", sorted(ALL_ACTIONS))
def test_each_role_action_bucket(role, action):
    guard = auth.require_action(action)
    user = {"id": 1, "username": role, "role": role}
    expected = action in ROLE_EXPECTATIONS[role]

    if expected:
        assert guard(user=user) == user
    else:
        with pytest.raises(HTTPException) as error:
            guard(user=user)
        assert error.value.status_code == 403
        assert role in error.value.detail
        assert action in error.value.detail


PROTECTED_HTTP_ROUTES = [
    ("GET", "/health"),
    ("GET", "/config"),
    ("GET", "/auth/me"),
    ("PATCH", "/auth/password"),
    ("POST", "/auth/logout"),
    ("GET", "/users"),
    ("POST", "/users"),
    ("PATCH", "/users/1"),
    ("DELETE", "/users/1"),
    ("GET", "/audit-logs"),
    ("GET", "/equipments"),
    ("POST", "/equipments"),
    ("PATCH", "/equipments/1"),
    ("DELETE", "/equipments/1"),
    ("POST", "/equipments/1/diagnose"),
    ("GET", "/equipments/1/diagnostics"),
    ("GET", "/equipments/1/metrics/timeseries"),
    ("GET", "/thresholds"),
    ("POST", "/thresholds"),
    ("DELETE", "/thresholds/1"),
    ("GET", "/snapshots"),
    ("GET", "/snapshots/1"),
    ("PATCH", "/snapshots/1"),
    ("DELETE", "/snapshots/1"),
    ("GET", "/snapshots/1/export/pdf"),
    ("GET", "/snapshots/1/export/xlsx"),
]


@pytest.mark.parametrize("method,path", PROTECTED_HTTP_ROUTES)
def test_every_protected_http_route_rejects_unauthenticated(method, path):
    with TestClient(app) as client:
        response = client.request(method, path)
    assert response.status_code == 401


def test_public_bootstrap_exceptions_remain_available_without_token():
    assert app.openapi_url is None
    assert app.docs_url is None
    assert app.redoc_url is None
    assert "/auth/login" in {route.path for route in app.routes}
    assert "/auth/register" in {route.path for route in app.routes}


def test_unauthenticated_websocket_is_rejected():
    with TestClient(app) as client:
        with pytest.raises(Exception) as error:
            with client.websocket_connect("/ws/diagnose?token=invalid"):
                pass
    assert getattr(error.value, "code", None) == 4401
