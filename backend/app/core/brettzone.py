"""Helpers for discovering and downloading BrettZone fight videos."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
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


@dataclass(slots=True)
class BrettzoneEntry:
    """A downloadable BrettZone recording entry."""

    media_url: str
    fight_url: str
    camera: str
    category: str


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


def list_downloadables(fight_url: str, timeout: float = 20.0) -> list[BrettzoneEntry]:
    html = fetch_html(fight_url, timeout=timeout)
    recordings = _extract_recordings_from_html(html)
    entries: list[BrettzoneEntry] = []

    for recording in recordings:
        media_url = recording.get("proxy720") or recording.get("proxy360") or recording.get("s3path")
        if not isinstance(media_url, str) or not media_url:
            continue
        camera = str(recording.get("camera") or "")
        if "program feed" in camera.lower():
            continue
        entries.append(
            BrettzoneEntry(
                media_url=media_url,
                fight_url=fight_url,
                camera=camera or "unknown_camera",
                category=str(recording.get("category") or "unknown_category"),
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
