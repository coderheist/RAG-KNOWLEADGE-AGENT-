"""Every setting in app/config.py must appear in .env.example (acceptance criterion: the example is complete)."""
import re
from pathlib import Path

from app.config import Settings

EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_env_example_lists_every_setting() -> None:
    keys = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", EXAMPLE.read_text(encoding="utf-8"), re.M))
    missing = sorted(name for name in Settings.model_fields if name not in keys)
    assert not missing, f"add these settings to backend/.env.example: {missing}"
