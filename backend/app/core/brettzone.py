"""Helpers for discovering and downloading BrettZone fight videos."""

from __future__ import annotations

import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

FIGHT_RE = re.compile(
    r"(fightReviewSync\.php\?gameID=[^&]+&tournamentID=[^\"'<> ]+)",
    re.IGNORECASE,
)
FIGHT_URL_PATTERN = re.compile(r"fightReviewSync\.php\?gameID=", re.IGNORECASE)
DEFAULT_SOURCE_PAGES = [
    "https://brettzone.nhrl.io/brettZone/index.php",
    "https://brettzone.nhrl.io/brettZone/robotFights.php",
    "https://brettzone.net/",
    "https://www.brettzone.net/",
]
PROGRAM_FEED_RE = re.compile(r"program[\s\-_]*feed", re.IGNORECASE)


@dataclass(slots=True)
class BrettzoneEntry:
    """A downloadable BrettZone recording entry."""

    media_url: str
    fight_url: str
    camera: str
    category: str
    robot_names: list[str] = field(default_factory=list)
    robot_thumbnails: dict[str, str] = field(default_factory=dict)


def fetch_html(url: str, timeout: float = 20.0) -> str:
    request = Request(
        url=url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def discover_fight_links(base_url: str, html: str) -> list[str]:
    links: set[str] = set()
    for match in FIGHT_RE.finditer(html):
        links.add(urljoin(base_url, match.group(1)))

    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
    for match in href_pattern.finditer(html):
        href = match.group(1).strip()
        if FIGHT_URL_PATTERN.search(href):
            links.add(urljoin(base_url, href))

    return sorted(links)


def _extract_recordings_from_html(html: str) -> list[dict]:
    match = re.search(r"recordings\s*:\s*(\[.*?\])\s*,\s*gameID\s*:", html, re.S)
    if not match:
        return []
    try:
        decoded = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [entry for entry in decoded if isinstance(entry, dict)]


def _extract_mp4_urls(html: str) -> list[str]:
    urls = re.findall(r"https:\\/\\/[^\"'\\s>]+\\.mp4", html)
    normalized = [url.replace("\\/", "/") for url in urls]
    return sorted(set(normalized))


def _is_program_feed(camera: str) -> bool:
    return bool(PROGRAM_FEED_RE.search(camera))


def _normalize_robot_name_for_compare(name: str) -> str:
    """Normalize robot names for matching/dedup only."""
    collapsed = " ".join(name.replace("_", " ").split()).strip().casefold()
    return collapsed


def _display_robot_name(name: str) -> str:
    """Preserve BrettZone display name (trim outer whitespace only)."""
    return name.strip()


def _is_valid_robot_name(name: str) -> bool:
    normalized = _normalize_robot_name_for_compare(name)
    if not normalized:
        return False
    return bool(normalized in {"n/a", "na", "unknown", "tbd", "none", "null"})


def _extract_robot_names_from_recording(recording: dict) -> list[str]:
    """Extract likely robot names from a recording dict."""
    robot_names: list[str] = []
    for key, value in recording.items():
        if not isinstance(value, str):
            continue
        key_lower = key.lower()
        if "name" not in key_lower:
            continue
        # Support both explicit robot/bot fields and red/blue side name fields.
        if (
            "robot" not in key_lower
            and "bot" not in key_lower
            and "red" not in key_lower
            and "blue" not in key_lower
        ):
            continue
        display_name = _display_robot_name(value)
        if _is_valid_robot_name(display_name):
            robot_names.append(display_name)
    return robot_names


def _extract_robot_thumbnails_from_recording(recording: dict, base_url: str) -> dict[str, str]:
    """Extract robot name -> thumbnail URL mappings from a recording dict."""
    side_to_name: dict[str, str] = {}
    side_to_image: dict[str, str] = {}

    for key, value in recording.items():
        if not isinstance(value, str):
            continue
        key_lower = key.lower()
        side = "red" if "red" in key_lower else ("blue" if "blue" in key_lower else "")
        if not side:
            continue

        if ("name" in key_lower) and (
            "robot" in key_lower or "bot" in key_lower or "red" in key_lower or "blue" in key_lower
        ):
            display_name = _display_robot_name(value)
            if _is_valid_robot_name(display_name):
                side_to_name[side] = display_name
            continue

        has_image_hint = any(
            token in key_lower
            for token in ("image", "img", "thumb", "thumbnail", "photo", "picture", "avatar", "logo")
        )
        if has_image_hint and value:
            side_to_image[side] = urljoin(base_url, value)

    thumbnail_map: dict[str, str] = {}
    for side, robot_name in side_to_name.items():
        image_url = side_to_image.get(side)
        if image_url:
            thumbnail_map[robot_name] = image_url
    return thumbnail_map


def _extract_robot_names_from_html(html: str) -> list[str]:
    """Best-effort extraction of robot names from fight page HTML."""
    names: set[str] = set()
    # Common patterns seen in embedded page JSON.
    patterns = [
        # JSON-style quoted keys
        r'"(?:red|blue)[A-Za-z_]*?(?:robot|bot)[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
        r'"(?:robot|bot)[A-Za-z_]*?(?:red|blue)[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
        r'"(?:red|blue)[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
        # JS object-style unquoted keys, single or double quoted values
        r'(?:^|[,{]\s*)(?:red|blue)[A-Za-z_]*?(?:robot|bot)[A-Za-z_]*?name\s*:\s*[\'"]([^\'"]+)[\'"]',
        r'(?:^|[,{]\s*)(?:robot|bot)[A-Za-z_]*?(?:red|blue)[A-Za-z_]*?name\s*:\s*[\'"]([^\'"]+)[\'"]',
        r'(?:^|[,{]\s*)(?:red|blue)[A-Za-z_]*?name\s*:\s*[\'"]([^\'"]+)[\'"]',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, flags=re.IGNORECASE):
            display_name = _display_robot_name(match.group(1))
            if _is_valid_robot_name(display_name):
                names.add(display_name)
    for left, right in _extract_robot_names_from_vs_text(html):
        if _is_valid_robot_name(left):
            names.add(left)
        if _is_valid_robot_name(right):
            names.add(right)
    return sorted(names)


def _extract_robot_names_from_vs_text(html: str) -> list[tuple[str, str]]:
    """Extract robot names from page text patterns like 'Robot A vs Robot B'."""
    results: list[tuple[str, str]] = []
    disallowed = {
        "multi-camera",
        "single",
        "clip",
        "fights",
        "tournament",
        "camera",
        "download all",
    }

    def add_pair(left_raw: str, right_raw: str) -> None:
        left = _display_robot_name(left_raw)
        right = _display_robot_name(right_raw)
        if not left or not right:
            return
        if left.casefold() in disallowed or right.casefold() in disallowed:
            return
        if len(left) > 50 or len(right) > 50:
            return
        results.append((left, right))

    # First pass: title/heading fields are the most reliable.
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        _extract_vs_pairs_from_text(title_match.group(1), add_pair)

    for heading in re.finditer(r"<h[1-3][^>]*>([^<]+)</h[1-3]>", html, flags=re.IGNORECASE):
        _extract_vs_pairs_from_text(heading.group(1), add_pair)

    # Second pass: flattened text catch-all.
    text = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(text.split())
    _extract_vs_pairs_from_text(text, add_pair)

    # Deduplicate while preserving order.
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for pair in results:
        key = (pair[0].casefold(), pair[1].casefold())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(pair)
    return deduped


def _extract_vs_pairs_from_text(
    text: str,
    add_pair: Callable[[str, str], None],
) -> None:
    """Extract 'A vs B' pair(s) from text and pass them to add_pair."""
    patterns = [
        # Common title/header format: "A vs B - Multi-Camera"
        r"([A-Za-z0-9!'\-&\.\+ ]{2,40}?)\s+vs\.?\s+([A-Za-z0-9!'\-&\.\+ ]{2,40}?)(?=\s*-\s*|$)",
        # Generic bounded pair in larger text.
        r"([A-Za-z0-9!'\-&\.\+ ]{2,30}?)\s+vs\.?\s+([A-Za-z0-9!'\-&\.\+ ]{2,30}?)\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            add_pair(match.group(1), match.group(2))


def _extract_robot_thumbnails_from_html(html: str, base_url: str) -> dict[str, str]:
    """Best-effort extraction of robot name -> thumbnail URL mappings from HTML."""
    side_to_name: dict[str, str] = {}
    side_to_image: dict[str, str] = {}

    for side in ("red", "blue"):
        name_patterns = [
            rf'"{side}[A-Za-z_]*?(?:robot|bot)[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
            rf'"(?:robot|bot)[A-Za-z_]*?{side}[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
            rf'"{side}[A-Za-z_]*?name"\s*:\s*"([^"]+)"',
        ]
        image_patterns = [
            rf'"{side}[A-Za-z_]*?(?:robot|bot)[A-Za-z_]*?(?:image|img|thumb|thumbnail|photo|picture|avatar|logo)"\s*:\s*"([^"]+)"',
            rf'"(?:robot|bot)[A-Za-z_]*?{side}[A-Za-z_]*?(?:image|img|thumb|thumbnail|photo|picture|avatar|logo)"\s*:\s*"([^"]+)"',
            rf'(?:^|[,\{{]\s*){side}[A-Za-z_]*?(?:robot|bot)[A-Za-z_]*?(?:image|img|thumb|thumbnail|photo|picture|avatar|logo)\s*:\s*[\'"]([^\'"]+)[\'"]',
            rf'(?:^|[,\{{]\s*)(?:robot|bot)[A-Za-z_]*?{side}[A-Za-z_]*?(?:image|img|thumb|thumbnail|photo|picture|avatar|logo)\s*:\s*[\'"]([^\'"]+)[\'"]',
        ]
        for pattern in name_patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE):
                display_name = _display_robot_name(match.group(1))
                if _is_valid_robot_name(display_name):
                    side_to_name[side] = display_name
        for pattern in image_patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE):
                candidate = match.group(1).strip()
                if candidate:
                    side_to_image[side] = urljoin(base_url, candidate.replace("\\/", "/"))

    thumbnail_map: dict[str, str] = {}
    for side, robot_name in side_to_name.items():
        image_url = side_to_image.get(side)
        if image_url:
            thumbnail_map[robot_name] = image_url
    return thumbnail_map


