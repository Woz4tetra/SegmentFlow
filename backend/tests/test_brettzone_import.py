"""Tests for BrettZone import helpers."""

import pytest

from app.core.brettzone import list_downloadables


def test_list_downloadables_filters_program_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Program feed camera entries are excluded."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {"proxy720":"https://cdn.example.com/a.mp4","camera":"Overhead 1","category":"overhead"},
          {"proxy720":"https://cdn.example.com/b.mp4","camera":"Program Feed","category":"program"}
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].media_url == "https://cdn.example.com/a.mp4"
    assert "program feed" not in entries[0].camera.lower()

