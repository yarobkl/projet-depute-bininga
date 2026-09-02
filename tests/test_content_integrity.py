"""Contrats de traçabilité des actualités manuelles."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import content_integrity


def site(*urls):
    return {"actus": {"cards": [{"title": str(i), "sourceUrl": url} for i, url in enumerate(urls)]}}


def test_existing_legacy_gap_does_not_block_unrelated_edits():
    assert content_integrity.validate_news_source_change(site("", "https://source.test"), site("", "https://source.test")) == ""


def test_new_unsourced_article_is_blocked():
    message = content_integrity.validate_news_source_change(site(""), site("", ""))
    assert "nouvelle actualité" in message


def test_new_sourced_article_is_allowed_and_bad_url_is_blocked():
    assert content_integrity.validate_news_source_change(site(""), site("", "https://source.test/article")) == ""
    assert "http" in content_integrity.validate_news_source_change(site(""), site("javascript:alert(1)"))


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("OK", test.__name__)
