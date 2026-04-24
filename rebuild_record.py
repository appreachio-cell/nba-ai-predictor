"""
rebuild_record.py — Rebuild record_nba.json purely from picks_history JSONs.
No ESPN calls needed. Reads result/tot_result already saved in each file.

Run: cd C:/NBA && python rebuild_record.py
"""

import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import HISTORY_DIR, RECORD_FILE

def implied_pnl(result, odds, stake=10):
    if result not in ("W", "L") or odds is None:
        return 0.0
    o = float(odds)
    if result == "W":
        return round(stake * (100/abs(o)) if o < 0 else stake * (o/100), 2)
    return -stake

def main():
    record = {
        "alltime":  {"W": 0, "L": 0},
        "by_month": {},
        "by_week":  {},
        "by_day":   {},
        "by_type":  {
            "ml":    {"W": 0, "L": 0},
            "total": {"W": 0, "L": 0},
            "prop":  {"W": 0, "L": 0},
        },
        "by_conf": {
            "50-59": {"W": 0, "L": 0, "pnl": 0.0},
            "60-69": {"W": 0, "L": 0, "pnl": 0.0},
            "70-79": {"W": 0, "L": 0, "pnl": 0.0},
            "80+":   {"W": 0, "L": 0, "pnl": 0.0},
        },
        "by_conf_total": {
            "OVER":  {"W": 0, "L": 0, "pnl": 0.0},
            "UNDER": {"W": 0, "L": 0, "pnl": 0.0},
        },
        "by_conf_prop": {
            "50-59": {"W": 0, "L": 0, "pnl": 0.0},
            "60-69": {"W": 0, "L": 0, "pnl": 0.0},
            "70-79": {"W": 0, "L": 0, "pnl": 0.0},
            "80+":   {"W": 0, "L": 0, "pnl": 0.0},
        },
    }

    ml_total = ou_total = prop_total = 0

    for fn in sorted(os.listdir(HISTORY_DIR)):
        if not fn.endswith(".json"):
            continue
        ds = fn.replace(".json", "")
        try:
            with open(os.path.join(HISTORY_DIR, fn)) as f:
                hdata = json.load(f)
        except:
            continue

        d   = datetime.strptime(ds, "%Y-%m-%d")
        mo  = ds[:7]
        wk  = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"

        day_w = day_l = 0

        for pg in hdata.get("games", []):
            ai   = pg.get("ai", {})
            pred = pg.get("pred", {})

            # ── ML result ────────────────────────────────────────────────────
            res = pg.get("result")
            if res in ("W", "L"):
                ml_total += 1
                record["alltime"][res] += 1
                record["by_type"]["ml"][res] += 1
                record["by_month"].setdefault(mo, {"W":0,"L":0})[res] += 1
                record["by_week"].setdefault(wk,  {"W":0,"L":0})[res] += 1
                if res == "W": day_w += 1
                else:          day_l += 1

                # Confidence bucket
                side = ai.get("pick", "home")
                conf = ai.get("confidence", round(
                    (pred.get("h_prob",0.5) if side=="home" else pred.get("a_prob",0.5))*100
                ))
                odds = pred.get("h_odds") if side=="home" else pred.get("a_odds")
                cb = "80+" if conf>=80 else "70-79" if conf>=70 else "60-69" if conf>=60 else "50-59"
                bucket = record["by_conf"][cb]
                bucket[res] += 1
                bucket["pnl"] = round(bucket["pnl"] + implied_pnl(res, odds), 2)

            # ── O/U result ───────────────────────────────────────────────────
            tot_res = pg.get("tot_result")
            tot_dir = ai.get("total_lean") or pred.get("tot_dir")
            if tot_res in ("W", "L") and tot_dir:
                ou_total += 1
                record["alltime"][tot_res] += 1
                record["by_type"]["total"][tot_res] += 1
                record["by_month"].setdefault(mo, {"W":0,"L":0})[tot_res] += 1
                record["by_week"].setdefault(wk,  {"W":0,"L":0})[tot_res] += 1
                if tot_res == "W": day_w += 1
                else:              day_l += 1

                tot_odds = pred.get("over_odds") if tot_dir=="OVER" else pred.get("under_odds")
                tb = record["by_conf_total"].setdefault(tot_dir, {"W":0,"L":0,"pnl":0.0})
                tb[tot_res] += 1
                tb["pnl"] = round(tb["pnl"] + implied_pnl(tot_res, tot_odds), 2)

            # ── Props ─────────────────────────────────────────────────────────
            for prop in ai.get("prop_picks", []):
                pr = prop.get("prop_result")
                if pr not in ("W", "L"):
                    continue
                prop_total += 1
                record["alltime"][pr] += 1
                record["by_type"]["prop"][pr] += 1
                pconf = prop.get("confidence") or 50
                cb = "80+" if pconf>=80 else "70-79" if pconf>=70 else "60-69" if pconf>=60 else "50-59"
                pb = record["by_conf_prop"][cb]
                pb[pr] += 1
                pb["pnl"] = round(pb["pnl"] + implied_pnl(pr, prop.get("odds")), 2)

        if day_w + day_l > 0:
            record["by_day"][ds] = {"W": day_w, "L": day_l}

    # Save
    with open(RECORD_FILE, "w") as f:
        json.dump(record, f, indent=2)

    at = record["alltime"]
    tot = at["W"] + at["L"]
    pct = round(at["W"]/tot*100,1) if tot else 0
    print(f"\n✅  Record rebuilt from {len(os.listdir(HISTORY_DIR))} history files")
    print(f"   All-time: {at['W']}-{at['L']} ({pct}%)")
    print(f"   ML: {record['by_type']['ml']['W']}-{record['by_type']['ml']['L']}")
    print(f"   O/U: {record['by_type']['total']['W']}-{record['by_type']['total']['L']}")
    print(f"   Props: {record['by_type']['prop']['W']}-{record['by_type']['prop']['L']}")
    print(f"   Total picks counted: {ml_total} ML | {ou_total} O/U | {prop_total} Props\n")

if __name__ == "__main__":
    main()