def list_downloadables(fight_url: str, timeout: float = 20.0) -> list[BrettzoneEntry]:
    html = fetch_html(fight_url, timeout=timeout)
    recordings = _extract_recordings_from_html(html)
    entries: list[BrettzoneEntry] = []
    robot_names: set[str] = set()
    robot_thumbnails: dict[str, str] = {}

    for recording in recordings:
        for name in _extract_robot_names_from_recording(recording):
            robot_names.add(name)
        for robot_name, image_url in _extract_robot_thumbnails_from_recording(recording, fight_url).items():
            robot_thumbnails.setdefault(robot_name, image_url)
    for name in _extract_robot_names_from_html(html):
        robot_names.add(name)
    for robot_name, image_url in _extract_robot_thumbnails_from_html(html, fight_url).items():
        robot_thumbnails.setdefault(robot_name, image_url)

    # Some fights expose names only on the single-camera page.
    if not robot_names and "fightReviewSync.php" in fight_url:
        single_camera_url = fight_url.replace("fightReviewSync.php", "fightReview.php")
        try:
            single_html = fetch_html(single_camera_url, timeout=timeout)
            for name in _extract_robot_names_from_html(single_html):
                robot_names.add(name)
            for robot_name, image_url in _extract_robot_thumbnails_from_html(
                single_html, single_camera_url
            ).items():
                robot_thumbnails.setdefault(robot_name, image_url)
        except (URLError, HTTPError, OSError):
            pass
    robot_names_list = sorted(robot_names)

    for recording in recordings:
        media_url = recording.get("proxy720") or recording.get("proxy360") or recording.get("s3path")
        if not isinstance(media_url, str) or not media_url:
            continue
        camera = str(recording.get("camera") or "")
        if _is_program_feed(camera):
            continue
        entries.append(
            BrettzoneEntry(
                media_url=media_url,
                fight_url=fight_url,
                camera=camera or "unknown_camera",
                category=str(recording.get("category") or "unknown_category"),
                robot_names=robot_names_list,
                robot_thumbnails=dict(robot_thumbnails),
            )
        )

    if entries:
        return entries

    # Fallback: direct mp4 extraction from page source.
    for media_url in _extract_mp4_urls(html):
        entries.append(
            BrettzoneEntry(
                media_url=media_url,
                fight_url=fight_url,
                camera="fallback",
                category="fallback",
                robot_names=robot_names_list,
                robot_thumbnails=dict(robot_thumbnails),
            )
        )
    return entries


