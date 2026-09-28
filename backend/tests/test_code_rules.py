"""Static guards for project-wide rules from AGENTS.md."""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _python_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


def test_no_float_in_application_code() -> None:
    """Money rule: amounts are Decimal only. `float` is banned in app/ entirely to keep it simple.

    If a non-money float is ever truly needed, discuss it and add an explicit allowlist here.
    """
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Name) and node.id == "float") or (
                isinstance(node, ast.Constant) and isinstance(node.value, float)
            ):
                offenders.append(f"{path.relative_to(APP_DIR.parent)}:{node.lineno}")

    assert not offenders, f"float is forbidden in app/ (use Decimal): {offenders}"


def test_env_is_read_only_in_config() -> None:
    """Settings are read only in app/config.py (pydantic-settings), never via os.environ."""
    offenders = [
        str(path.relative_to(APP_DIR.parent))
        for path in _python_files()
        if path.name != "config.py"
        and any(s in path.read_text(encoding="utf-8") for s in ("os.environ", "os.getenv"))
    ]

    assert not offenders, f"read settings via app.config.get_settings(): {offenders}"
