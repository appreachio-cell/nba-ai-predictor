"""
nba_stats.py — Fetch real NBA stats for prop analysis using Tavily search.
"""

import json, re
import urllib.request

TAVILY_KEY = "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"
TAVILY_URL = "https://api.tavily.com/search"
_cache = {}


def _search(query, max_results=2):
    if query in _cache:
        return _cache[query]
    try:
        body = json.dumps({
            "api_key": TAVILY_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,
        }).encode()
        req = urllib.request.Request(TAVILY_URL, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        parts = []
        if data.get("answer"):
            parts.append(data["answer"])
        for result in data.get("results", [])[:max_results]:
            snippet = result.get("content", "")[:200]
            if snippet:
                parts.append(snippet)
        result = " ".join(parts)[:400]
        _cache[query] = result
        return result
    except:
        return ""


def _extract_number(text, keywords):
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw)
        if idx >= 0:
            snippet = text[max(0, idx-20):idx+30]
            nums = re.findall(r'\d+\.?\d*', snippet)
            if nums:
                return float(nums[0])
    return None


def get_prop_context(player_name, stat, line, opponent_abbr, opponent_team):
    parts = []
    stat_lower = stat.lower()

    # Player season average
    avg_query = f"{player_name} 2025-26 NBA season average {stat_lower} per game stats"
    avg_text  = _search(avg_query, max_results=2)
    if avg_text:
        keywords = [stat_lower[:3], "per game", "avg", "average",
                    "ppg" if stat=="Points" else "rpg" if stat=="Rebounds" else "apg"]
        avg_val = _extract_number(avg_text, keywords)
        if avg_val and 0 < avg_val < 60:
            diff = avg_val - float(line)
            sign = "+" if diff > 0 else ""
            parts.append(f"Season avg={avg_val:.1f} ({sign}{diff:.1f} vs {line} line)")
        else:
            clean = avg_text[:120].strip()
            if clean:
                parts.append(f"Stats: {clean}")

    # Opponent defense
    opp_query = f"{opponent_team} 2025-26 NBA {stat_lower} allowed opponents defense"
    opp_text  = _search(opp_query, max_results=1)
    if opp_text:
        parts.append(f"vs {opponent_abbr} defense: {opp_text[:100].strip()}")

    return " | ".join(parts) if parts else ""


def enrich_props_with_nba_stats(props, home_abbr, away_abbr, home_team="", away_team=""):
    for prop in props:
        player   = prop.get("player", "")
        stat     = prop.get("stat", "Points")
        line     = prop.get("line", 0)
        team     = prop.get("team", "")
        opp_abbr = away_abbr if team == home_abbr else home_abbr
        opp_team = away_team if team == home_abbr else home_team
        print(f"    📊 Stats for {player} {stat}...")
        ctx = get_prop_context(player, stat, line, opp_abbr, opp_team)
        prop["search_ctx"] = ctx
        if ctx:
            print(f"       → {ctx[:100]}")
    return props