import logging
import sys

import pytest

from app.logging import MaskingFormatter, mask_sensitive


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("user john.doe@example.com logged in", "user j***@example.com logged in"),
        ("card 4111 1111 1111 1234 declined", "card ****1234 declined"),
        ("card 4111111111111234", "card ****1234"),
        ("phone +7 (912) 345-67-89", "phone +***89"),
        ("Authorization: Bearer abc.def.ghi", "Authorization: ***"),
        ("header bearer abc.def", "header bearer ***"),
        ('{"password": "hunter2", "ok": 1}', '{"password": "***", "ok": 1}'),
        ("api_key=sk_live_123&x=1", "api_key=***&x=1"),
        ("postgresql://app:s3cret@db:5432/app", "postgresql://app:***@db:5432/app"),
    ],
)
def test_mask_sensitive(raw: str, expected: str) -> None:
    assert mask_sensitive(raw) == expected


def test_amounts_and_ids_are_not_masked() -> None:
    text = "order 12345 amount 100.500000 USDT"
    assert mask_sensitive(text) == text


def test_formatter_masks_args_and_exceptions() -> None:
    formatter = MaskingFormatter("%(message)s")
    try:
        raise ValueError("bad email a.b@example.com")
    except ValueError:
        record = logging.LogRecord(
            "t", logging.ERROR, __file__, 1, "user %s", ("x.y@example.com",), sys.exc_info()
        )

    output = formatter.format(record)

    assert "x.y@example.com" not in output
    assert "a.b@example.com" not in output
    assert "x***@example.com" in output
