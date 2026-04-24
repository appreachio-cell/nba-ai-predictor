"""
prop_context.py — Fetch player and team context for prop analysis.
Uses ESPN's free API to get:
- Player season averages (PPG, RPG, APG, MPG)
- Team pace and defensive rating
- Position-based defense (pts/reb/ast allowed by position)
"""

import json, re
import urllib.request

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_CDN  = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba"


def _fetch(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except:
        return {}


def get_team_stats():
    """
    Fetch all NBA team stats — pace, offensive/defensive ratings.
    Returns dict keyed by team abbreviation.
    """
    url = f"{ESPN_BASE}/teams"
    data = _fetch(url)
    teams = {}

    for team in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        t    = team.get("team", {})
        abbr = t.get("abbreviation", "")
        tid  = t.get("id", "")
        if abbr and tid:
            teams[abbr] = {"id": tid, "name": t.get("displayName", "")}

    return teams


def get_team_season_stats(team_id):
    """Fetch a team's season stats including pace and defensive rating."""
    url = f"{ESPN_BASE}/teams/{team_id}/statistics"
    data = _fetch(url)
    stats = {}

    for cat in data.get("results", {}).get("stats", {}).get("categories", []):
        for stat in cat.get("stats", []):
            name = stat.get("name", "")
            val  = stat.get("value")
            if val is not None:
                stats[name] = val

    return stats


def get_player_id(player_name):
    """Search ESPN for a player ID by name."""
    query = player_name.replace(" ", "+")
    url   = f"https://site.api.espn.com/apis/common/v3/search?query={query}&limit=5&type=athlete&sport=basketball&league=nba"
    data  = _fetch(url)

    for item in data.get("items", []):
        if item.get("type") == "athlete":
            name = item.get("displayName", "")
            pid  = item.get("id", "")
            if pid and player_name.lower().split()[-1] in name.lower():
                return pid, name
    return None, None


def get_player_stats(player_id):
    """Fetch a player's season averages."""
    url  = f"{ESPN_BASE}/athletes/{player_id}/statistics"
    data = _fetch(url)
    stats = {}

    for cat in data.get("categories", []):
        labels = cat.get("labels", [])
        values = cat.get("totals", [])
        for label, val in zip(labels, values):
            try:
                stats[label] = float(val)
            except:
                stats[label] = val

    return stats


def build_prop_context(prop_players, home_abbr, away_abbr, team_map):
    """
    Build a context string for a game's props.
    prop_players: list of {player, stat, line} dicts
    Returns a formatted string to inject into the prompt.
    """
    lines = []

    # Get team IDs
    home_id = team_map.get(home_abbr, {}).get("id")
    away_id = team_map.get(away_abbr, {}).get("id")

    # Fetch team defensive stats
    home_def = get_team_season_stats(home_id) if home_id else {}
    away_def = get_team_season_stats(away_id) if away_id else {}

    # Key defensive stats
    def fmt_stat(d, key, decimals=1):
        v = d.get(key)
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    if home_def or away_def:
        lines.append(f"\nTEAM CONTEXT:")
        if home_def:
            lines.append(
                f"  {home_abbr} defense: "
                f"opp PPG allowed={fmt_stat(home_def,'avgPointsAllowed')} "
                f"pace={fmt_stat(home_def,'pace')} "
                f"def_rtg={fmt_stat(home_def,'defensiveRating')}"
            )
        if away_def:
            lines.append(
                f"  {away_abbr} defense: "
                f"opp PPG allowed={fmt_stat(away_def,'avgPointsAllowed')} "
                f"pace={fmt_stat(away_def,'pace')} "
                f"def_rtg={fmt_stat(away_def,'defensiveRating')}"
            )

    # Fetch player averages
    lines.append(f"\nPLAYER SEASON AVERAGES:")
    seen_players = set()
    for prop in prop_players:
        name = prop.get("player", "")
        if name in seen_players:
            continue
        seen_players.add(name)

        pid, found_name = get_player_id(name)
        if not pid:
            lines.append(f"  {name}: stats unavailable")
            continue

        pstats = get_player_stats(pid)
        if not pstats:
            lines.append(f"  {name}: stats unavailable")
            continue

        ppg = pstats.get("avgPoints", pstats.get("PPG"))
        rpg = pstats.get("avgRebounds", pstats.get("RPG"))
        apg = pstats.get("avgAssists", pstats.get("APG"))
        mpg = pstats.get("avgMinutes", pstats.get("MIN"))

        parts = []
        if ppg is not None: parts.append(f"PPG={ppg:.1f}")
        if rpg is not None: parts.append(f"RPG={rpg:.1f}")
        if apg is not None: parts.append(f"APG={apg:.1f}")
        if mpg is not None: parts.append(f"MPG={mpg:.1f}")

        line_val  = prop.get("line", 0)
        stat_type = prop.get("stat", "Points")
        avg_map   = {"Points": ppg, "Rebounds": rpg, "Assists": apg}
        avg       = avg_map.get(stat_type)
        vs_line   = ""
        if avg is not None and line_val:
            diff = avg - float(line_val)
            vs_line = f" [avg {'+' if diff > 0 else ''}{diff:.1f} vs {line_val} line]"

        lines.append(f"  {name}: {' '.join(parts)}{vs_line}")

    return "\n".join(lines)
