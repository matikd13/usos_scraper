#!/usr/bin/env python3
"""
Scrape USOS timetable.html and generate a readable HTML schedule (fix13-style).
Usage: python scrape_timetable.py [timetable.html] [--output readable.html]
Requires: beautifulsoup4 (install with: uv add beautifulsoup4  or  pip install beautifulsoup4)
"""

import re
import html
import json
import argparse
from pathlib import Path

from bs4 import BeautifulSoup


# Default palette for subject colors (when metaData is auto-generated)
SUBJECT_COLORS = [
    "#e3f2fd", "#ffe0b2", "#c8e6c9", "#fff9c4", "#e1bee7",
    "#b2dfdb", "#f0f4c3", "#b3e5fc", "#d1c4e9", "#ffcdd2",
    "#f8bbd0", "#cfd8dc",
]


def grid_time_to_str(g: str) -> str:
    """Convert grid token like 'g0800' or 'g0945' to '08:00' or '09:45'."""
    m = re.match(r"g(\d{4})", g.strip())
    if not m:
        return ""
    hh, mm = m.group(1)[:2], m.group(1)[2:]
    return f"{hh}:{mm}"


def parse_style_times(style: str) -> tuple[str, str]:
    """Extract start and end time from timetable-entry style."""
    start_match = re.search(r"grid-row-start:\s*(g\d{4})", style or "")
    end_match = re.search(r"grid-row-end:\s*(g\d{4})", style or "")
    start = grid_time_to_str(start_match.group(1)) if start_match else ""
    end = grid_time_to_str(end_match.group(1)) if end_match else ""
    return start, end


def parse_info_slot(info_text: str) -> tuple[str, str, str]:
    """
    Parse div[slot=info] e.g. "CWL, gr.&nbsp;1 (012, bud. B9)" or "W, gr.&nbsp;1 (on-line, bud. A0)".
    Returns (type_abbrev, group, room_string).
    """
    if not info_text:
        return "", "", ""
    # Normalize &nbsp; and strip
    text = info_text.replace("\xa0", " ").strip()
    # Type: first part before "gr." (e.g. "CWL" or "W")
    gr_match = re.search(r"\bgr\.\s*(\d+)", text, re.IGNORECASE)
    group = gr_match.group(1) if gr_match else ""
    # Type is everything before "gr."
    type_part = text[: gr_match.start()].strip().rstrip(",").strip() if gr_match else text.split(",")[0].strip()
    # Room: content in parentheses (e.g. "012, bud. B9" or "on-line, bud. A0")
    room_match = re.search(r"\(\s*([^)]+)\s*\)", text)
    room = room_match.group(1).strip() if room_match else ""
    return type_part, group, room


def extract_lecturers(dialog_person_slot) -> str:
    """Extract lecturer names from dialog-person div (text of links, comma-separated)."""
    if not dialog_person_slot:
        return ""
    links = dialog_person_slot.find_all("a")
    names = [a.get_text(strip=True).rstrip(",") for a in links if a.get_text(strip=True)]
    return ", ".join(names) if names else ""


def scrape_timetable(html_path: Path) -> list[dict]:
    """Parse USOS timetable HTML and return list of events as dicts."""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    timetable = soup.find("usos-timetable") or soup
    day_blocks = timetable.find_all("timetable-day", recursive=True)
    day_names = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek"]
    events = []

    for i, td in enumerate(day_blocks):
        parent = td.parent
        day_name = day_names[i] if i < len(day_names) else f"Day {i+1}"
        if parent:
            h4 = parent.find("h4")
            if h4:
                day_name = h4.get_text(strip=True)

        for entry in td.find_all("timetable-entry"):
            style = entry.get("style") or ""
            start, end = parse_style_times(style)
            if not start or not end:
                time_span = entry.find("span", {"slot": "time"})
                dialog_ev = entry.find("span", {"slot": "dialog-event"})
                if time_span:
                    start = time_span.get_text(strip=True)
                if dialog_ev:
                    text = dialog_ev.get_text(strip=True)
                    m = re.search(r"(\d{1,2}:\d{2})\s*[—\-]\s*(\d{1,2}:\d{2})", text)
                    if m:
                        start, end = m.group(1), m.group(2)
                        if len(start) == 4:
                            start = "0" + start
                        if len(end) == 4:
                            end = "0" + end
            subject = (entry.get("name") or "").strip()
            info_div = entry.find("div", {"slot": "info"})
            info_text = info_div.get_text() if info_div else ""
            type_abbrev, group, room = parse_info_slot(info_text)

            events.append({
                "day": day_name,
                "start": start,
                "end": end,
                "subject": subject,
                "type": type_abbrev,
                "group": group,
                "room": room,
            })

    return events


