"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 NBA AI PREDICTOR v5  —  entry point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW TO RUN (every time):
  cd C:/NBA
  rmdir /s /q cache_nba
  python nba_picks.py

OTHER COMMANDS:
  python nba_picks.py --date 2026-04-05   ← specific date
  python nba_picks.py --history           ← rebuild all history tabs
  python nba_picks.py --reset-record      ← recalculate P&L from scratch
  python backtest.py                      ← backtest on saved history

FILE STRUCTURE:
  nba_picks.py      ← this file (orchestrator / CLI)
  config.py         ← API keys + paths
  utils.py          ← date helpers, HTTP fetch, odds math
  record.py         ← W/L record management
  espn.py           ← ESPN schedule + game detail
  odds.py           ← Odds API fetch + parsing
  predictor.py      ← statistical pre-model
  claude_ai.py      ← batched Claude Sonnet call
  history.py        ← save / load / grade history
  html_builder.py   ← build app.html
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json, os, sys
from datetime import date, timedelta

from config import HISTORY_DIR, APP_FILE, RECORD_FILE
from utils import today_str, fmt_odds, wipe_schedule_cache
from record import load_record, save_record
from espn import espn_schedule, espn_game_detail
from odds import odds_today, odds_props, parse_game_odds, parse_props, match_odds_event
from prizepicks import fetch_prizepicks_props, filter_props_for_game
from prop_context import build_prop_context, get_team_stats
from prop_search import enrich_props_with_context
from predictor import predict
from groq_ai import groq_analyze_all as claude_analyze_all
from history import save_history, load_history, grade_day, grade_yesterday
from html_builder import build_html


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _build_hist_games(hdata):
    """Convert a history day dict into the format build_html expects."""
    hist_games = []
    for pg in hdata.get("games", []):
        fake_g = {
            "espn_id":   pg.get("espn_id", ""),
            "date":      hdata.get("date", ""),
            "sort_ts":   "",
            "homeAbbr":  pg["homeAbbr"],
            "awayAbbr":  pg["awayAbbr"],
            "homeTeam":  pg["homeTeam"],
            "awayTeam":  pg["awayTeam"],
            "homeRec":   pg.get("homeRec", {"summary": "?", "wins": 0, "losses": 0, "pct": 0.5}),
            "awayRec":   pg.get("awayRec", {"summary": "?", "wins": 0, "losses": 0, "pct": 0.5}),
            "homeScore": 0, "awayScore": 0, "totalPts": 0,
            "homeWon":   None,
            "completed": pg.get("result") is not None,
            "startTime": pg.get("startTime", ""),
        }
        pred_r = {
            **pg.get("pred", {}),
            "result":       pg.get("result"),
            "result_score": pg.get("result_score", ""),
            "tot_result":   pg.get("tot_result"),
        }
        hist_games.append({
            "game":   fake_g,
            "pred":   pred_r,
            "ai":     pg.get("ai", {}),
            "props":  pg.get("props", []),
            "detail": {"injuries": pg.get("injuries", [])},
        })
    return hist_games


