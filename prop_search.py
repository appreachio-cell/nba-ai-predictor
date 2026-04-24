"""
prop_search.py — Fetch prop context using Tavily search.
Gets opponent defensive stats and player recent form for prop reasoning.
"""

import json
import urllib.request

TAVILY_KEY = "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"
TAVILY_URL = "https://api.tavily.com/search"


def _search(query, max_results=2):
    """Single Tavily search. Returns list of result snippets."""
    try:
        body = json.dumps({
            "api_key":     TAVILY_KEY,
            "query":       query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,
        }).encode()

        req = urllib.request.Request(
            TAVILY_URL,
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())

        # Return the AI-generated answer first, then snippets
        parts = []
        if data.get("answer"):
            parts.append(data["answer"])
        for result in data.get("results", [])[:max_results]:
            snippet = result.get("content", "")[:200]
            if snippet:
                parts.append(snippet)
        return " ".join(parts)[:400]

    except Exception as e:
        return ""


def get_prop_context(player, stat, line, direction, opponent_abbr, opponent_team):
    """
    Fetch context for a single prop:
    - Player's recent average in this stat
    - Opponent's defensive ranking for this stat
    Returns a short context string.
    """
    stat_lower = stat.lower()

    # Search 1: player recent form
    player_query = f"{player} {stat_lower} per game 2026 NBA season average"
    player_ctx   = _search(player_query, max_results=1)

    # Search 2: opponent defense vs this stat
    opp_query  = f"{opponent_team} points allowed {stat_lower} opposing players 2026 NBA defensive rating"
    opp_ctx    = _search(opp_query, max_results=1)

    parts = []
    if player_ctx:
        parts.append(f"{player}: {player_ctx[:180]}")
    if opp_ctx:
        parts.append(f"vs {opponent_abbr} defense: {opp_ctx[:180]}")

    return " | ".join(parts) if parts else ""


def enrich_props_with_context(props, home_abbr, away_abbr, home_team, away_team):
    """
    Add search context to each prop.
    props: list of {player, stat, line, dir, ...} dicts
    Returns props with 'search_ctx' field added.
    """
    # Determine which team each player is on based on abbr in pp data
    for prop in props:
        player     = prop.get("player", "")
        stat       = prop.get("stat", "Points")
        line       = prop.get("line", 0)
        direction  = prop.get("dir", "OVER")
        player_team = prop.get("team", "")

        # Opponent is whichever team the player is NOT on
        if player_team == home_abbr:
            opp_abbr = away_abbr
            opp_team = away_team
        else:
            opp_abbr = home_abbr
            opp_team = home_team

        print(f"    🔍 Searching context for {player} {stat}...")
        ctx = get_prop_context(player, stat, line, direction, opp_abbr, opp_team)
        prop["search_ctx"] = ctx

    return props
