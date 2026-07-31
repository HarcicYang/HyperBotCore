import json
from pathlib import Path

TEST_CONFIG = {
    "protocol": "OneBot",
    "owner": [],
    "black_list": [],
    "silents": [],
    "connection": {
        "mode": "FWS",
        "ob_auto_startup": False,
        "ob_exec": "",
        "ob_startup_path": "",
        "ob_log_output": False,
        "host": "127.0.0.1",
        "port": 5004,
        "token": "",
        "auth": "",
    },
    "log_level": "ERROR",
    "log_use_nf": False,
    "uin": 0,
    "max_workers": 1,
    "others": {},
}

_ROOT = Path(__file__).resolve().parent.parent


def _ensure_config() -> None:
    cfg = _ROOT / "config.json"
    if not cfg.exists():
        cfg.write_text(json.dumps(TEST_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")


_ensure_config()


def _setup() -> None:
    import hyperot

    hyperot.init()
    from hyperot import listener  # noqa: F401  (triggers events.init())


_setup()
