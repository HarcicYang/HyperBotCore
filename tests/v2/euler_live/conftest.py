import json
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest


@dataclass(frozen=True)
class EulerLive:
    url: str
    group_id: int
    user_id: int
    run_dir: Path


def _enabled() -> bool:
    return os.environ.get("HYPEROT_EULER_LIVE") == "1"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _lagrange_task_env(root: Path) -> dict[str, str]:
    task_file = root / ".zed" / "tasks.json"
    tasks = json.loads(task_file.read_text(encoding="utf-8"))
    for task in tasks:
        if task.get("label") == "Local Test":
            return dict(task.get("env", {}))
    raise RuntimeError("lagrange-python Local Test task not found")


def _signer_config(sign_url: str) -> tuple[str, str]:
    parsed = urlsplit(sign_url)
    token = parsed.username or ""
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}", token


@pytest.fixture(scope="session")
def euler_live(tmp_path_factory: pytest.TempPathFactory) -> EulerLive:
    if not _enabled():
        pytest.skip("set HYPEROT_EULER_LIVE=1 to run live EulerOneBot tests")
    if shutil.which("uv") is None:
        pytest.skip("uv is required to launch EulerOneBot")

    euler_root = Path(os.environ.get("HYPEROT_EULER_ROOT", "/run/media/harcic8042/HarcicYang/projects/EulerOneBot"))
    lagrange_root = Path(
        os.environ.get("HYPEROT_LAGRANGE_PYTHON_ROOT", "/run/media/harcic8042/HarcicYang/projects/lagrange-python")
    )
    env_values = _lagrange_task_env(lagrange_root)
    sign_url = os.environ.get("LAGRANGE_SIGN_URL") or env_values["LAGRANGE_SIGN_URL"]
    uin = int(os.environ.get("LAGRANGE_UIN") or env_values["LAGRANGE_UIN"])
    signer_url, signer_token = _signer_config(sign_url)

    run_dir = tmp_path_factory.mktemp("euler-live")
    shutil.copy2(lagrange_root / "device.json", run_dir / "device.json")
    shutil.copy2(lagrange_root / "sig.bin", run_dir / "sig.bin")
    port = _free_port()
    appconfig = {
        "log_level": "INFO",
        "log_nf": False,
        "connections": [{"type": "ForwardWebSocket", "url": f"ws://127.0.0.1:{port}"}],
        "login": {
            "uin": uin,
            "signer_url": signer_url,
            "signer_token": signer_token,
            "use_custom": False,
            "appinfo_path": "./appinfo.json",
            "setup_watchdog": False,
            "use_ipv6": False,
            "use_optimum": True,
        },
        "heartbeat": {"enabled": True, "interval": 15000},
    }
    (run_dir / "appconfig.json").write_text(json.dumps(appconfig, indent=2), encoding="utf-8")
    log_path = run_dir / "euler.log"
    log_file = log_path.open("wb")
    process = subprocess.Popen(
        ["uv", "run", "--project", str(euler_root), "python", str(euler_root / "main.py")],
        cwd=run_dir,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"EulerOneBot exited early; log: {log_path}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise TimeoutError(f"EulerOneBot did not start; log: {log_path}")
        yield EulerLive(
            url=f"ws://127.0.0.1:{port}",
            group_id=int(os.environ.get("HYPEROT_TEST_GROUP_ID", "623371208")),
            user_id=int(os.environ.get("HYPEROT_TEST_USER_ID", "2488529467")),
            run_dir=run_dir,
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log_file.close()
