"""
espn.py — ESPN API: schedule, game detail (injuries/totals), box scores.
"""

from datetime import datetime, timedelta

from config import ESPN_BASE
from utils import fetch, safe


def espn_schedule(date_str):
    """Return list of game dicts for a given date (YYYY-MM-DD)."""
    d   = date_str.replace("-", "")
    url = f"{ESPN_BASE}/scoreboard?dates={d}&limit=20"
    try:
        data   = fetch(url, no_cache=True)
        events = data.get("events", [])
        print(f"    ESPN: {len(events)} games on {date_str}")

        # ── Back-to-back detection ─────────────────────────────────────────
        # Fetch yesterday's games and collect which teams played
        try:
            yd_str  = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            yd_d    = yd_str.replace("-", "")
            yd_data = fetch(f"{ESPN_BASE}/scoreboard?dates={yd_d}&limit=20", cache_mins=360)
            yd_teams = set()
            for ev in yd_data.get("events", []):
                try:
                    comp = ev["competitions"][0]
                    for t in comp["competitors"]:
                        yd_teams.add(t["team"]["abbreviation"])
                except:
                    continue
        except:
            yd_teams = set()

        games = []

        for ev in events:
            try:
                comp = ev["competitions"][0]
                stat = comp["status"]["type"]["name"]
                done = stat == "STATUS_FINAL"
                home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
                hs   = int(safe(home.get("score", 0)))
                as_  = int(safe(away.get("score", 0)))

                home_abbr = home["team"]["abbreviation"]
                away_abbr = away["team"]["abbreviation"]

                # Back-to-back flags
                home_b2b = home_abbr in yd_teams
                away_b2b = away_abbr in yd_teams

                def parse_rec(comp):
                    for r in comp.get("records", []):
                        if r.get("type") == "total" or r.get("name", "").lower() == "overall":
                            try:
                                parts = r.get("summary", "0-0").split("-")
                                w = int(parts[0])
                                l = int(parts[1])
                                return {
                                    "wins": w, "losses": l,
                                    "pct": w / (w + l) if w + l else 0.5,
                                    "summary": r.get("summary", "?"),
                                }
                            except:
                                pass
                    return {"wins": 0, "losses": 0, "pct": 0.5, "summary": "?"}

                ts = "TBD"
                try:
                    dt = datetime.strptime(ev["date"], "%Y-%m-%dT%H:%MZ") - timedelta(hours=4)
                    ts = f"{dt.hour % 12 or 12}:{dt.strftime('%M')} {'PM' if dt.hour >= 12 else 'AM'} ET"
                except:
                    pass

                games.append({
                    "espn_id":   ev.get("id", ""),
                    "date":      date_str,
                    "sort_ts":   ev.get("date", ""),
                    "homeAbbr":  home_abbr,
                    "awayAbbr":  away_abbr,
                    "homeTeam":  home["team"]["displayName"],
                    "awayTeam":  away["team"]["displayName"],
                    "homeRec":   parse_rec(home),
                    "awayRec":   parse_rec(away),
                    "homeScore": hs,
                    "awayScore": as_,
                    "totalPts":  hs + as_,
                    "homeWon":   hs > as_ if done else None,
                    "completed": done,
                    "startTime": ts,
                    "home_b2b":  home_b2b,
                    "away_b2b":  away_b2b,
                })

                if home_b2b or away_b2b:
                    b2b_teams = []
                    if home_b2b: b2b_teams.append(home["team"]["displayName"])
                    if away_b2b: b2b_teams.append(away["team"]["displayName"])
                    print(f"    ⚠ B2B: {', '.join(b2b_teams)}")

            except:
                continue

        games.sort(key=lambda g: g["sort_ts"])
        return games

    except Exception as e:
        print(f"    ESPN error: {e}")
        return []


def espn_game_detail(espn_id, home_abbr=None, away_abbr=None):
    """Return injuries list and total line for a single game."""
    url = f"{ESPN_BASE}/summary?event={espn_id}"

    # Keywords that indicate a season-long or already-priced-in injury
    SEASON_LONG_KEYWORDS = {
        "surgery", "season", "acl", "achilles", "torn", "rupture",
        "out for season", "out indefinitely", "out - surgery"
    }

    try:
        data     = fetch(url, cache_mins=30)
        injuries = []

        # Build set of valid team abbrs for this game
        valid_teams = set()
        if home_abbr:
            valid_teams.add(home_abbr.upper())
        if away_abbr:
            valid_teams.add(away_abbr.upper())

        for inj in data.get("injuries", []):
            team = inj.get("team", {}).get("abbreviation", "").upper()

            # Skip if player's team isn't in this game (e.g. traded players)
            if valid_teams and team not in valid_teams:
                continue

            for p in inj.get("injuries", []):
                name   = p.get("athlete", {}).get("displayName", "")
                status = p.get("status", "")
                detail = p.get("details", {}).get("detail", "")

                if not name or not status:
                    continue

                # Skip season-long injuries — already fully priced into the line
                combined = (status + " " + detail).lower()
                if any(kw in combined for kw in SEASON_LONG_KEYWORDS):
                    continue

                injuries.append(
                    f"{team}: {name} {status}{' - ' + detail if detail else ''}"
                )

        total_line = None
        for item in data.get("pickcenter", []):
            tl = item.get("overUnder")
            if tl:
                total_line = float(tl)
                break

        return {"injuries": injuries, "total_line": total_line}

    except:
        return {"injuries": [], "total_line": None}


def espn_box(espn_id):
    """Return player stat dict from box score (used by grading)."""
    url = f"{ESPN_BASE}/summary?event={espn_id}"
    try:
        data    = fetch(url, cache_mins=120)
        players = {}
        for tb in data.get("boxscore", {}).get("players", []):
            for sg in tb.get("statistics", []):
                labels = sg.get("labels", [])
                for ath in sg.get("athletes", []):
                    name = ath["athlete"]["displayName"].lower()
                    players[name] = dict(zip(labels, ath.get("stats", [])))
        return players
    except:
        return {}