import json
import os

HISTORY_DIR = "picks_history"

def load_all_picks():
    all_games = []
    for fn in sorted(os.listdir(HISTORY_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(HISTORY_DIR, fn)) as f:
            day = json.load(f)
        for g in day.get("games", []):
            if g.get("result") is None:
                continue  # skip ungraded
            ai   = g.get("ai", {})
            pred = g.get("pred", {})
            side = ai.get("pick", pred.get("win_side", "home"))
            conf = ai.get("confidence", round(
                (pred.get("h_prob", 0.5) if side == "home" else pred.get("a_prob", 0.5)) * 100
            ))
            all_games.append({
                "date":       day["date"],
                "home":       g["homeAbbr"],
                "away":       g["awayAbbr"],
                "pick_team":  ai.get("pick_team", ""),
                "pick_side":  side,
                "confidence": conf,
                "result":     g["result"],
                "tot_result": g.get("tot_result"),
                "tot_dir":    pred.get("tot_dir") or ai.get("total_lean"),
                "edge_found": ai.get("edge_found", False),
                "score":      g.get("result_score", ""),
            })
    return all_games

def bucket(conf):
    if conf >= 80: return "80+"
    if conf >= 70: return "70-79"
    if conf >= 60: return "60-69"
    return "50-59"

games = load_all_picks()
print(f"Total graded picks: {len(games)}\n")

# ── ML BY CONFIDENCE BUCKET ───────────────────────────────
print("=" * 50)
print("MONEYLINE BY CONFIDENCE BUCKET")
print("=" * 50)
print(f"  {'Bucket':<10} {'W':>4} {'L':>4} {'Total':>6} {'Hit%':>7}")
print(f"  {'-'*10} {'-'*4} {'-'*4} {'-'*6} {'-'*7}")

buckets = ["50-59", "60-69", "70-79", "80+"]
for b in buckets:
    bg = [g for g in games if bucket(g["confidence"]) == b]
    if not bg: continue
    w = sum(1 for g in bg if g["result"] == "W")
    l = sum(1 for g in bg if g["result"] == "L")
    n = w + l
    print(f"  {b:<10} {w:>4} {l:>4} {n:>6} {w/n*100:>6.1f}%")

total_w = sum(1 for g in games if g["result"] == "W")
total_l = sum(1 for g in games if g["result"] == "L")
total_n = total_w + total_l
print(f"  {'TOTAL':<10} {total_w:>4} {total_l:>4} {total_n:>6} {total_w/total_n*100:>6.1f}%")

# ── TOTALS ────────────────────────────────────────────────
tot_games = [g for g in games if g["tot_result"] is not None]
print(f"\n{'=' * 50}")
print("TOTALS")
print("=" * 50)
tw = sum(1 for g in tot_games if g["tot_result"] == "W")
tl = sum(1 for g in tot_games if g["tot_result"] == "L")
tn = tw + tl
print(f"  Overall:  {tw}W {tl}L ({tw/tn*100:.1f}%)" if tn else "  No total picks")

over_g  = [g for g in tot_games if g["tot_dir"] == "OVER"]
under_g = [g for g in tot_games if g["tot_dir"] == "UNDER"]
if over_g:
    ow = sum(1 for g in over_g if g["tot_result"] == "W")
    print(f"  Overs:    {ow}W {len(over_g)-ow}L ({ow/len(over_g)*100:.1f}%)")
if under_g:
    uw = sum(1 for g in under_g if g["tot_result"] == "W")
    print(f"  Unders:   {uw}W {len(under_g)-uw}L ({uw/len(under_g)*100:.1f}%)")

# ── EDGE FOUND vs NO EDGE ─────────────────────────────────
print(f"\n{'=' * 50}")
print("EDGE FOUND FLAG")
print("=" * 50)
for edge in [True, False]:
    eg = [g for g in games if g["edge_found"] == edge]
    if not eg: continue
    ew = sum(1 for g in eg if g["result"] == "W")
    label = "Edge found    " if edge else "No edge found "
    print(f"  {label} {ew}W {len(eg)-ew}L ({ew/len(eg)*100:.1f}%)")

# ── BY DAY ────────────────────────────────────────────────
print(f"\n{'=' * 50}")
print("BY DAY")
print("=" * 50)
print(f"  {'Date':<12} {'W':>4} {'L':>4} {'Hit%':>7}")
print(f"  {'-'*12} {'-'*4} {'-'*4} {'-'*7}")
days = sorted(set(g["date"] for g in games))
for d in days:
    dg = [g for g in games if g["date"] == d]
    dw = sum(1 for g in dg if g["result"] == "W")
    dl = sum(1 for g in dg if g["result"] == "L")
    dn = dw + dl
    print(f"  {d:<12} {dw:>4} {dl:>4} {dw/dn*100:>6.1f}%")

# ── LOSSES DETAIL ─────────────────────────────────────────
losses = [g for g in games if g["result"] == "L"]
print(f"\n{'=' * 50}")
print(f"LOSSES ({len(losses)} total)")
print("=" * 50)
for g in losses:
    print(f"  {g['date']}  {g['away']}@{g['home']}  Picked: {g['pick_team']}  Conf: {g['confidence']}  Score: {g['score']}")

print("\nDone.")