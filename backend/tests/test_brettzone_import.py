"""Tests for BrettZone import helpers."""

import pytest

from app.core.brettzone import (
    _extract_fight_bounds_from_match_data,
    _extract_robot_names_from_match_data,
    _extract_robot_thumbnails_from_match_data,
    _is_valid_robot_name,
    list_downloadables,
)
from app.core.trim_utils import resolve_import_trim_bounds


def test_robot_name_validation_accepts_real_names() -> None:
    """Real robot names should be accepted by validation."""
    assert _is_valid_robot_name("Paradox")
    assert _is_valid_robot_name("Buzzzz-Kill")
    assert _is_valid_robot_name("0-0")
    assert not _is_valid_robot_name("0W-0L")
    assert not _is_valid_robot_name("unknown")


def test_extract_robot_names_from_match_data_players() -> None:
    """Player names are extracted from window.MATCH_DATA.player1/player2."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        gameID: "EX-123",
        tournamentID: "nhrl_sep24_12lb",
        player1: { name: "Paradox", cleanName: "paradox" },
        player2: { name: "Buzzzz-Kill", cleanName: "buzzzzkill" }
      };
    </script>
    """
    assert _extract_robot_names_from_match_data(sample_html) == ["Paradox", "Buzzzz-Kill"]


def test_extract_robot_thumbnails_from_match_data_players() -> None:
    """Player clean names map to getBotPic thumbnail URLs."""
    sample_html = """
    <script>
      window.MATCH_DATA = {
        gameID: "EX-123",
        tournamentID: "nhrl_sep24_12lb",
        player1: { name: "Paradox", cleanName: "paradox" },
        player2: { name: "Buzzzz-Kill", cleanName: "buzzzzkill" }
      };
    </script>
    """
    assert _extract_robot_thumbnails_from_match_data(
        sample_html,
        "https://brettzone.nhrl.io/brettZone/fightReviewSync.php?gameID=EX-123&tournamentID=nhrl_sep24_12lb",
    ) == {
        "Paradox": "https://brettzone.nhrl.io/brettZone/getBotPic.php?bot=paradox",
        "Buzzzz-Kill": "https://brettzone.nhrl.io/brettZone/getBotPic.php?bot=buzzzzkill",
    }


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


def test_extract_fight_bounds_from_match_data_seconds() -> None:
    sample_html = """
    <script>
      window.MATCH_DATA = {
        clipStart: 42.5,
        clipEnd: 178.25,
        gameID: "EX-123"
      };
    </script>
    """
    assert _extract_fight_bounds_from_match_data(sample_html) == (42.5, 178.25)


def test_extract_fight_bounds_from_match_data_time_strings() -> None:
    sample_html = """
    <script>
      window.MATCH_DATA = {
        "trim_start": "00:15",
        "trim_end": "03:00",
        "gameID": "EX-123"
      };
    </script>
    """
    assert _extract_fight_bounds_from_match_data(sample_html) == (15.0, 180.0)


def test_list_downloadables_carries_fight_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_html = """
    <script>
      window.MATCH_DATA = {
        recordings: [
          {
            "proxy720":"https://cdn.example.com/a.mp4",
            "camera":"Cage 2 Overhead High",
            "category":"overhead",
            "clipStart":"00:12",
            "clipEnd":"02:58"
          }
        ],
        gameID: "123"
      };
    </script>
    """
    monkeypatch.setattr("app.core.brettzone.fetch_html", lambda url, timeout=20.0: sample_html)
    entries = list_downloadables("https://brettzone.net/fightReviewSync.php?gameID=1&tournamentID=2")
    assert len(entries) == 1
    assert entries[0].fight_start_sec == 12.0
    assert entries[0].fight_end_sec == 178.0


def test_resolve_trim_bounds_uses_fight_bounds_when_valid(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class FakeVideoInfo:
        fps = 30.0
        frame_count = 9000

    monkeypatch.setattr(
        "app.core.trim_utils.get_video_info",
        lambda _path: FakeVideoInfo(),
    )
    bounds = resolve_import_trim_bounds(tmp_path / "video.mp4", 10.0, 20.0)
    assert bounds == (10.0, 20.0)


def test_resolve_trim_bounds_falls_back_to_full_duration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class FakeVideoInfo:
        fps = 25.0
        frame_count = 500

    monkeypatch.setattr(
        "app.core.trim_utils.get_video_info",
        lambda _path: FakeVideoInfo(),
    )
    bounds = resolve_import_trim_bounds(tmp_path / "video.mp4")
    assert bounds == (0.0, 20.0)


def test_resolve_trim_bounds_falls_back_when_invalid_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class FakeVideoInfo:
        fps = 25.0
        frame_count = 500

    monkeypatch.setattr(
        "app.core.trim_utils.get_video_info",
        lambda _path: FakeVideoInfo(),
    )
    bounds = resolve_import_trim_bounds(tmp_path / "video.mp4", 30.0, 20.0)
    assert bounds == (0.0, 20.0)

