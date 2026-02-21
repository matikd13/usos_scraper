#!/usr/bin/env python3
"""
Load urls.py (dict: program -> year -> URL), sort by program and year,
fetch each URL, run scrape_timetable.py, and write readable HTMLs.
Usage: python run_from_urls.py [--urls urls.py] [--out dist]
Requires: requests (pip install requests)
"""

import re
import subprocess
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    raise SystemExit("Install requests: pip install requests")

SCRIPT_DIR = Path(__file__).resolve().parent


def slug(s: str) -> str:
    """Safe filename segment from a label."""
    return re.sub(r"[^\w\-]", "_", s.strip().lower()).strip("_") or "page"


def load_urls_dict(path: Path) -> list[tuple[str, str, str]]:
    """
    Load URLS from a Python module (dict: program -> year -> url).
    Return sorted list of (program, year, url) for stable ordering.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("urls_module", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    urls_map = getattr(mod, "URLS", None)
    if not isinstance(urls_map, dict):
        raise SystemExit(f"{path} must define URLS = {{ program: {{ year: url, ... }}, ... }}")

    entries = []
    for program, years in urls_map.items():
        if not isinstance(years, dict):
            continue
        for year, url in years.items():
            if url and isinstance(url, str):
                entries.append((program, year, url))
    # Sort by program, then year
    entries.sort(key=lambda e: (e[0].lower(), e[1].lower()))
    return entries


def output_filename(program: str, year: str) -> str:
    return f"{slug(program)}_{slug(year)}.html"


def fetch_and_build(url: str, output_path: Path, template_path: Path) -> bool:
    """Download URL to a temp file, run scrape_timetable, write to output_path. Return True on success."""
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "USOS-scraper/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fetch failed: {e}")
        return False

    tmp = SCRIPT_DIR / ".tmp_timetable.html"
    tmp.write_text(r.text, encoding="utf-8")
    try:
        subprocess.run(
            [
                "python",
                str(SCRIPT_DIR / "scrape_timetable.py"),
                str(tmp),
                "--template",
                str(template_path),
                "-o",
                str(output_path),
            ],
            check=True,
            cwd=str(SCRIPT_DIR),
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Scrape failed: {e}")
        return False
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape timetables from urls.py (program -> year -> URL)")
    parser.add_argument("--urls", default="urls.py", help="Path to urls.py (default: urls.py)")
    parser.add_argument("--out", default="dist", help="Output directory for HTML files (default: dist)")
    args = parser.parse_args()

    base = SCRIPT_DIR
    urls_path = base / args.urls
    out_dir = base / args.out
    template_path = base / "template.html"

    if not urls_path.is_file():
        raise SystemExit(f"URLs module not found: {urls_path}")
    if not template_path.is_file():
        raise SystemExit(f"Template not found: {template_path}")

    entries = load_urls_dict(urls_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not entries:
        print("No URLs in urls.py (URLS dict empty or no valid program/year/url entries).")
        (out_dir / "index.html").write_text(
            "<!DOCTYPE html><html><body><p>Add timetable URLs to <code>urls.py</code> URLS and re-run.</p></body></html>",
            encoding="utf-8",
        )
        return
    ok = 0
    for program, year, url in entries:
        name = output_filename(program, year)
        output_path = out_dir / name
        print(f"  {program} / {year} -> {output_path.name}")
        if fetch_and_build(url, output_path, template_path):
            ok += 1
    print(f"Built {ok}/{len(entries)} timetables in {out_dir}")


if __name__ == "__main__":
    main()
