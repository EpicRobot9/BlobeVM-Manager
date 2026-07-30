from pathlib import Path


REPO = Path(__file__).parents[1]
APP = (REPO / "dashboard/app.py").read_text()
TOPBAR = (REPO / "dashboard_v2/src/components/Topbar.jsx").read_text()


def test_dashboard_exposes_authenticated_notification_aggregation():
    assert "def api_notifications" in APP
    assert "@auth_required" in APP[APP.index("def api_notifications") - 200 : APP.index("def api_notifications")]
    assert "get_vm_notifications" in APP[APP.index("def api_notifications") : APP.index("def api_notifications") + 900]


def test_topbar_uses_live_notification_count_and_empty_state():
    assert "<b>3</b>" not in TOPBAR
    assert "notifications.length" in TOPBAR
    assert "No new notifications" in TOPBAR
