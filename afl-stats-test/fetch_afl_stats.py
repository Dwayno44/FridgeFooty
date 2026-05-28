"""
AFL 2026 Player Statistics — Source Test
=========================================
Tests multiple public data sources for 2026 AFL player statistics.
Run with:   python3 fetch_afl_stats.py [--round N] [--season YYYY]

Sources tested (in priority order):
  1. AFL Tables  (afltables.com)      — free scrape, needs cloudscraper
  2. API-Sports AFL API               — free tier 100 req/day, needs API key
  3. Squiggle API                     — free, game scores only (no player stats)
  4. GitHub CSV mirror                — static dataset, only current to ~2024

Environment variables:
  AFL_API_KEY   — API-Sports key (get free at https://api-sports.io)
"""

import sys
import os
import csv
import json
import io
import argparse
import urllib.request
import urllib.error
from datetime import datetime

SEASON   = datetime.now().year
TIMEOUT  = 15
UA       = "FridgeFooty-StatsTest/1.0 (github.com/dwayno44/fridgefooty)"

AFL_API_KEY  = os.environ.get("AFL_API_KEY", "")
AFL_API_BASE = "https://v1.afl.api-sports.io"


# ── Shared HTTP ───────────────────────────────────────────────────────────────

def http_get(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


# ── Source 1: AFL Tables (afltables.com) ─────────────────────────────────────
# AFL Tables is protected by Cloudflare; plain requests return 403.
# cloudscraper bypasses the JS challenge and is the standard approach.
# URL pattern: https://afltables.com/afl/stats/{year}.html
# Player profile: https://afltables.com/afl/stats/players/{initial}/{Name}.html
# Team season:    https://afltables.com/afl/teams/{team}/2026.html

def fetch_afltables_season(season: int = SEASON) -> list[dict]:
    """Returns player game log rows for the season index page."""
    try:
        import cloudscraper  # pip install cloudscraper
    except ImportError:
        raise ImportError("Install cloudscraper:  pip install cloudscraper")

    url = f"https://afltables.com/afl/stats/{season}.html"
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    resp = scraper.get(url, timeout=TIMEOUT)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")

    players = []
    table = soup.find("table")
    if not table:
        return players

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    for row in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if cells and len(cells) == len(headers):
            players.append(dict(zip(headers, cells)))

    return players


def fetch_afltables_player(player_name: str, season: int = SEASON) -> list[dict]:
    """
    Returns per-game rows for a specific player from AFL Tables.
    player_name: e.g. "Marcus Bontempelli"  (exact match as on afltables.com)
    """
    try:
        import cloudscraper
    except ImportError:
        raise ImportError("Install cloudscraper:  pip install cloudscraper")

    initial = player_name.split()[1][0].upper()
    slug    = player_name.replace(" ", "_")
    url     = f"https://afltables.com/afl/stats/players/{initial}/{slug}.html"

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    resp = scraper.get(url, timeout=TIMEOUT)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")

    rows = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Season" not in headers and "Year" not in headers:
            continue
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if cells:
                r = dict(zip(headers, cells))
                if str(season) in r.get("Season", r.get("Year", "")):
                    rows.append(r)
    return rows


# ── Source 2: API-Sports AFL API ─────────────────────────────────────────────
# Free tier: 100 requests/day. Register at https://api-sports.io
# Set your key: export AFL_API_KEY=your_key_here
#
# Key endpoints:
#   GET /games?season={year}&league=1          → list of games (id, teams, scores)
#   GET /games/statistics/players?id={game_id} → per-player stats for a game
#   GET /players?season={year}&team={team_id}  → player roster + metadata
#
# Player stats fields returned per game:
#   player_id, player_name, position, team_id,
#   kicks, handballs, marks, disposals, goals, behinds,
#   tackles, hit_outs, inside_50s, rebound_50s, clearances,
#   contested_possessions, uncontested_possessions,
#   free_kicks_for, free_kicks_against,
#   time_on_ground, fantasy_points

def _api_sports_get(path: str) -> dict:
    if not AFL_API_KEY:
        raise ValueError("AFL_API_KEY not set — get a free key at https://api-sports.io")
    url = f"{AFL_API_BASE}{path}"
    raw = http_get(url, headers={"x-apisports-key": AFL_API_KEY})
    return json.loads(raw)


def fetch_api_sports_games(season: int = SEASON, round_num: int | None = None) -> list[dict]:
    path = f"/games?season={season}&league=1"
    if round_num is not None:
        path += f"&round={round_num}"
    data = _api_sports_get(path)
    return data.get("response", [])


def fetch_api_sports_player_stats(game_id: int) -> list[dict]:
    """Returns player stats for a completed game by game ID."""
    data = _api_sports_get(f"/games/statistics/players?id={game_id}")
    return data.get("response", [])


def fetch_api_sports_players_for_team(team_id: int, season: int = SEASON) -> list[dict]:
    """Returns player roster and biographical data for a team."""
    data = _api_sports_get(f"/players?season={season}&team={team_id}")
    return data.get("response", [])


# ── Source 3: Squiggle API ────────────────────────────────────────────────────
# Free, no key required. Game scores + model tips only.
# No individual player stats — scores/tips only.
# Must set a descriptive User-Agent with contact info (see ToS).
# Endpoints:
#   https://api.squiggle.com.au/?q=games;year={year}
#   https://api.squiggle.com.au/?q=games;year={year};round={n}
#   https://api.squiggle.com.au/?q=tips;year={year}
#   https://api.squiggle.com.au/?q=standings;year={year};round={n}

def fetch_squiggle_games(season: int = SEASON, round_num: int | None = None) -> list[dict]:
    path = f"?q=games;year={season}"
    if round_num is not None:
        path += f";round={round_num}"
    url = f"https://api.squiggle.com.au/{path}"
    raw = http_get(url, headers={"User-Agent": f"{UA} ; smithdk44@gmail.com"})
    return json.loads(raw).get("games", [])


def fetch_squiggle_tips(season: int = SEASON, round_num: int | None = None) -> list[dict]:
    path = f"?q=tips;year={season}"
    if round_num is not None:
        path += f";round={round_num}"
    url = f"https://api.squiggle.com.au/{path}"
    raw = http_get(url, headers={"User-Agent": f"{UA} ; smithdk44@gmail.com"})
    return json.loads(raw).get("tips", [])


# ── Source 4: GitHub CSV mirror (akareen/AFL-Data-Analysis) ──────────────────
# Static dataset updated by contributor — currently covers up to 2024.
# Player files: data/players/{lastname}_{firstname}_{ddmmyyyy}_performance_details.csv
# Columns: team, year, games_played, opponent, round, result, jersey_num, kicks,
#          marks, handballs, disposals, goals, behinds, hit_outs, tackles,
#          rebound_50s, inside_50s, clearances, clangers, free_kicks_for,
#          free_kicks_against, brownlow_votes, contested_possessions,
#          uncontested_possessions, contested_marks, marks_inside_50,
#          one_percenters, bounces, goal_assist, percentage_of_game_played

GITHUB_BASE = (
    "https://raw.githubusercontent.com/akareen/AFL-Data-Analysis/main/data/players"
)

# Known player slugs: {last}_{first}_{ddmmyyyy}
# Only slugs confirmed to exist in the repo are listed here.
# To add more players use: afltables.com player URL to find DOB, then
# format slug as {lastname}_{firstname}_{ddmmyyyy}.
PLAYER_SLUGS: dict[str, str] = {
    "Marcus Bontempelli":  "bontempelli_marcus_24111995",  # up to 2024
    "Patrick Dangerfield": "dangerfield_patrick_05041990",  # up to 2025 R4
    "Scott Pendlebury":    "pendlebury_scott_07011988",     # up to 2025 R3
}


def fetch_github_player_stats(slug: str, season: int | None = None) -> list[dict]:
    """Fetch per-game stats for a player from the GitHub CSV mirror."""
    import urllib.request
    url = f"{GITHUB_BASE}/{slug}_performance_details.csv"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    if season is not None:
        rows = [r for r in rows if r.get("year", "").strip() == str(season)]
    return rows


# ── Stats field reference ─────────────────────────────────────────────────────

STAT_FIELDS = [
    ("kicks",                   "Total kicks"),
    ("handballs",               "Total handballs"),
    ("disposals",               "Kicks + handballs"),
    ("marks",                   "Total marks"),
    ("goals",                   "Goals scored"),
    ("behinds",                 "Behinds scored"),
    ("hit_outs",                "Hit-outs (rucks)"),
    ("tackles",                 "Tackles"),
    ("rebound_50s",             "Rebound 50s"),
    ("inside_50s",              "Inside 50s"),
    ("clearances",              "Clearances"),
    ("contested_possessions",   "Contested possessions"),
    ("uncontested_possessions", "Uncontested possessions"),
    ("free_kicks_for",          "Free kicks for"),
    ("free_kicks_against",      "Free kicks against"),
    ("contested_marks",         "Contested marks"),
    ("marks_inside_50",         "Marks inside 50"),
    ("brownlow_votes",          "Brownlow votes"),
    ("one_percenters",          "One-percenters"),
    ("goal_assist",             "Goal assists"),
    ("time_on_ground",          "Time on ground (%)"),
    ("fantasy_points",          "AFL Fantasy points"),
]


# ── Test runner ───────────────────────────────────────────────────────────────

def banner(title: str) -> None:
    print(f"\n{'─' * 64}")
    print(f"  {title}")
    print("─" * 64)


def check(label: str, fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
        return result, None
    except Exception as e:
        return None, str(e)


def run(season: int = SEASON, round_num: int | None = None) -> None:
    results: list[tuple[str, str]] = []

    # ── AFL Tables ──────────────────────────────────────────────────────
    banner(f"Source 1 — AFL Tables  (afltables.com)  season={season}")
    print("  Method : cloudscraper (Cloudflare bypass) + BeautifulSoup HTML parse")
    print(f"  URL    : https://afltables.com/afl/stats/{season}.html")
    players, err = check(None, fetch_afltables_season, season)
    if err:
        results.append(("AFL Tables", f"FAIL — {err}"))
        print(f"  Result : {results[-1][1]}")
    else:
        results.append(("AFL Tables", f"OK — {len(players)} player rows"))
        print(f"  Result : {results[-1][1]}")
        for p in (players or [])[:3]:
            print(f"  sample : {dict(list(p.items())[:8])}")

    # ── API-Sports ─────────────────────────────────────────────────────
    banner(f"Source 2 — API-Sports AFL API  season={season}")
    print("  Method : REST JSON, header x-apisports-key")
    print(f"  URL    : {AFL_API_BASE}/games?season={season}&league=1")
    print(f"  Key    : {'SET ✓' if AFL_API_KEY else 'NOT SET — export AFL_API_KEY=<your_key>'}")
    if AFL_API_KEY:
        games, err = check(None, fetch_api_sports_games, season, round_num)
        if err:
            results.append(("API-Sports", f"FAIL — {err}"))
            print(f"  Result : {results[-1][1]}")
        else:
            results.append(("API-Sports", f"OK — {len(games)} game(s)"))
            print(f"  Result : {results[-1][1]}")
            for g in (games or [])[:2]:
                home = g.get("teams", {}).get("home", {}).get("name", "?")
                away = g.get("teams", {}).get("away", {}).get("name", "?")
                hs   = g.get("scores", {}).get("home", {}).get("score", "?")
                as_  = g.get("scores", {}).get("away", {}).get("score", "?")
                rnd  = g.get("league", {}).get("round", "?")
                gid  = g.get("id", "?")
                print(f"  game   : id={gid} r={rnd}  {home} {hs} – {as_} {away}")
            # If games exist, fetch player stats for the first completed game
            completed = [g for g in (games or []) if g.get("status", {}).get("short") == "FT"]
            if completed:
                gid = completed[0]["id"]
                print(f"\n  Fetching player stats for game id={gid} ...")
                pstats, perr = check(None, fetch_api_sports_player_stats, gid)
                if perr:
                    print(f"  player stats: FAIL — {perr}")
                else:
                    print(f"  player stats: {len(pstats)} player(s)")
                    for p in (pstats or [])[:2]:
                        name = p.get("player", {}).get("name", "?")
                        s    = p.get("statistics", [{}])[0]
                        print(f"    {name}: kicks={s.get('kicks','?')} "
                              f"handballs={s.get('handballs','?')} "
                              f"marks={s.get('marks','?')} "
                              f"goals={s.get('goals','?')} "
                              f"tackles={s.get('tackles','?')}")
    else:
        results.append(("API-Sports", "SKIP — no AFL_API_KEY"))
        print(f"  Result : {results[-1][1]}")
        print("  Sign up free: https://api-sports.io  (100 req/day free tier)")

    # ── Squiggle ────────────────────────────────────────────────────────
    banner(f"Source 3 — Squiggle API  season={season}")
    print("  Method : REST JSON, no auth required")
    print("  Note   : Game scores + model tips only — no individual player stats")
    r_label = f"round={round_num}" if round_num else "all rounds"
    print(f"  URL    : https://api.squiggle.com.au/?q=games;year={season}")
    games, err = check(None, fetch_squiggle_games, season, round_num)
    if err:
        results.append(("Squiggle", f"FAIL — {err}"))
        print(f"  Result : {results[-1][1]}")
    else:
        results.append(("Squiggle", f"OK — {len(games)} game(s) ({r_label})"))
        print(f"  Result : {results[-1][1]}")
        for g in (games or [])[:3]:
            hteam = g.get("hteam", "?")
            ateam = g.get("ateam", "?")
            hs    = g.get("hscore", "–")
            as_   = g.get("ascore", "–")
            rnd   = g.get("round", "?")
            print(f"  R{rnd:>2}  {hteam} {hs} – {as_} {ateam}")

    # ── GitHub CSV mirror ────────────────────────────────────────────────
    banner(f"Source 4 — GitHub CSV mirror  (akareen/AFL-Data-Analysis)")
    print("  Method : raw.githubusercontent.com download")
    print("  Note   : Static dataset — Bontempelli up to 2024, others patchy 2025")
    for name, slug in PLAYER_SLUGS.items():
        rows, err = check(None, fetch_github_player_stats, slug, season)
        if err:
            print(f"  {name:<28} FAIL — {err}")
        elif rows:
            rnd_list = [r.get("round", "?") for r in rows[:4]]
            print(f"  {name:<28} {len(rows)} game(s) in {season}  rounds={rnd_list}")
        else:
            latest_year = None
            all_rows, _ = check(None, fetch_github_player_stats, slug, None)
            if all_rows:
                years = sorted({r.get("year","") for r in all_rows if r.get("year")})
                latest_year = years[-1] if years else None
            print(f"  {name:<28} no {season} data  (latest: {latest_year or '?'})")
    results.append(("GitHub CSV", "OK — accessible, 2024 data only"))

    # ── Summary ─────────────────────────────────────────────────────────
    banner("Summary")
    for src, status in results:
        icon = "✓" if status.startswith("OK") else ("○" if status.startswith("SKIP") else "✗")
        print(f"  {icon}  {src:<20}  {status}")

    print()
    print("  Full player stat schema (AFL Tables + API-Sports + GitHub CSV):")
    col1_w = max(len(f) for f, _ in STAT_FIELDS) + 2
    for field, desc in STAT_FIELDS:
        print(f"    {field:<{col1_w}} {desc}")
    print()
    print("  Quick-start:")
    print("    pip install cloudscraper beautifulsoup4 lxml")
    print("    python3 fetch_afl_stats.py --round 1 --season 2026")
    print("    AFL_API_KEY=<key> python3 fetch_afl_stats.py --round 1")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AFL 2026 player stats data sources")
    parser.add_argument("--season", type=int, default=SEASON, help="Season year (default: current)")
    parser.add_argument("--round",  type=int, default=None,   dest="round_num",
                        help="Round number (default: all)")
    args = parser.parse_args()
    run(season=args.season, round_num=args.round_num)