def discover_random_entry(
    rng: random.Random | None = None,
    source_pages: list[str] | None = None,
    timeout: float = 20.0,
) -> BrettzoneEntry:
    rand = rng or random.Random()
    pages = source_pages or DEFAULT_SOURCE_PAGES
    fight_links: set[str] = set()

    for page_url in pages:
        try:
            html = fetch_html(page_url, timeout=timeout)
            fight_links.update(discover_fight_links(page_url, html))
        except (URLError, HTTPError, OSError):
            continue

    if not fight_links:
        raise ValueError(
            "Could not reach BrettZone or discover fights. "
            "Please try again later or import via direct URL."
        )

    shuffled_fights = list(fight_links)
    rand.shuffle(shuffled_fights)
    for fight_url in shuffled_fights:
        entries = list_downloadables(fight_url, timeout=timeout)
        if entries:
            return rand.choice(entries)

    raise ValueError("No downloadable BrettZone videos were found.")


def discover_entry_from_url(
    brettzone_url: str,
    rng: random.Random | None = None,
    timeout: float = 20.0,
) -> BrettzoneEntry:
    rand = rng or random.Random()
    parsed = urlparse(brettzone_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid BrettZone URL.")
    host = parsed.netloc.lower()
    if "brettzone" not in host:
        raise ValueError("URL must be a BrettZone URL.")

    # Direct fight page.
    if FIGHT_URL_PATTERN.search(brettzone_url):
        entries = list_downloadables(brettzone_url, timeout=timeout)
        if entries:
            return rand.choice(entries)
        raise ValueError("No downloadable videos found at the provided fight URL.")

    try:
        html = fetch_html(brettzone_url, timeout=timeout)
    except (URLError, HTTPError, OSError) as exc:
        raise ValueError("Could not fetch the provided BrettZone URL.") from exc
    # If page itself has recordings, use that.
    recordings_here = list_downloadables(brettzone_url, timeout=timeout)
    if recordings_here:
        return rand.choice(recordings_here)

    fight_links = discover_fight_links(brettzone_url, html)
    if not fight_links:
        raise ValueError("No fight links found on the provided BrettZone page.")

    rand.shuffle(fight_links)
    for fight_url in fight_links:
        entries = list_downloadables(fight_url, timeout=timeout)
        if entries:
            return rand.choice(entries)

    raise ValueError("No downloadable videos found from fight links on the provided page.")


def download_video(media_url: str, output_path: Path, timeout: float = 60.0) -> int:
    request = Request(
        url=media_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(f"{output_path.suffix}.part")
    with urlopen(request, timeout=timeout) as response, open(temp_path, "wb") as file:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            file.write(chunk)
    temp_path.replace(output_path)
    return output_path.stat().st_size