def build_meta_data(events: list[dict]) -> dict:
    """Build metaData object for each subject (short name, color)."""
    subjects = list({e["subject"] for e in events if e["subject"]})
    meta = {}
    for i, subj in enumerate(sorted(subjects)):
        short = subj if len(subj) <= 20 else subj[:17] + "..."
        meta[subj] = {
            "ects": "?",
            "status": "?",
            "verify": "?",
            "short": short,
            "color": SUBJECT_COLORS[i % len(SUBJECT_COLORS)],
        }
    return meta


def raw_data_to_js(events: list[dict]) -> str:
    """Format events as JavaScript array of objects for rawData."""
    lines = []
    for e in events:
        line = (
            f'            {{ day: "{e["day"]}", start: "{e["start"]}", end: "{e["end"]}", '
            f'subject: "{e["subject"].replace(chr(34), chr(92)+chr(34))}", '
            f'type: "{e["type"]}", group: "{e["group"]}", room: "{e["room"].replace(chr(34), chr(92)+chr(34))}" }},'
        )
        lines.append(line)
    return "\n".join(lines) if lines else "            // no events"


def meta_data_to_js(meta: dict) -> str:
    """Format metaData as JavaScript object."""
    lines = []
    for subj, data in sorted(meta.items()):
        esc = subj.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(
            f'            "{esc}": {{ ects: {json.dumps(data["ects"])}, status: {json.dumps(data["status"])}, '
            f'verify: {json.dumps(data["verify"])}, short: {json.dumps(data["short"])}, color: {json.dumps(data["color"])} }},'
        )
    return "\n".join(lines) if lines else "            // no meta"


def generate_readable_html(
    events: list[dict],
    template_path: Path,
    output_path: Path,
    *,
    inject_meta: bool = True,
    plan_title: str = "Plan Zajęć",
) -> None:
    """Generate readable HTML from fix13 template with scraped rawData (and optional metaData)."""
    template = template_path.read_text(encoding="utf-8")

    template = template.replace("__PLAN_TITLE__", html.escape(plan_title))

    raw_js = raw_data_to_js(events)
    raw_pattern = re.compile(
        r"const rawData = \[\s*[\s\S]*?\n\s*\];",
        re.MULTILINE,
    )
    template = raw_pattern.sub(lambda _: f"const rawData = [\n{raw_js}\n        ];", template, count=1)

    if inject_meta:
        meta = build_meta_data(events)
        meta_js = meta_data_to_js(meta)
        meta_pattern = re.compile(
            r"const metaData = \{\s*[\s\S]*?\n\s*\};",
            re.MULTILINE,
        )
        template = meta_pattern.sub(
            lambda _: f"const metaData = {{\n{meta_js}\n        }};",
            template,
            count=1,
        )

    output_path.write_text(template, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape USOS timetable and generate readable HTML")
    parser.add_argument(
        "input",
        nargs="?",
        default="timetable.html",
        help="Path to timetable.html (default: timetable.html)",
    )
    parser.add_argument(
        "-o", "--output",
        default="readable_timetable.html",
        help="Output HTML path (default: readable_timetable.html)",
    )
    parser.add_argument(
        "--template",
        default="template.html",
        help="Template HTML path (default: template.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also write scraped events to a JSON file (readable_timetable.json)",
    )
    parser.add_argument(
        "--title",
        default="Plan Zajęć",
        help="Page title for the generated HTML (default: Plan Zajęć)",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    input_path = base / args.input
    template_path = base / args.template
    output_path = base / args.output

    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")
    if not template_path.is_file():
        raise SystemExit(f"Template file not found: {template_path}")

    events = scrape_timetable(input_path)
    print(f"Scraped {len(events)} events from {input_path}")

    if args.json:
        json_path = output_path.with_suffix(".json")
        json_path.write_text(
            json.dumps(events, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {json_path}")

    generate_readable_html(events, template_path, output_path, plan_title=args.title)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
