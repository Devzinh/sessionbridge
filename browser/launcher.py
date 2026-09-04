import os
import subprocess
import time
import socket
import urllib.request
import json
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlsplit

DEFAULT_CDP_PORT = 9222
DEFAULT_PROFILE_DIR = Path(__file__).resolve().parent.parent / ".chrome_profile"
SESSION_MARKER_NAME = "SessionBridgeActivePort"

COMMON_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome_executable() -> Optional[str]:
    """Finds Chrome, Brave, or Edge executable on Windows."""
    for path in COMMON_CHROME_PATHS:
        if os.path.isfile(path):
            return path
    return None


def is_port_listening(host: str = "127.0.0.1", port: int = DEFAULT_CDP_PORT) -> bool:
    """Checks if a local TCP port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def is_cdp_ready(
    port: int = DEFAULT_CDP_PORT,
    timeout_sec: float = 2.0,
) -> bool:
    """Checks if Chrome DevTools Protocol is actively responding to JSON version queries."""
    return get_cdp_websocket_url(port, timeout_sec) is not None


def get_cdp_websocket_url(
    port: int = DEFAULT_CDP_PORT,
    timeout_sec: float = 2.0,
) -> Optional[str]:
    """Returns the browser websocket URL exposed by a loopback CDP endpoint."""
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SessionBridge"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode())
            websocket_url = data.get("webSocketDebuggerUrl")
            return websocket_url if isinstance(websocket_url, str) else None
    except Exception:
        return None


def read_devtools_active_port(user_data_dir: Path | str) -> Optional[tuple[int, str]]:
    """Reads Chrome's native profile marker without accepting malformed content."""
    profile_path = Path(user_data_dir)
    for marker_name in (SESSION_MARKER_NAME, "DevToolsActivePort"):
        try:
            lines = (profile_path / marker_name).read_text(encoding="utf-8").splitlines()
            if len(lines) < 2 or not lines[1].startswith("/devtools/browser/"):
                continue
            return int(lines[0]), lines[1]
        except (OSError, UnicodeError, ValueError):
            continue
    return None


def write_session_marker(user_data_dir: Path | str, port: int, websocket_url: str) -> None:
    """Records identity only for a browser process launched by SessionBridge."""
    websocket_path = urlsplit(websocket_url).path
    if not websocket_path.startswith("/devtools/browser/"):
        raise ValueError("Invalid CDP browser websocket URL")
    profile_path = Path(user_data_dir)
    profile_path.mkdir(parents=True, exist_ok=True)
    (profile_path / SESSION_MARKER_NAME).write_text(
        f"{port}\n{websocket_path}\n", encoding="utf-8"
    )


def get_dedicated_cdp_status(
    user_data_dir: Path | str,
    port: int = DEFAULT_CDP_PORT,
    timeout_sec: float = 2.0,
) -> Literal["ready", "mismatch", "unavailable"]:
    """Identifies whether the endpoint belongs to the requested Chrome profile."""
    websocket_url = get_cdp_websocket_url(port, timeout_sec)
    if websocket_url is None:
        return "unavailable"

    marker = read_devtools_active_port(user_data_dir)
    if marker is None:
        return "mismatch"

    marker_port, marker_path = marker
    try:
        endpoint_path = urlsplit(websocket_url).path
    except ValueError:
        return "mismatch"
    return "ready" if marker_port == port and endpoint_path == marker_path else "mismatch"


def launch_chrome(
    port: int = DEFAULT_CDP_PORT,
    user_data_dir: Optional[Path | str] = None,
    url: Optional[str] = None,
    headless: bool = False,
) -> subprocess.Popen:
    """
    Launches Chrome with a dedicated user data profile and remote debugging enabled.
    A dedicated profile is required so that Chrome doesn't join an existing default session
    which ignores --remote-debugging-port.
    """
    chrome_path = find_chrome_executable()
    if not chrome_path:
        raise FileNotFoundError(
            "Chrome executable not found. Please verify Google Chrome is installed."
        )

    profile_path = Path(user_data_dir) if user_data_dir else DEFAULT_PROFILE_DIR
    profile_path.mkdir(parents=True, exist_ok=True)

    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if headless:
        args.append("--headless=new")

    if url:
        args.append(url)
    else:
        args.append("about:blank")

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        shell=False,
    )
    return process


def ensure_chrome(
    port: int = DEFAULT_CDP_PORT,
    user_data_dir: Optional[Path | str] = None,
    url: Optional[str] = None,
    timeout_sec: float = 10.0,
) -> bool:
    """
    Ensures Chrome is up and CDP is ready. If not running, launches it and waits until ready.
    Raises ConnectionError if Chrome exits early or CDP misses the deadline.
    """
    profile_path = Path(user_data_dir) if user_data_dir else DEFAULT_PROFILE_DIR
    deadline = time.monotonic() + timeout_sec
    remaining = max(0.0, deadline - time.monotonic())
    status = get_dedicated_cdp_status(
        profile_path, port, timeout_sec=min(2.0, remaining)
    )
    if status == "ready":
        return True
    if status == "mismatch":
        raise ConnectionError(
            f"Chrome CDP endpoint on port {port} does not match dedicated profile {profile_path}"
        )

    if deadline - time.monotonic() <= 0:
        raise ConnectionError(
            f"Chrome CDP did not become ready on port {port} within {timeout_sec}s"
        )

    for marker_name in (SESSION_MARKER_NAME, "DevToolsActivePort"):
        try:
            (profile_path / marker_name).unlink()
        except FileNotFoundError:
            pass

    process = launch_chrome(port=port, user_data_dir=profile_path, url=url)

    while True:
        returncode = process.poll()
        if returncode is not None:
            raise ConnectionError(
                f"Chrome exited before CDP was ready with return code {returncode}"
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        status = get_dedicated_cdp_status(
            profile_path, port, timeout_sec=min(2.0, remaining)
        )
        if status == "ready":
            return True
        if status == "mismatch":
            websocket_url = get_cdp_websocket_url(
                port, timeout_sec=min(2.0, remaining)
            )
            if websocket_url is not None and read_devtools_active_port(profile_path) is None:
                write_session_marker(profile_path, port, websocket_url)
                return True
            raise ConnectionError(
                f"Chrome CDP endpoint on port {port} does not match dedicated profile {profile_path}"
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.4, remaining))

    raise ConnectionError(f"Chrome CDP did not become ready on port {port} within {timeout_sec}s")


if __name__ == "__main__":
    print(f"Finding Chrome: {find_chrome_executable()}")
    print(f"CDP ready on {DEFAULT_CDP_PORT}: {is_cdp_ready()}")
    if not is_cdp_ready():
        print("Launching Chrome...")
        success = ensure_chrome()
        print(f"Chrome launched and ready: {success}")
