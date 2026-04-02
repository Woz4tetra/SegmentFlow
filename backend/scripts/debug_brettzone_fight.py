"""Debug BrettZone fight parsing using backend helper functions.

Usage examples:
  python scripts/debug_brettzone_fight.py \
    "https://brettzone.nhrl.io/brettZone/fightReviewSync.php?gameID=W-7&tournamentID=nhrl_june25_3lb"

  python scripts/debug_brettzone_fight.py \
    "https://brettzone.nhrl.io/brettZone/tournamentFights.php?tournamentID=nhrl_june25_3lb" \
    --resolve
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from app.core.brettzone import (
    _extract_recordings_from_html,
    _extract_robot_names_from_html,
    _extract_robot_names_from_recording,
    _extract_robot_thumbnails_from_html,
    _extract_robot_thumbnails_from_recording,
    discover_entry_from_url,
    fetch_html,
    list_downloadables,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect what BrettZone parser discovers for a URL.",
    )
    parser.add_argument("url", help="BrettZone fight URL (or page URL with --resolve)")
    parser.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve non-fight pages via discover_entry_from_url first",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Network timeout in seconds (default: 20.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Max downloadables to print (default: 8)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed extraction diagnostics",
    )
    return parser


def _print_summary(entries: list, limit: int) -> None:
    print(f"downloadables_count={len(entries)}")
    if not entries:
        print("No downloadable entries were found.")
        return

    cameras = Counter(entry.camera for entry in entries)
    categories = Counter(entry.category for entry in entries)
    all_robot_names = sorted({name for entry in entries for name in entry.robot_names})
    all_thumbnail_names = sorted({name for entry in entries for name in entry.robot_thumbnails.keys()})

    print("camera_counts=", json.dumps(cameras, indent=2))
    print("category_counts=", json.dumps(categories, indent=2))
    print("robot_names=", json.dumps(all_robot_names, indent=2))
    print("robot_thumbnail_names=", json.dumps(all_thumbnail_names, indent=2))

    for idx, entry in enumerate(entries[:limit], start=1):
        print(f"\n[{idx}] camera={entry.camera!r} category={entry.category!r}")
        print(f"    media_url={entry.media_url}")
        print(f"    fight_url={entry.fight_url}")
        print(f"    robot_names={entry.robot_names}")
        print(f"    robot_thumbnails={entry.robot_thumbnails}")


def _print_verbose_diagnostics(url: str, timeout: float) -> None:
    print("\n=== Verbose Diagnostics ===")
    html = fetch_html(url, timeout=timeout)
    print(f"fetched_html_chars={len(html)}")

    recordings = _extract_recordings_from_html(html)
    print(f"recordings_count={len(recordings)}")
    if recordings:
        key_counter: Counter[str] = Counter()
        for rec in recordings:
            for key in rec.keys():
                key_counter[key] += 1
        print("recording_keys_top20=", json.dumps(dict(key_counter.most_common(20)), indent=2))

        for idx, rec in enumerate(recordings[:3], start=1):
            names = _extract_robot_names_from_recording(rec)
            thumbs = _extract_robot_thumbnails_from_recording(rec, url)
            camera = rec.get("camera")
            media = rec.get("proxy720") or rec.get("proxy360") or rec.get("s3path")
            print(f"recording[{idx}] camera={camera!r} media={media!r}")
            print(f"recording[{idx}] extracted_names={names}")
            print(f"recording[{idx}] extracted_thumbnails={thumbs}")

    html_names = _extract_robot_names_from_html(html)
    html_thumbs = _extract_robot_thumbnails_from_html(html, url)
    print("html_extracted_names=", json.dumps(html_names, indent=2))
    print("html_extracted_thumbnail_names=", json.dumps(sorted(html_thumbs.keys()), indent=2))

    if "fightReviewSync.php" in url:
        single_url = url.replace("fightReviewSync.php", "fightReview.php")
        print(f"sync_fallback_single_url={single_url}")
        single_html = fetch_html(single_url, timeout=timeout)
        print(f"single_html_chars={len(single_html)}")
        single_names = _extract_robot_names_from_html(single_html)
        single_thumbs = _extract_robot_thumbnails_from_html(single_html, single_url)
        print("single_html_extracted_names=", json.dumps(single_names, indent=2))
        print(
            "single_html_extracted_thumbnail_names=",
            json.dumps(sorted(single_thumbs.keys()), indent=2),
        )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        target_url = args.url
        if args.resolve:
            resolved = discover_entry_from_url(args.url, timeout=args.timeout)
            target_url = resolved.fight_url
            print("resolved_entry:")
            print(f"  fight_url={resolved.fight_url}")
            print(f"  media_url={resolved.media_url}")
            print(f"  camera={resolved.camera}")
            print(f"  category={resolved.category}")
            print(f"  robot_names={resolved.robot_names}")
            print(f"  robot_thumbnails={resolved.robot_thumbnails}")
            print()

        print(f"parsing_fight_url={target_url}")
        if args.verbose:
            _print_verbose_diagnostics(target_url, args.timeout)
        entries = list_downloadables(target_url, timeout=args.timeout)
        _print_summary(entries, args.limit)
        return 0
    except Exception as exc:  # pragma: no cover - debug script
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
