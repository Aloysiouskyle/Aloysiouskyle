#!/usr/bin/env python3
"""Generate self-hosted SVG cards for a GitHub profile.

Sources: GitHub's public REST API. The activity graph represents *public
events*, not GitHub's contribution calendar. GitHub's events API is limited
to recent activity and may lag. No third-party stats-image service needed.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

USER = os.environ.get("PROFILE_USERNAME", "Aloysiouskyle")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = Path("assets")
BG, PANEL, TEXT, MUTED, ACCENT, GRID = "#0d1717", "#142320", "#e9f8f0", "#9bb8af", "#63e6be", "#2b4740"


def api(path):
    url = "https://api.github.com" + path
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats-generator"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=25) as response:
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError("GitHub API request failed for " + path + ": " + str(exc)) from exc


def elt(x, y, text, size=16, color=TEXT, weight="normal", anchor="start"):
    return '<text x="{}" y="{}" font-size="{}" font-family="Arial,Helvetica,sans-serif" fill="{}" font-weight="{}" text-anchor="{}">{}</text>'.format(
        x, y, size, color, weight, anchor, escape(str(text))
    )


def svg(width, height, inner):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" '
            'viewBox="0 0 {0} {1}" role="img"><rect width="{0}" height="{1}" '
            'rx="18" fill="{2}"/>'.format(width, height, BG) + inner + '</svg>\n')


def save(name, value):
    ET.fromstring(value)  # fail rather than commit broken XML
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(value, encoding="utf-8")


def get_repos():
    repos = []
    for page in range(1, 11):
        chunk = api("/users/{}/repos?type=owner&sort=updated&per_page=100&page={}".format(USER, page))
        if not isinstance(chunk, list):
            raise RuntimeError("Unexpected repository API response")
        repos += [r for r in chunk if not r.get("fork") and not r.get("private")]
        if len(chunk) < 100:
            break
    return repos


def get_events():
    events = []
    for page in range(1, 4):
        chunk = api("/users/{}/events/public?per_page=100&page={}".format(USER, page))
        if not isinstance(chunk, list):
            raise RuntimeError("Unexpected events API response")
        events += chunk
        if len(chunk) < 100:
            break
    return events


def make_summary(repos, updated):
    lang = Counter(r.get("language") for r in repos if r.get("language"))
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    s = elt(30, 43, "PUBLIC REPOSITORY SNAPSHOT", 18, ACCENT, "bold")
    s += elt(30, 75, "A view of public repositories, not an estimate of coding ability.", 13, MUTED)
    cards = [("Repositories", len(repos)), ("Stars received", stars), ("Forks", forks)]
    for i, (label, value) in enumerate(cards):
        x = 30 + 200 * i
        s += '<rect x="{}" y="99" width="184" height="100" rx="12" fill="{}"/>'.format(x, PANEL)
        s += elt(x + 17, 142, value, 29, TEXT, "bold")
        s += elt(x + 17, 175, label, 13, MUTED)
    s += elt(30, 238, "Main repository languages", 16, TEXT, "bold")
    if lang:
        for i, (language, count) in enumerate(lang.most_common(4)):
            y = 269 + i * 31
            s += elt(30, y, language, 13, TEXT)
            s += '<rect x="190" y="{}" width="385" height="11" rx="5" fill="{}"/>'.format(y - 10, GRID)
            s += '<rect x="190" y="{}" width="{}" height="11" rx="5" fill="{}"/>'.format(
                y - 10, round(385 * count / len(repos)), ACCENT)
            s += elt(600, y, str(count), 12, MUTED, anchor="end")
    else:
        s += elt(30, 280, "No primary languages reported for public repositories.", 13, MUTED)
    s += elt(30, 426, "Updated " + updated + " UTC  |  Source: GitHub public API", 12, MUTED)
    save("github-summary.svg", svg(640, 451, s))


def make_activity(events, updated, now):
    # Recent public events are NOT identical to GitHub contribution squares.
    # Display a 12-week window and label the data accurately.
    today = now.date()
    start = today - timedelta(days=83)
    counts = Counter()
    for ev in events:
        stamp = ev.get("created_at", "")
        if not stamp:
            continue
        try:
            day = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if start <= day <= today:
            counts[day] += 1
    s = elt(30, 44, "PUBLIC ACTIVITY · LAST 12 WEEKS", 18, ACCENT, "bold")
    s += elt(30, 72, "Public GitHub events (pushes, issues, PRs and more). Not contribution counts.", 13, MUTED)
    base_x, base_y, size, gap = 35, 111, 17, 9
    palette = ["#263b36", "#22574d", "#268d76", "#40bb98", ACCENT]
    for i in range(84):
        day = start + timedelta(days=i)
        count = counts[day]
        shade = palette[0 if count == 0 else min(4, 1 + (count >= 2) + (count >= 4) + (count >= 8))]
        x, y = base_x + (i // 7) * (size + gap), base_y + (i % 7) * (size + gap)
        s += '<rect x="{}" y="{}" width="{}" height="{}" rx="3" fill="{}"><title>{}: {} public events</title></rect>'.format(
            x, y, size, size, shade, day.isoformat(), count)
    total = sum(counts.values())
    s += elt(385, 144, str(total), 33, TEXT, "bold")
    s += elt(385, 169, "recent public events", 13, MUTED)
    s += elt(385, 210, "Window: " + start.isoformat(), 13, MUTED)
    s += elt(385, 231, "through " + today.isoformat(), 13, MUTED)
    s += elt(35, 319, "GitHub's public events feed is limited and can be delayed.", 12, MUTED)
    s += elt(35, 342, "Updated " + updated + " UTC  |  Source: GitHub public events API", 12, MUTED)
    save("github-activity.svg", svg(640, 370, s))


def self_test():
    test_now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    repos = [
        {"fork": False, "private": False, "language": "Python", "stargazers_count": 2, "forks_count": 0},
        {"fork": False, "private": False, "language": "JavaScript", "stargazers_count": 1, "forks_count": 1},
    ]
    events = [{"created_at": "2026-11-19T12:00:00Z"}]
    make_summary(repos, "2026-11-20")
    make_activity(events, "2026-11-20", test_now)
    assert all((OUT / name).read_text().startswith("<svg") for name in ("github-summary.svg", "github-activity.svg"))
    print("SVG generator self-test passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        now = datetime.now(timezone.utc)
        updated = now.strftime("%Y-%m-%d %H:%M")
        make_summary(get_repos(), updated)
        make_activity(get_events(), updated, now)
        print("Generated public statistics for", USER)
