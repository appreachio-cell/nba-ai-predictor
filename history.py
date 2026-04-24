"""
history.py — Save, load, and grade daily picks history.
"""

import json, os
from datetime import date, timedelta

from config import HISTORY_DIR
from espn import espn_schedule
from record import add_result, save_record
from utils import yesterday_str


# ── SAVE ──────────────────────────────────────────────────────────────────────
def save_history(date_str, games_data):
    path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    out  = {"date": date_str, "graded": False, "games": []}

    for gd in games_data:
        g    = gd["game"]
        ai   = gd["ai"]
        pred = gd["pred"]
        out["games"].append({
            "espn_id":      g["espn_id"],
            "homeAbbr":     g["homeAbbr"],
            "awayAbbr":     g["awayAbbr"],
            "homeTeam":     g["homeTeam"],
            "awayTeam":     g["awayTeam"],
            "homeRec":      g["homeRec"],
            "awayRec":      g["awayRec"],
            "startTime":    g["startTime"],
            "pred":         pred,
            "ai":           ai,
            "props":        gd.get("props", []),
            "injuries":     gd.get("detail", {}).get("injuries", []),
            "prop_picks":   ai.get("prop_picks", []),
            "result":       None,
            "result_score": None,
            "tot_result":   None,
        })

    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"    Saved → picks_history/{date_str}.json")


# ── LOAD ──────────────────────────────────────────────────────────────────────
def load_history(n=10):
    days = []
    for fn in sorted(os.listdir(HISTORY_DIR), reverse=True):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(HISTORY_DIR, fn)) as f:
                days.append(json.load(f))
        except:
            continue
        if len(days) >= n:
            break
    return days


# ── GRADE ─────────────────────────────────────────────────────────────────────
def grade_day(date_str, record):
    """Grade all picks for a completed day and update the running record."""
    path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        hdata = json.load(f)
    if hdata.get("graded"):
        return

    results = espn_schedule(date_str)
    res_map = {f"{g['awayAbbr']}@{g['homeAbbr']}": g for g in results}
    graded  = 0

    for pg in hdata.get("games", []):
        key = f"{pg['awayAbbr']}@{pg['homeAbbr']}"
        rg  = res_map.get(key)
        if not rg or not rg["completed"]:
            continue

        ai   = pg.get("ai", {})
        pred = pg.get("pred", {})
        side = ai.get("pick", pred.get("win_side", "home"))
        won  = rg["homeWon"]
        res  = "W" if (side == "home" and won) or (side == "away" and not won) else "L"

        pg["result"]       = res
        pg["result_score"] = (
            f"{rg['awayAbbr']} {rg['awayScore']}–{rg['homeScore']} {rg['homeAbbr']}"
        )

        conf      = ai.get("confidence", round(
            (pred.get("h_prob", 0.5) if side == "home" else pred.get("a_prob", 0.5)) * 100
        ))
        pick_odds = pred.get("h_odds") if side == "home" else pred.get("a_odds")
        add_result(record, res, "ml", date_str, conf=conf, odds=pick_odds)
        graded += 1

        # Total
        tot_dir = pred.get("tot_dir") or ai.get("total_lean")
        if tot_dir:
            actual   = rg["totalPts"]
            line     = pred.get("total_line", 224.0)
            tot_res  = "W" if (
                (tot_dir == "OVER"  and actual > line) or
                (tot_dir == "UNDER" and actual < line)
            ) else "L"
            pg["tot_result"] = tot_res
            tot_odds = pred.get("over_odds") if tot_dir == "OVER" else pred.get("under_odds")
            add_result(record, tot_res, "total", date_str, tot_dir=tot_dir, odds=tot_odds)

        # Props grading
        from espn import espn_box
        stat_map = {"Points": "PTS", "Rebounds": "REB", "Assists": "AST"}
        box = None
        prop_picks = pg.get("prop_picks") or pg.get("ai", {}).get("prop_picks", [])
        if prop_picks and rg.get("completed"):
            try:
                box = espn_box(pg.get("espn_id", ""))
            except:
                box = {}
        if box:
            for prop in prop_picks:
                player_key = prop.get("player", "").lower()
                stat_label = stat_map.get(prop.get("stat", ""), "")
                if not stat_label:
                    continue
                # Fuzzy match player name
                matched = None
                for k in box:
                    if player_key in k or k in player_key:
                        matched = k
                        break
                if not matched:
                    continue
                try:
                    actual = float(box[matched].get(stat_label, -1))
                    if actual < 0:
                        continue
                    line = float(prop.get("line", 0))
                    prop_res = "W" if (
                        (prop["dir"] == "OVER"  and actual > line) or
                        (prop["dir"] == "UNDER" and actual < line)
                    ) else "L"
                    prop["prop_result"] = prop_res
                    prop["actual"]      = actual
                    add_result(
                        record, prop_res, "prop", ds,
                        conf=prop.get("confidence"),
                        odds=prop.get("odds")
                    )
                except:
                    continue

    if graded:
        hdata["graded"] = True
        with open(path, "w") as f:
            json.dump(hdata, f, indent=2)
        save_record(record)
        print(f"    Graded {date_str}: {graded} picks")


def grade_yesterday(record):
    yd = yesterday_str()
    print(f"\n📋  Grading yesterday ({yd})...")
    grade_day(yd, record)