def _build_history_pages(history, active_date, record):
    """Write individual HTML files for past days so day tabs link correctly."""
    from config import DIR
    for hday in history:
        ds = hday.get("date", "")
        if ds == active_date:
            continue
        hist_games = _build_hist_games(hday)
        hhtml      = build_html(hist_games, record, history=history, active_date=ds)
        path       = os.path.join(DIR, f"history_{ds}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(hhtml)


# ── CORE RUN ──────────────────────────────────────────────────────────────────
def run_for_date(target_date):
    """Fetch, analyze, save, and build HTML for a given date string."""
    record = load_record()
    grade_yesterday(record)

    at  = record["alltime"]
    tot = at.get("W", 0) + at.get("L", 0)
    pct = round(at["W"] / tot * 100, 1) if tot else 0
    print(f"\n📊  Record: {at['W']}-{at['L']} ({pct}%)")

    print(f"\n📅  Schedule ({target_date})...")
    games    = espn_schedule(target_date)
    upcoming = [g for g in games if not g["completed"]]

    # All games done (or no games) — load from history if available
    if not upcoming:
        hist_path = os.path.join(HISTORY_DIR, f"{target_date}.json")
        if os.path.exists(hist_path):
            print("    All games completed — loading saved picks from history")
            with open(hist_path) as f:
                hdata = json.load(f)
            grade_day(target_date, record)
            hist_games = _build_hist_games(hdata)
            history    = load_history(10)
            html       = build_html(hist_games, record, history=history, active_date=target_date)
            with open(APP_FILE, "w", encoding="utf-8") as f:
                f.write(html)
            _build_history_pages(history, target_date, record)
            print("✅  Done — open app.html")
            return
        else:
            print(f"    No upcoming games and no saved picks for {target_date}")
            history = load_history(10)
            html    = build_html([], record, history=history, active_date=target_date)
            with open(APP_FILE, "w", encoding="utf-8") as f:
                f.write(html)
            print("✅  Done — open app.html")
            return

    print(f"\n💰  Odds...")
    odds_data = odds_today()

    # Step 1: fetch odds + injury detail for every upcoming game
    print(f"\n🔍  Fetching odds + injuries for {len(upcoming)} games...")
    all_pp_props = fetch_prizepicks_props()
    team_map = get_team_stats()
    games_prep = []
    for g in upcoming:
        print(f"  {g['awayAbbr']} @ {g['homeAbbr']}", end=" ")
        odds_ev      = match_odds_event(odds_data, g["homeTeam"], g["awayTeam"])
        ml_odds      = {}
        total_odds   = {}
        raw_props_bm = []

        if odds_ev:
            ml_odds, total_odds = parse_game_odds(odds_ev)
            raw_props_bm        = odds_props(odds_ev.get("id", ""))
            print(
                f"| {g['homeAbbr']} {fmt_odds(ml_odds.get(g['homeTeam']))} "
                f"/ {g['awayAbbr']} {fmt_odds(ml_odds.get(g['awayTeam']))}",
                end=" ",
            )
        else:
            print("| no odds", end=" ")

        detail = espn_game_detail(g["espn_id"])
        print(f"| {len(detail['injuries'])} injuries")

        pred  = predict(g, ml_odds, total_odds, detail)
        props = parse_props(raw_props_bm)
        # Supplement with PrizePicks props if odds props are empty
        if not props and all_pp_props:
            props = filter_props_for_game(all_pp_props, g["homeTeam"], g["awayTeam"])
        # Build prop context for this game
        prop_ctx = ""
        if props:
            try:
                prop_ctx = build_prop_context(props, g["homeAbbr"], g["awayAbbr"], team_map)
            except Exception as e:
                pass
        # Store PrizePicks props separately so model only sees what PP has
        pp_filtered = filter_props_for_game(all_pp_props, g["homeTeam"], g["awayTeam"], g["homeAbbr"], g["awayAbbr"]) if all_pp_props else []
        # Enrich PrizePicks props with Tavily search context
        if pp_filtered:
            try:
                pp_filtered = enrich_props_with_context(
                    pp_filtered, g["homeAbbr"], g["awayAbbr"], g["homeTeam"], g["awayTeam"]
                )
            except Exception as e:
                pass
        games_prep.append({"game": g, "pred": pred, "detail": detail, "props": props, "prop_ctx": prop_ctx, "pp_props": pp_filtered})

    # Step 2: ONE Claude call for all games
    print(f"\n🤖  Claude analyzing all {len(games_prep)} games in one call...")
    ai_results = claude_analyze_all(games_prep)

    # Normalize prop_picks field names — model uses inconsistent schema
    for ai in ai_results:
        normalized = []
        for prop in ai.get("prop_picks", []):
            # Normalize direction field
            direction = prop.get("dir") or prop.get("outcome") or "OVER"
            # Normalize stat field — prefer "prop" key over "stat" if stat says "Points" for everything
            stat = prop.get("prop") or prop.get("stat") or "Points"
            # Normalize confidence — derive from edge value if not provided
            conf = prop.get("confidence")
            if not conf:
                edge_val = prop.get("edge", 0)
                try:
                    # edge of 0.03 -> ~65%, 0.04 -> ~68%, 0.05 -> ~70%
                    conf = min(80, max(55, 55 + int(float(edge_val) * 500)))
                except:
                    conf = 60
            normalized.append({
                "player":     prop.get("player", ""),
                "stat":       stat,
                "line":       prop.get("line", 0),
                "dir":        direction,
                "confidence": conf,
                "reasoning":  prop.get("reasoning", ""),
                "odds":       prop.get("odds", -115),
            })
        ai["prop_picks"] = normalized

    # Post-process: backfill prop lines from PrizePicks data
    # Key: "player_name|stat|line" for exact matching
    pp_lookup = {}
    for p in all_pp_props:
        key = f"{p['player'].lower().strip()}|{p.get('stat','')}|{p.get('line','')}"
        pp_lookup[key] = p
    # Also build player|stat -> list of lines for fuzzy matching
    pp_by_player_stat = {}
    for p in all_pp_props:
        key = f"{p['player'].lower().strip()}|{p.get('stat','')}"
        if key not in pp_by_player_stat:
            pp_by_player_stat[key] = []
        pp_by_player_stat[key].append(p)

    for gi, ai in zip(games_prep, ai_results):
        for prop in ai.get("prop_picks", []):
            player_key = prop.get("player", "").lower().strip()
            stat       = prop.get("stat", "")
            direction  = prop.get("dir", "OVER")

            # Match player+stat in PrizePicks
            exact_key  = f"{player_key}|{stat}"
            candidates = pp_by_player_stat.get(exact_key)
            if not candidates:
                for ps_key, pp_list in pp_by_player_stat.items():
                    ps_player = ps_key.split("|")[0]
                    ps_stat   = ps_key.split("|")[1] if "|" in ps_key else ""
                    if ps_stat == stat and (player_key in ps_player or ps_player in player_key):
                        candidates = pp_list
                        break

            # Pick median line
            matched = None
            if candidates:
                sorted_c = sorted(candidates, key=lambda x: x["line"])
                matched  = sorted_c[len(sorted_c)//2]

            if not matched:
                print(f"    ✗ No PP match for '{prop.get('player')}' {stat} — skipping")
                prop["_skip"] = True
                continue

            # Backfill line and odds
            line_val      = float(matched["line"])
            prop["line"]  = line_val
            prop["stat"]  = matched.get("stat", stat)
            book_odds     = matched.get("OVER" if direction == "OVER" else "UNDER", -115)
            prop["odds"]  = int(book_odds) if book_odds else -115

            # Calculate confidence continuously from line value
            # Higher line = star player = more minutes/touches = more predictable
            if stat == "Points":
                # Scale: 10pts=57%, 20pts=63%, 30pts=68%, 40pts=72%
                conf = round(min(75, 55 + (line_val / 40) * 20))
            elif stat == "Rebounds":
                conf = round(min(73, 55 + (line_val / 15) * 18))
            elif stat == "Assists":
                conf = round(min(72, 55 + (line_val / 12) * 17))
            else:
                conf = 60

            # Boost if book prices it heavily (means books think it hits)
            o = float(book_odds) if book_odds else -115
            impl = abs(o)/(abs(o)+100) if o < 0 else 100/(o+100)
            if impl >= 0.60: conf = min(78, conf + 5)
            elif impl <= 0.47: conf = max(53, conf - 3)

            prop["confidence"] = conf

            # Generate reasoning from real data
            player_name = prop.get("player", "")
            prop["reasoning"] = (
                f"{player_name} {direction} {line_val} {prop['stat']} "
                f"— PrizePicks line, book at {'+' if o > 0 else ''}{int(o)}."
            )

            print(f"    ✓ Backfilled {player_name} {prop['stat']} {line_val} → {conf}% conf")

    games_data = []
    for gi, ai in zip(games_prep, ai_results):
        print(
            f"  → {gi['game']['awayAbbr']} @ {gi['game']['homeAbbr']}: "
            f"{ai.get('pick_team','?')} ({ai.get('confidence','?')}%)  "
            
        )
        # Remove props that had no valid PrizePicks match
        ai["prop_picks"] = [p for p in ai.get("prop_picks", []) if not p.get("_skip")]
        games_data.append({
            "game":   gi["game"],
            "pred":   gi["pred"],
            "ai":     ai,
            "props":  gi["props"],
            "detail": gi["detail"],
        })

    # Grade any ungraded history days (past 7 days)
    for i in range(1, 8):
        ds = (date.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        if os.path.exists(os.path.join(HISTORY_DIR, f"{ds}.json")):
            grade_day(ds, record)

    save_history(target_date, games_data)
    history = load_history(10)
    html    = build_html(games_data, record, history=history, active_date=target_date)
    with open(APP_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    _build_history_pages(history, target_date, record)

    props = sum(len(g["props"]) for g in games_data)
    print(f"\n✅  Done — open app.html")
    print(f"    {len(games_data)} games · {props} props")
    print(f"    {len(history)} days in history tabs\n")


# ── HISTORY REBUILD ───────────────────────────────────────────────────────────
def main_history():
    """Rebuild app.html from saved history.  Run: python nba_picks.py --history"""
    print("\n📅  Rebuilding history view...")
    record  = load_record()
    history = load_history(14)
    for hday in history:
        grade_day(hday.get("date", ""), record)
    html = build_html([], record, history=history, active_date=None)
    with open(APP_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    _build_history_pages(history, "", record)
    print(f"✅  Done — open app.html ({len(history)} days)\n")


# ── RESET RECORD ──────────────────────────────────────────────────────────────
def reset_record():
    """Delete record and re-grade all history so P&L recalculates correctly."""
    if os.path.exists(RECORD_FILE):
        os.remove(RECORD_FILE)

    # Unmark all history days so they get re-graded
    for fn in os.listdir(HISTORY_DIR):
        if fn.endswith(".json"):
            fp = os.path.join(HISTORY_DIR, fn)
            with open(fp) as f:
                d = json.load(f)
            d["graded"] = False
            with open(fp, "w") as f:
                json.dump(d, f, indent=2)

    record = load_record()
    print("Re-grading all history days...")
    for fn in sorted(os.listdir(HISTORY_DIR)):
        if fn.endswith(".json"):
            ds = fn.replace(".json", "")
            grade_day(ds, record)

    print(f"Done. Record: {record['alltime']['W']}-{record['alltime']['L']}")
    main_history()


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n🏀  NBA AI PREDICTOR v5")
    print("=" * 50)
    wipe_schedule_cache()

    target = today_str()
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
            print(f"\n📆  Running for date: {target}")

    run_for_date(target)


if __name__ == "__main__":
    if "--history" in sys.argv:
        main_history()
    elif "--reset-record" in sys.argv:
        reset_record()
    else:
        main()