# AFL 2026 Player Stats — Data Sources

Quick reference for the four sources tested by `fetch_afl_stats.py`.

## 1. AFL Tables — `afltables.com`

| Property | Detail |
|---|---|
| Cost | Free |
| Auth | None |
| Player stats depth | 1965 → present |
| Update cadence | Within 24 h of each match |
| Cloudflare bypass | Required (`cloudscraper`) |
| Python lib | `pyAFL` (`pip install pyAFL`) |

**Season index URL**
```
https://afltables.com/afl/stats/{year}.html
```
**Player profile URL**
```
https://afltables.com/afl/stats/players/{Initial}/{First_Last}.html
```

Stat columns available: kicks, handballs, marks, disposals, goals, behinds,
hit_outs, tackles, rebound_50s, inside_50s, clearances, contested_possessions,
uncontested_possessions, contested_marks, marks_inside_50, free_kicks_for,
free_kicks_against, brownlow_votes, one_percenters, bounces, goal_assist,
percentage_of_game_played.

---

## 2. API-Sports AFL API — `v1.afl.api-sports.io`

| Property | Detail |
|---|---|
| Cost | Free tier: 100 req/day; paid plans available |
| Auth | `x-apisports-key` header |
| Register | https://api-sports.io |
| League ID | 1 (AFL Men's) |

**Key endpoints**
```
GET /games?season={year}&league=1             → fixture + scores
GET /games/statistics/players?id={game_id}    → per-player stats (completed games)
GET /players?season={year}&team={team_id}     → roster + bio
```

**Player stats fields per game**
`kicks`, `handballs`, `marks`, `disposals`, `goals`, `behinds`, `tackles`,
`hit_outs`, `inside_50s`, `rebound_50s`, `clearances`, `contested_possessions`,
`uncontested_possessions`, `free_kicks_for`, `free_kicks_against`,
`time_on_ground`, `fantasy_points`

```bash
export AFL_API_KEY=your_key_here
python3 fetch_afl_stats.py --round 1 --season 2026
```

---

## 3. Squiggle API — `api.squiggle.com.au`

| Property | Detail |
|---|---|
| Cost | Free |
| Auth | None (descriptive User-Agent required) |
| Player stats | **None** — game scores + model tips only |

**Endpoints**
```
https://api.squiggle.com.au/?q=games;year=2026
https://api.squiggle.com.au/?q=games;year=2026;round=1
https://api.squiggle.com.au/?q=tips;year=2026
https://api.squiggle.com.au/?q=standings;year=2026;round=10
```

Useful for: fixture data, live scores, 50+ community model predictions.
Not useful for: individual player statistics.

---

## 4. GitHub CSV Mirror — `akareen/AFL-Data-Analysis`

| Property | Detail |
|---|---|
| Cost | Free |
| Auth | None |
| Coverage | Player game logs 1897–2024 (needs 2025/26 update) |
| Format | Per-player CSV files |

**File pattern**
```
https://raw.githubusercontent.com/akareen/AFL-Data-Analysis/main/data/players/
  {lastname}_{firstname}_{ddmmyyyy}_performance_details.csv
```

Columns: `team, year, games_played, opponent, round, result, jersey_num,
kicks, marks, handballs, disposals, goals, behinds, hit_outs, tackles,
rebound_50s, inside_50s, clearances, clangers, free_kicks_for,
free_kicks_against, brownlow_votes, contested_possessions,
uncontested_possessions, contested_marks, marks_inside_50, one_percenters,
bounces, goal_assist, percentage_of_game_played`

**Limitation:** Dataset is community-maintained and currently only includes
data through the 2024 season. Not suitable as a live 2026 data source.

---

## Recommendation for 2026 Live Stats

For a **free** live-stats solution combine:

1. **AFL Tables** (primary) — scrape with `cloudscraper` after each round for full
   historical + 2026 season player stats.
2. **Squiggle API** (fixture/scores) — zero-setup fixture and score feed.
3. **API-Sports** (optional) — structured JSON, 100 req/day free; upgrade if
   higher volume is needed.

For a **paid** solution:
- **Champion Data AFL API** (`docs.api.afl.championdata.com`) — official source,
  commercial contract, includes advanced metrics (metres gained, pressure acts, etc).
