"""Tests for BrettZone import helpers."""

import pytest

from app.core.brettzone import _is_valid_robot_name, list_downloadables


def test_robot_name_validation_accepts_real_names() -> None:
    """Real robot names should be accepted by validation."""
    assert _is_valid_robot_name("Paradox")
    assert _is_valid_robot_name("Buzzzz-Kill")
    assert not _is_valid_robot_name("unknown")


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


def test_list_downloadables_extracts_red_blue_name_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Robot names are extracted when metadata uses redName/blueName keys."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {
            "proxy720":"https://cdn.example.com/a.mp4",
            "camera":"Overhead 1",
            "category":"overhead",
            "redName":"Ripperoni",
            "blueName":"Whiplash"
          }
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")

    assert len(entries) == 1
    assert entries[0].robot_names == ["Ripperoni", "Whiplash"]


def test_list_downloadables_extracts_unquoted_js_name_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Robot names are extracted from unquoted JS object keys."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {
            proxy720: "https://cdn.example.com/a.mp4",
            camera: "Overhead 1",
            category: "overhead",
            redName: "End Game",
            blueName: "SawBlaze"
          }
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")

    # JSON parser fallback won't parse unquoted keys, but regex extraction should still recover names.
    assert entries == []
    # Re-run with an MP4 fallback in same page to exercise name extraction on fallback path.
    fallback_html = sample_html + '<video src="https:\\/\\/cdn.example.com\\/fallback.mp4"></video>'
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: fallback_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].robot_names == ["End Game", "SawBlaze"]


def test_list_downloadables_extracts_vs_names_from_page_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Robot names are extracted from visible page text when metadata keys are absent."""
    sample_html = """
    <html>
      <head><title>Eviscerator vs Injection! - Multi-Camera</title></head>
      <body>
        <h1>Eviscerator vs Injection!</h1>
        <video src="https:\\/\\/cdn.example.com\\/fallback.mp4"></video>
      </body>
    </html>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].robot_names == ["Eviscerator", "Injection!"]


def test_list_downloadables_fallbacks_to_single_camera_page_for_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If sync page lacks names, fallback to fightReview page should populate them."""
    sync_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {"proxy720":"https://cdn.example.com/a.mp4","camera":"Cage 4 Blue High","category":"other"}
        ],
        gameID: "123"
      };
    </script>
    """
    single_html = """
    <html>
      <head><title>Paradox vs Buzzzz-Kill - Fight Review</title></head>
      <body><h1>Paradox vs Buzzzz-Kill</h1></body>
    </html>
    """

    def fake_fetch_html(url: str, timeout: float = 20.0) -> str:
        if "fightReviewSync.php" in url:
            return sync_html
        if "fightReview.php" in url:
            return single_html
        return ""

    monkeypatch.setattr("app.core.brettzone.fetch_html", fake_fetch_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].robot_names == ["Buzzzz-Kill", "Paradox"]


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

