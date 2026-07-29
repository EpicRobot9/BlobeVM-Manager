import importlib.util
import json
import sys


APP_PATH = "/opt/blobe-vm/repo/dashboard/app.py"


def load_app(monkeypatch):
    monkeypatch.setenv("BLOBEDASH_STATE", "/tmp/blobevm-test-state")
    monkeypatch.setenv("DASH_V2_SECRET", "test-secret")
    spec = importlib.util.spec_from_file_location("blobedash_test_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_admin_vm_sso_is_enabled_by_default(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))

    assert module._admin_vm_sso_enabled() is True


def test_admin_vm_sso_setting_can_be_disabled(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    (tmp_path / "dashboard_settings.json").write_text(
        json.dumps({"admin_vm_sso": False}), encoding="utf-8"
    )

    assert module._admin_vm_sso_enabled() is False


def test_forward_auth_accepts_dashboard_admin_session_when_enabled(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    monkeypatch.setattr(module, "_current_portal_user", lambda: None)
    monkeypatch.setattr(module, "_verify_v2_token", lambda token: {"admin": True} if token else None)
    monkeypatch.setattr(module, "_vm_access_mode", lambda name: "restricted")

    client = module.app.test_client()
    client.set_cookie("Dashboard-Auth", "valid-admin-session")
    response = client.get("/dashboard/auth/vm/alpha")

    assert response.status_code == 200


def test_forward_auth_does_not_use_dashboard_admin_session_when_disabled(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    (tmp_path / "dashboard_settings.json").write_text(
        json.dumps({"admin_vm_sso": False}), encoding="utf-8"
    )
    monkeypatch.setattr(module, "_current_portal_user", lambda: None)
    monkeypatch.setattr(module, "_verify_v2_token", lambda token: {"admin": True} if token else None)
    monkeypatch.setattr(module, "_vm_access_mode", lambda name: "restricted")

    response = module.app.test_client().get(
        "/dashboard/auth/vm/alpha",
        headers={"Cookie": "Dashboard-Auth=valid-admin-session"},
    )

    assert response.status_code == 302
    assert "/portal/login" in response.headers["Location"]


def test_settings_endpoint_persists_admin_vm_sso_toggle(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    monkeypatch.setattr(module, "_admin_credentials", lambda: ("Epic", "test-password"))
    monkeypatch.setattr(module, "_dashboard_secret", lambda: "test-secret")
    monkeypatch.setattr(module, "_verify_v2_token", lambda token: bool(token))

    client = module.app.test_client()
    client.set_cookie("Dashboard-Auth", "valid-admin-session")
    response = client.post(
        "/dashboard/api/settings",
        json={"adminVmSso": False},
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 200
    assert module._admin_vm_sso_enabled() is False


def test_vm_wrapper_accepts_dashboard_admin_session_when_enabled(monkeypatch, tmp_path):
    module = load_app(monkeypatch)
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    monkeypatch.setattr(module, "_current_portal_user", lambda: None)
    monkeypatch.setattr(module, "_verify_v2_token", lambda token: bool(token))
    monkeypatch.setattr(module, "_vm_access_mode", lambda name: "restricted")

    with module.app.test_request_context(
        "/vm/alpha/", headers={"Cookie": "Dashboard-Auth=valid-admin-session"}
    ):
        assert module._enforce_vm_user_access("alpha") is None
