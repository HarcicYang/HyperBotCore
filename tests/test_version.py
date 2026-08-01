import tomllib
from importlib import metadata
from pathlib import Path

import hyperot

_ROOT = Path(__file__).resolve().parent.parent


def test_runtime_version_matches_pyproject():
    with open(_ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    declared = pyproject["project"]["version"]
    assert hyperot.__version__ == declared
    assert metadata.version("hyper-bot") == declared
