from __future__ import annotations

from app.services.runtime_config_apply import classify_runtime_config_changes


def test_classify_runtime_config_changes_groups_hot_apply_paths() -> None:
    changes = classify_runtime_config_changes(
        {
            "cameras.0.source",
            "plc.host",
            "line_signal.port",
            "alert.ng_popup_timeout_seconds",
            "app.line_id",
            "app.trigger_poll_interval_s",
            "offline_platform.hot_reload_enabled",
            "app.inspection_mode",
            "storage.log_dir",
        }
    )

    assert "cameras.0.source" in changes.cameras
    assert "plc.host" in changes.plc
    assert "line_signal.port" in changes.plc
    assert "alert.ng_popup_timeout_seconds" in changes.alert
    assert "app.line_id" in changes.ui
    assert "app.trigger_poll_interval_s" in changes.trigger
    assert "offline_platform.hot_reload_enabled" in changes.hot_reload
    assert "app.inspection_mode" in changes.restart_required
    assert "storage.log_dir" in changes.ignored
