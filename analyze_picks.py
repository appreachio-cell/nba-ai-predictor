"""
analyze_picks.py — Deep analysis of all picks history.
Shows confidence calibration, daily patterns, and prompt quality insights.

Run: cd C:/NBA && python analyze_picks.py
"""

import json, os, sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import HISTORY_DIR

def bar(w, t, width=25):
    if not t: return "░"*width
    filled = round(w/t*width)
    return "█"*filled + "░"*(width-filled)

def pct(w, t):
    return f"{round(w/t*100,1)}%" if t else "—"

def pnl_str(v):
    return f"+${v:.2f}" if v>=0 else f"-${abs(v):.2f}"

def implied_pnl(result, odds, stake=10):
    if result not in ("W","L") or odds is None: return 0.0
    o = float(odds)
    if result == "W":
        return round(stake*(100/abs(o)) if o<0 else stake*(o/100), 2)
    return -stake

def main():
    all_ml    = []
    all_ou    = []
    by_day    = defaultdict(lambda: {"ml":[],"ou":[]})

    for fn in sorted(os.listdir(HISTORY_DIR)):
        if not fn.endswith(".json"): continue
        ds = fn.replace(".json","")
        try:
            with open(os.path.join(HISTORY_DIR, fn)) as f:
                hdata = json.load(f)
        except: continue

        for pg in hdata.get("games",[]):
            ai   = pg.get("ai",{})
            pred = pg.get("pred",{})
            res  = pg.get("result")
            side = ai.get("pick","home")
            conf = ai.get("confidence", round(
                (pred.get("h_prob",0.5) if side=="home" else pred.get("a_prob",0.5))*100
            ))
            odds = pred.get("h_odds") if side=="home" else pred.get("a_odds")

            if res in ("W","L"):
                pick = {"date":ds,"conf":conf,"result":res,"odds":odds,
                        "reasoning":ai.get("reasoning",""),"edge":ai.get("edge_found",False)}
                all_ml.append(pick)
                by_day[ds]["ml"].append(pick)

            tot_res = pg.get("tot_result")
            tot_dir = ai.get("total_lean")
            tot_conf = ai.get("total_confidence")
            if tot_res in ("W","L") and tot_dir:
                tot_odds = pred.get("over_odds") if tot_dir=="OVER" else pred.get("under_odds")
                ou = {"date":ds,"conf":tot_conf,"dir":tot_dir,"result":tot_res,"odds":tot_odds}
                all_ou.append(ou)
                by_day[ds]["ou"].append(ou)

    graded_ml = [p for p in all_ml if p["result"] in ("W","L")]
    graded_ou = [p for p in all_ou if p["result"] in ("W","L")]

    print("\n" + "="*60)
    print("  PICK ANALYSIS REPORT")
    print("="*60)

    # ── ML CONFIDENCE CALIBRATION ─────────────────────────────────
    print("\n── ML CONFIDENCE CALIBRATION ──────────────────────────────")
    print(f"  {'Bucket':<10} {'W-L':<10} {'Hit%':<8} {'Expected':<10} {'Edge':<8} {'P&L'}")
    print(f"  {'-'*9} {'-'*9} {'-'*7} {'-'*9} {'-'*7} {'-'*8}")
    buckets = [("50-59",50,59),("60-69",60,69),("70-79",70,79),("80+",80,100)]
    for label, lo, hi in buckets:
        bp = [p for p in graded_ml if lo <= p["conf"] <= hi]
        if not bp: continue
        w  = sum(1 for p in bp if p["result"]=="W")
        l  = len(bp)-w
        hp = round(w/len(bp)*100,1) if bp else 0
        ex = f"{(lo+min(hi,95))//2}%"
        edge = f"+{round(hp-(lo+min(hi,95))//2,1)}%" if hp > (lo+min(hi,95))//2 else f"{round(hp-(lo+min(hi,95))//2,1)}%"
        total_pnl = sum(implied_pnl(p["result"],p["odds"]) for p in bp)
        print(f"  {label+'%':<10} {str(w)+'-'+str(l):<10} {str(hp)+'%':<8} {ex:<10} {edge:<8} {pnl_str(total_pnl)}")

    # ── EDGE VS NO EDGE ───────────────────────────────────────────
    print("\n── EDGE FLAG IMPACT ────────────────────────────────────────")
    edge_p    = [p for p in graded_ml if p["edge"]]
    no_edge_p = [p for p in graded_ml if not p["edge"]]
    for label, group in [("Edge picks", edge_p), ("No-edge picks", no_edge_p)]:
        if not group: continue
        w = sum(1 for p in group if p["result"]=="W")
        total_pnl = sum(implied_pnl(p["result"],p["odds"]) for p in group)
        print(f"  {label:<16} {w}-{len(group)-w} ({pct(w,len(group))})   P&L: {pnl_str(total_pnl)}")

    # ── O/U CALIBRATION ──────────────────────────────────────────
    if graded_ou:
        print("\n── O/U CALIBRATION ─────────────────────────────────────────")
        for direction in ("OVER","UNDER"):
            dp = [p for p in graded_ou if p["dir"]==direction]
            if not dp: continue
            w  = sum(1 for p in dp if p["result"]=="W")
            total_pnl = sum(implied_pnl(p["result"],p["odds"]) for p in dp)
            print(f"  {direction:<8} {w}-{len(dp)-w} ({pct(w,len(dp))})   P&L: {pnl_str(total_pnl)}")

        # O/U by confidence
        conf_ou = [p for p in graded_ou if p["conf"] is not None]
        if conf_ou:
            print()
            for label, lo, hi in buckets:
                bp = [p for p in conf_ou if lo <= (p["conf"] or 0) <= hi]
                if not bp: continue
                w = sum(1 for p in bp if p["result"]=="W")
                total_pnl = sum(implied_pnl(p["result"],p["odds"]) for p in bp)
                print(f"  {label+'%':<10} {str(w)+'-'+str(len(bp)-w):<10} {pct(w,len(bp)):<8} {pnl_str(total_pnl)}")

    # ── DAILY PERFORMANCE ─────────────────────────────────────────
    print("\n── DAILY ML PERFORMANCE ────────────────────────────────────")
    print(f"  {'Date':<12} {'W-L':<8} {'Hit%':<7} {'Bar'}")
    print(f"  {'-'*11} {'-'*7} {'-'*6} {'-'*25}")
    for ds in sorted(by_day.keys()):
        picks = by_day[ds]["ml"]
        graded = [p for p in picks if p["result"] in ("W","L")]
        if not graded: continue
        w = sum(1 for p in graded if p["result"]=="W")
        l = len(graded)-w
        try: dlabel = datetime.strptime(ds,"%Y-%m-%d").strftime("%b %d")
        except: dlabel = ds
        print(f"  {dlabel:<12} {str(w)+'-'+str(l):<8} {pct(w,len(graded)):<7} {bar(w,len(graded))}")

    # ── WHAT APRIL 9 DID RIGHT ────────────────────────────────────
    print("\n── BEST DAY BREAKDOWN (Apr 09) ─────────────────────────────")
    apr9 = by_day.get("2026-04-09",{}).get("ml",[])
    for p in apr9:
        marker = "✓" if p["result"]=="W" else "✗"
        print(f"  {marker} {p['conf']}% | {p['reasoning'][:80]}...")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
