from unittest.mock import Mock

import pytest

from browser import launcher


def test_read_devtools_active_port_returns_port_and_browser_path(tmp_path):
    (tmp_path / "DevToolsActivePort").write_text(
        "9333\n/devtools/browser/dedicated-id\n", encoding="utf-8"
    )

    assert launcher.read_devtools_active_port(tmp_path) == (
        9333,
        "/devtools/browser/dedicated-id",
    )


def test_dedicated_cdp_status_matches_profile_marker(monkeypatch, tmp_path):
    (tmp_path / "DevToolsActivePort").write_text(
        "9222\n/devtools/browser/dedicated-id\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        launcher,
        "get_cdp_websocket_url",
        lambda port, timeout_sec=2.0: (
            "ws://127.0.0.1:9222/devtools/browser/dedicated-id"
        ),
    )

    assert launcher.get_dedicated_cdp_status(tmp_path, 9222) == "ready"


def test_dedicated_cdp_status_rejects_other_browser_on_same_port(monkeypatch, tmp_path):
    (tmp_path / "DevToolsActivePort").write_text(
        "9222\n/devtools/browser/dedicated-id\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        launcher,
        "get_cdp_websocket_url",
        lambda port, timeout_sec=2.0: "ws://127.0.0.1:9222/devtools/browser/other-id",
    )

    assert launcher.get_dedicated_cdp_status(tmp_path, 9222) == "mismatch"


def test_ensure_chrome_removes_stale_marker_before_launch(monkeypatch, tmp_path):
    marker = tmp_path / "DevToolsActivePort"
    marker.write_text("9222\n/devtools/browser/stale\n", encoding="utf-8")
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    statuses = iter(["unavailable", "ready"])
    monkeypatch.setattr(
        launcher, "get_dedicated_cdp_status", lambda *args, **kwargs: next(statuses)
    )
    monkeypatch.setattr(launcher, "launch_chrome", launch)

    assert launcher.ensure_chrome(user_data_dir=tmp_path) is True
    assert not marker.exists()
    launch.assert_called_once()


def test_ensure_chrome_fails_without_launch_when_endpoint_is_not_dedicated(
    monkeypatch, tmp_path
):
    launch = Mock()
    monkeypatch.setattr(
        launcher, "get_dedicated_cdp_status", lambda *args, **kwargs: "mismatch"
    )
    monkeypatch.setattr(launcher, "launch_chrome", launch)

    with pytest.raises(ConnectionError, match="does not match dedicated profile"):
        launcher.ensure_chrome(user_data_dir=tmp_path)

    launch.assert_not_called()


def test_ensure_chrome_records_endpoint_for_browser_it_launched(monkeypatch, tmp_path):
    process = Mock()
    process.poll.return_value = None
    websocket_urls = iter(
        [
            None,
            "ws://127.0.0.1:9222/devtools/browser/launched-id",
            "ws://127.0.0.1:9222/devtools/browser/launched-id",
        ]
    )
    monkeypatch.setattr(
        launcher,
        "get_cdp_websocket_url",
        lambda port, timeout_sec=2.0: next(websocket_urls),
    )
    monkeypatch.setattr(launcher, "launch_chrome", Mock(return_value=process))

    assert launcher.ensure_chrome(user_data_dir=tmp_path) is True
    assert (tmp_path / "SessionBridgeActivePort").read_text(encoding="utf-8") == (
        "9222\n/devtools/browser/launched-id\n"
    )


def test_launch_chrome_restricts_remote_debugging_to_loopback(monkeypatch, tmp_path):
    popen = Mock()
    monkeypatch.setattr(launcher, "find_chrome_executable", lambda: "chrome.exe")
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)

    launcher.launch_chrome(user_data_dir=tmp_path)

    args = popen.call_args.args[0]
    assert "--remote-debugging-address=127.0.0.1" in args
    assert f"--user-data-dir={tmp_path}" in args


def test_ensure_chrome_raises_connection_error_after_timeout(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr(
        launcher, "get_dedicated_cdp_status", lambda *args, **kwargs: "unavailable"
    )
    monkeypatch.setattr(launcher, "launch_chrome", launch)
    monkeypatch.setattr(
        launcher.time, "monotonic", Mock(side_effect=[0.0, 0.0, 0.0, 1.0])
    )
    monkeypatch.setattr(launcher.time, "sleep", Mock())

    with pytest.raises(ConnectionError, match="9222"):
        launcher.ensure_chrome(timeout_sec=0.1)

    launch.assert_called_once()


def test_ensure_chrome_reports_early_process_exit(monkeypatch):
    process = Mock()
    process.poll.return_value = 7
    monkeypatch.setattr(
        launcher, "get_dedicated_cdp_status", lambda *args, **kwargs: "unavailable"
    )
    monkeypatch.setattr(launcher, "launch_chrome", Mock(return_value=process))

    with pytest.raises(ConnectionError, match="return code 7"):
        launcher.ensure_chrome(timeout_sec=1.0)


def test_ensure_chrome_limits_probe_timeout_to_remaining_deadline(monkeypatch):
    probe_timeouts = []
    process = Mock()
    process.poll.return_value = None
    clock = iter([10.0, 10.0, 10.25, 10.25, 11.0])

    def not_ready(_profile, port, timeout_sec):
        probe_timeouts.append(timeout_sec)
        return "unavailable"

    monkeypatch.setattr(launcher, "get_dedicated_cdp_status", not_ready)
    monkeypatch.setattr(launcher, "launch_chrome", Mock(return_value=process))
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(launcher.time, "sleep", Mock())

    with pytest.raises(ConnectionError, match="within 1.0s"):
        launcher.ensure_chrome(timeout_sec=1.0)

    assert probe_timeouts == [1.0, 0.75]


def test_ensure_chrome_does_not_launch_after_initial_probe_exhausts_deadline(
    monkeypatch,
):
    launch = Mock()
    clock = iter([10.0, 10.0, 11.0])
    monkeypatch.setattr(
        launcher, "get_dedicated_cdp_status", lambda *args, **kwargs: "unavailable"
    )
    monkeypatch.setattr(launcher, "launch_chrome", launch)
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(clock))

    with pytest.raises(ConnectionError, match="within 1.0s"):
        launcher.ensure_chrome(timeout_sec=1.0)

    launch.assert_not_called()
