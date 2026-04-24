"""
odds.py — The Odds API: fetch moneylines, totals, props, and match events.
"""

from config import ODDS_BASE, ODDS_KEY
from utils import fetch, implied, calc_ev


def odds_today():
    """Fetch today's moneyline + totals from major books."""
    url = (
        f"{ODDS_BASE}/odds/?apiKey={ODDS_KEY}"
        f"&regions=us&markets=h2h,totals&oddsFormat=american"
        f"&bookmakers=draftkings,fanduel,betmgm,caesars"
    )
    try:
        data = fetch(url, no_cache=True)
        print(f"    Odds API: {len(data)} games")
        return data
    except Exception as e:
        print(f"    Odds API error: {e}")
        return []


def odds_props(event_id):
    """Fetch player props (points/rebounds/assists) for a single event."""
    url = (
        f"{ODDS_BASE}/events/{event_id}/odds?apiKey={ODDS_KEY}"
        f"&regions=us&markets=player_points,player_rebounds,player_assists"
        f"&oddsFormat=american&bookmakers=draftkings,fanduel"
    )
    try:
        data = fetch(url, cache_mins=20)
        return data.get("bookmakers", [])
    except:
        return []


def parse_game_odds(ev):
    """
    From an odds event dict, return:
      ml    : {team_name: best_price}
      total : {"over_<line>": price, "under_<line>": price}
    """
    ml    = {}
    total = {}

    for bm in ev.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] == "h2h":
                for o in mkt["outcomes"]:
                    nm = o["name"]
                    pr = o["price"]
                    if nm not in ml or float(pr) > float(ml[nm]):
                        ml[nm] = pr

            elif mkt["key"] == "totals":
                for o in mkt["outcomes"]:
                    pt  = o.get("point", 220.5)
                    key = f"{'over' if o['name'].lower() == 'over' else 'under'}_{pt}"
                    pr  = o["price"]
                    if key not in total or float(pr) > float(total[key]):
                        total[key] = pr

    return ml, total


def parse_props(bookmakers):
    """
    Flatten bookmakers → list of top-EV prop picks (max 8).
    Each item: {player, stat, line, dir, odds, ev}
    """
    seen = {}

    stat_map = {
        "player_points":   "Points",
        "player_rebounds": "Rebounds",
        "player_assists":  "Assists",
    }

    for bm in bookmakers:
        for mkt in bm.get("markets", []):
            stat = stat_map.get(mkt.get("key", ""))
            if not stat:
                continue

            for o in mkt.get("outcomes", []):
                player = o.get("description") or o.get("name", "")
                if not player or player in ("Over", "Under"):
                    continue

                name_lower = o.get("name", "").lower()
                if "over" in name_lower:
                    dirn = "OVER"
                elif "under" in name_lower:
                    dirn = "UNDER"
                else:
                    continue

                pt  = float(o.get("point", 0))
                key = f"{player}|{stat}|{pt}"

                if key not in seen:
                    seen[key] = {"player": player, "stat": stat, "line": pt}
                # Keep best odds across bookmakers
                existing = seen[key].get(dirn)
                new_price = o.get("price", -999)
                if existing is None or float(new_price) > float(existing):
                    seen[key][dirn] = new_price

    results = []
    for key, p in seen.items():
        if "OVER" not in p or "UNDER" not in p:
            continue
        try:
            op = implied(p["OVER"])
            up = implied(p["UNDER"])
            t  = op + up
            if t == 0:
                continue
            to = op / t
            tu = up / t
            eo = calc_ev(to, p["OVER"])
            eu = calc_ev(tu, p["UNDER"])

            if (eo or -99) >= (eu or -99):
                best = {"dir": "OVER",  "odds": p["OVER"],  "ev": eo}
            else:
                best = {"dir": "UNDER", "odds": p["UNDER"], "ev": eu}

            results.append({**p, **best})
        except:
            continue

    results.sort(key=lambda x: -(x.get("ev") or 0))
    return results[:8]


def match_odds_event(odds_data, home_team, away_team):
    """Find the odds event dict that matches a given home/away team pair."""
    def n(s):
        return s.lower().replace(" ", "").replace(".", "")

    hn = n(home_team)
    an = n(away_team)

    for ev in odds_data:
        gh = n(ev.get("home_team", ""))
        ga = n(ev.get("away_team", ""))
        if (hn in gh or gh in hn) and (an in ga or ga in an):
            return ev

    return None