"""
prizepicks.py — Fetch NBA player prop lines from PrizePicks (free, no key needed).
Returns props in same format as parse_props() from odds.py.
"""

import json, re, time
import urllib.request

from utils import calc_ev, implied


PRIZEPICKS_URL = "https://api.prizepicks.com/projections?league_id=7&per_page=250&single_stat=true"

STAT_MAP = {
    "Points":        "Points",
    "Rebounds":      "Rebounds",
    "Assists":       "Assists",
    "Pts+Reb+Ast":   None,  # skip combo stats
    "Pts+Ast":       None,
    "Pts+Reb":       None,
    "Reb+Ast":       None,
}


def fetch_prizepicks_props(home_teams=None, away_teams=None):
    """
    Fetch PrizePicks NBA props for today.
    Optionally filter to teams playing today.
    Returns list of prop dicts: {player, stat, line, dir, odds, ev}
    """
    try:
        req = urllib.request.Request(
            PRIZEPICKS_URL,
            headers={
                "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept":          "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer":         "https://app.prizepicks.com/",
                "Origin":          "https://app.prizepicks.com",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        # Build player lookup from included
        player_map = {}
        for item in data.get("included", []):
            if item.get("type") == "new_player":
                pid  = item["id"]
                name = item.get("attributes", {}).get("display_name", "")
                team = item.get("attributes", {}).get("team", "")
                player_map[pid] = {"name": name, "team": team}

        props = []
        seen  = set()

        for proj in data.get("data", []):
            attrs = proj.get("attributes", {})
            stat  = attrs.get("stat_type", "")

            # Only keep single stats we care about
            if stat not in ("Points", "Rebounds", "Assists"):
                continue

            line = attrs.get("line_score")
            if line is None:
                continue

            # Get player info
            pid    = proj.get("relationships", {}).get("new_player", {}).get("data", {}).get("id", "")
            player = player_map.get(pid, {})
            name   = player.get("name", "")
            team   = player.get("team", "")

            if not name:
                continue

            # Deduplicate
            key = f"{name}|{stat}|{line}"
            if key in seen:
                continue
            seen.add(key)

            # PrizePicks uses fixed -120 juice equivalent
            # We'll use -115 as a reasonable standard price
            over_odds  = -115
            under_odds = -115

            # Calculate EV using no-vig 50/50 as baseline
            # Real edge comes from model analysis, not raw EV here
            eo = calc_ev(0.5, over_odds)
            eu = calc_ev(0.5, under_odds)

            props.append({
                "player":    name,
                "stat":      stat,
                "line":      float(line),
                "dir":       "OVER",   # model will decide direction
                "odds":      over_odds,
                "ev":        eo,
                "team":      team,
                "OVER":      over_odds,
                "UNDER":     under_odds,
            })

        print(f"    PrizePicks: {len(props)} NBA props fetched")
        return props

    except urllib.error.HTTPError as e:
        print(f"    PrizePicks HTTP {e.code}: {e}")
        return []
    except Exception as e:
        print(f"    PrizePicks error: {e}")
        return []


def filter_props_for_game(all_props, home_team, away_team, home_abbr=None, away_abbr=None):
    """
    Filter props to players on the two teams in this game.
    Deduplicates by player+stat, keeping the median line.
    """
    # PrizePicks uses abbreviations — match directly if provided
    valid_abbrs = set()
    if home_abbr:
        valid_abbrs.add(home_abbr.upper())
    if away_abbr:
        valid_abbrs.add(away_abbr.upper())

    # Also try token matching on full names as fallback
    def normalize(s):
        return s.lower().replace(" ", "").replace(".", "")

    def tokens(name):
        n = normalize(name)
        parts = name.lower().split()
        return [n[:4]] + [p for p in parts if len(p) > 3]

    h_tokens = tokens(home_team)
    a_tokens = tokens(away_team)

    # Group by player+stat, pick median line
    by_player_stat = {}
    for p in all_props:
        team = p.get("team", "").upper()

        # Match by abbreviation first (most reliable)
        if valid_abbrs:
            if team not in valid_abbrs:
                continue
        else:
            # Fallback to token matching
            team_n = normalize(team)
            if not any(t in team_n or team_n in t for t in h_tokens + a_tokens):
                continue

        key = f"{p['player']}|{p['stat']}"
        if key not in by_player_stat:
            by_player_stat[key] = []
        by_player_stat[key].append(p)

    filtered = []
    for key, candidates in by_player_stat.items():
        sorted_c = sorted(candidates, key=lambda x: x["line"])
        filtered.append(sorted_c[len(sorted_c)//2])

    # Sort by line value descending — higher lines = more important players
    filtered.sort(key=lambda x: -x["line"])
    return filtered[:6]