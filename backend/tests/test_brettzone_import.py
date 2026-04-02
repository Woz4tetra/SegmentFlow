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


def test_list_downloadables_filters_program_feed_hyphenated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Program-feed variants with hyphens are excluded."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {"proxy720":"https://cdn.example.com/a.mp4","camera":"Overhead 1","category":"overhead"},
          {"proxy720":"https://cdn.example.com/b.mp4","camera":"Program-Feed","category":"program"}
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].media_url == "https://cdn.example.com/a.mp4"


def test_list_downloadables_extracts_robot_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Robot names are extracted from BrettZone metadata when available."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {
            "proxy720":"https://cdn.example.com/a.mp4",
            "camera":"Overhead 1",
            "category":"overhead",
            "redRobotName":"Big Dill",
            "blueRobotName":"Riptide"
          }
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")

    assert len(entries) == 1
    assert entries[0].robot_names == ["Big Dill", "Riptide"]


def test_list_downloadables_extracts_robot_thumbnails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Robot thumbnail URLs are extracted from BrettZone metadata."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {
            "proxy720":"https://cdn.example.com/a.mp4",
            "camera":"Overhead 1",
            "category":"overhead",
            "redRobotName":"Big Dill",
            "blueRobotName":"Riptide",
            "redRobotImage":"https://nhrl.io/media/big-dill.jpg",
            "blueRobotImage":"https://nhrl.io/media/riptide.jpg"
          }
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")

    assert len(entries) == 1
    assert entries[0].robot_thumbnails == {
        "Big Dill": "https://nhrl.io/media/big-dill.jpg",
        "Riptide": "https://nhrl.io/media/riptide.jpg",
    }

