import json
import math

with open("rotowire_games_clean.json") as f:
    games = json.load(f)

# Filter to 2025-26 season only
season = [g for g in games if g["season"] == 2025]
print(f"2025-26 season games: {len(season)}\n")

def spread_to_prob(spread):
    """Convert point spread to win probability using logistic curve."""
    return 1 / (1 + math.exp(-0.15 * spread))

def confidence(prob):
    return round(prob * 100)

def bucket(conf):
    if conf >= 80: return "80+"
    if conf >= 70: return "70-79"
    if conf >= 60: return "60-69"
    return "50-59"

def prob_to_ml(prob):
    """Convert win probability to approximate moneyline (with vig)."""
    if prob <= 0:
        return None
    vigged = prob * 1.045
    vigged = min(vigged, 0.98)
    if vigged >= 0.5:
        return -(vigged / (1 - vigged)) * 100
    else:
        return ((1 - vigged) / vigged) * 100

def ml_payout(stake, ml):
    """Profit on a winning bet."""
    if ml is None:
        return stake * 0.9
    if ml < 0:
        return stake * (100 / abs(ml))
    else:
        return stake * (ml / 100)

# Simulate picks — always pick the favorite
results = []
for g in season:
    if g["home_line"] is None or g["winner"] is None:
        continue

    if g["home_line"] <= 0:
        pick_side = "home"
        prob = spread_to_prob(abs(g["home_line"]))
        pick_team = g["home_team"]
        won = (g["winner"] == g["home_team"])
    else:
        pick_side = "away"
        prob = spread_to_prob(g["home_line"])
        pick_team = g["away_team"]
        won = (g["winner"] == g["away_team"])

    conf = confidence(prob)
    results.append({
        "game":      f"{g['away_team']} @ {g['home_team']}",
        "pick":      pick_team,
        "conf":      conf,
        "won":       won,
        "home_line": g["home_line"],
    })

print(f"Simulated picks: {len(results)}\n")

# ── BY CONFIDENCE BUCKET ──────────────────────────────────
print("=" * 55)
print("HIT RATE BY CONFIDENCE BUCKET (always pick favorite)")
print("=" * 55)
print(f"  {'Bucket':<10} {'W':>5} {'L':>5} {'Total':>7} {'Hit%':>7}")
print(f"  {'-'*10} {'-'*5} {'-'*5} {'-'*7} {'-'*7}")

for b in ["50-59", "60-69", "70-79", "80+"]:
    bg = [r for r in results if bucket(r["conf"]) == b]
    if not bg: continue
    w = sum(1 for r in bg if r["won"])
    l = len(bg) - w
    print(f"  {b:<10} {w:>5} {l:>5} {len(bg):>7} {w/len(bg)*100:>6.1f}%")

total_w = sum(1 for r in results if r["won"])
print(f"  {'TOTAL':<10} {total_w:>5} {len(results)-total_w:>5} {len(results):>7} {total_w/len(results)*100:>6.1f}%")

# ── BY SPREAD BUCKET ─────────────────────────────────────
print(f"\n{'=' * 55}")
print("HIT RATE BY SPREAD SIZE")
print("=" * 55)
print(f"  {'Spread':<20} {'W':>5} {'L':>5} {'Total':>7} {'Hit%':>7}")
print(f"  {'-'*20} {'-'*5} {'-'*5} {'-'*7} {'-'*7}")

spread_buckets = [
    ("Pick em (0-1.5)",   0,   1.5),
    ("Small   (1.5-4.5)", 1.5, 4.5),
    ("Mid     (4.5-8.5)", 4.5, 8.5),
    ("Large   (8.5-14)",  8.5, 14.0),
    ("Blowout (14+)",    14.0, 99.0),
]
for label, lo, hi in spread_buckets:
    bg = [r for r in results if lo <= abs(r["home_line"]) < hi]
    if not bg: continue
    w = sum(1 for r in bg if r["won"])
    print(f"  {label:<20} {w:>5} {len(bg)-w:>5} {len(bg):>7} {w/len(bg)*100:>6.1f}%")

# ── THRESHOLD SIMULATION ─────────────────────────────────
print(f"\n{'=' * 65}")
print("$10 FLAT BET — WHAT IF YOU ONLY BET ABOVE CONFIDENCE THRESHOLD?")
print("=" * 65)
print(f"  {'Min Conf':<10} {'Picks':>6} {'W':>5} {'L':>5} {'Hit%':>7} {'P&L':>10} {'ROI':>7}")
print(f"  {'-'*10} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*10} {'-'*7}")

for threshold in [50, 60, 65, 70, 75, 80, 85, 90]:
    filtered = [r for r in results if r["conf"] >= threshold]
    if not filtered: continue
    w = sum(1 for r in filtered if r["won"])
    l = len(filtered) - w

    pnl = 0
    for r in filtered:
        ml = prob_to_ml(r["conf"] / 100)
        if r["won"]:
            pnl += ml_payout(10, ml)
        else:
            pnl -= 10

    roi = pnl / (len(filtered) * 10) * 100
    pnl_str = f"+${pnl:.0f}" if pnl >= 0 else f"-${abs(pnl):.0f}"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
    print(f"  {threshold:<10} {len(filtered):>6} {w:>5} {l:>5} {w/len(filtered)*100:>6.1f}%  {pnl_str:>9}  {roi_str:>7}")

# ── ODDS CAP FILTER ───────────────────────────────────────
print(f"\n{'=' * 65}")
print("$10 BET — CONFIDENCE + MAX ODDS CAP COMBINED")
print("=" * 65)
print(f"  {'Conf':<6} {'Max Odds':<10} {'Picks':>6} {'W':>5} {'L':>5} {'Hit%':>7} {'P&L':>9} {'ROI':>7}")
print(f"  {'-'*6} {'-'*10} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*9} {'-'*7}")

for threshold in [70, 75, 80, 85]:
    for max_ml in [-150, -200, -250, -300, -350]:
        filtered = [
            r for r in results
            if r["conf"] >= threshold
            and prob_to_ml(r["conf"] / 100) >= max_ml
        ]
        if len(filtered) < 20:
            continue
        w = sum(1 for r in filtered if r["won"])
        l = len(filtered) - w

        pnl = 0
        for r in filtered:
            ml = prob_to_ml(r["conf"] / 100)
            if r["won"]:
                pnl += ml_payout(10, ml)
            else:
                pnl -= 10

        roi = pnl / (len(filtered) * 10) * 100
        pnl_str = f"+${pnl:.0f}" if pnl >= 0 else f"-${abs(pnl):.0f}"
        roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
        marker = " ◄ PROFITABLE" if pnl > 0 else ""
        print(f"  {threshold:<6} {max_ml:<10} {len(filtered):>6} {w:>5} {l:>5} {w/len(filtered)*100:>6.1f}%  {pnl_str:>8}  {roi_str:>7}{marker}")
    print()

print("Done.")
# ── THRESHOLD SIMULATION ─────────────────────────────────
print(f"\n{'=' * 65}")
print("$10 FLAT BET — WHAT IF YOU ONLY BET ABOVE CONFIDENCE THRESHOLD?")
print("=" * 65)
print(f"  {'Min Conf':<10} {'Picks':>6} {'W':>5} {'L':>5} {'Hit%':>7} {'P&L':>10} {'ROI':>7}")
print(f"  {'-'*10} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*10} {'-'*7}")

for threshold in [50, 60, 65, 70, 75, 80, 85, 90]:
    filtered = [r for r in results if r["conf"] >= threshold]
    if not filtered: continue
    w = sum(1 for r in filtered if r["won"])
    l = len(filtered) - w
    pnl = 0
    for r in filtered:
        ml = prob_to_ml(r["conf"] / 100)
        if r["won"]:
            pnl += ml_payout(10, ml)
        else:
            pnl -= 10
    roi = pnl / (len(filtered) * 10) * 100
    pnl_str = f"+${pnl:.0f}" if pnl >= 0 else f"-${abs(pnl):.0f}"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
    print(f"  {threshold:<10} {len(filtered):>6} {w:>5} {l:>5} {w/len(filtered)*100:>6.1f}%  {pnl_str:>9}  {roi_str:>7}")

# ── ODDS CAP FILTER ───────────────────────────────────────
print(f"\n{'=' * 65}")
print("$10 BET — CONFIDENCE + MAX ODDS CAP COMBINED")
print("=" * 65)
print(f"  {'Conf':<6} {'Max Odds':<10} {'Picks':>6} {'W':>5} {'L':>5} {'Hit%':>7} {'P&L':>9} {'ROI':>7}")
print(f"  {'-'*6} {'-'*10} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*9} {'-'*7}")

for threshold in [60, 65, 70, 75]:
    for max_ml in [-110, -150, -200, -250, -300]:
        filtered = [
            r for r in results
            if r["conf"] >= threshold
            and prob_to_ml(r["conf"] / 100) >= max_ml
        ]
        if len(filtered) < 5:
            continue
        w = sum(1 for r in filtered if r["won"])
        l = len(filtered) - w
        pnl = 0
        for r in filtered:
            ml = prob_to_ml(r["conf"] / 100)
            if r["won"]:
                pnl += ml_payout(10, ml)
            else:
                pnl -= 10
        roi = pnl / (len(filtered) * 10) * 100
        pnl_str = f"+${pnl:.0f}" if pnl >= 0 else f"-${abs(pnl):.0f}"
        roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
        marker = " ◄ PROFITABLE" if pnl > 0 else ""
        print(f"  {threshold:<6} {max_ml:<10} {len(filtered):>6} {w:>5} {l:>5} {w/len(filtered)*100:>6.1f}%  {pnl_str:>8}  {roi_str:>7}{marker}")
    print()

# ── B2B IMPACT ────────────────────────────────────────────
print(f"\n{'=' * 55}")
print("BACK-TO-BACK IMPACT (2025-26 season)")
print("=" * 55)

with open("rotowire_games_clean.json") as f:
    all_games = json.load(f)

season_b2b = [g for g in all_games if g["season"] == 2025 and g["winner"] is not None]

scenarios = [
    ("Neither on B2B",  lambda g: not g.get("home_b2b") and not g.get("away_b2b")),
    ("Home on B2B",     lambda g: g.get("home_b2b") and not g.get("away_b2b")),
    ("Away on B2B",     lambda g: g.get("away_b2b") and not g.get("home_b2b")),
    ("Both on B2B",     lambda g: g.get("home_b2b") and g.get("away_b2b")),
]

print(f"  {'Scenario':<22} {'Games':>6} {'Home Win%':>10} {'Fav Win%':>10}")
print(f"  {'-'*22} {'-'*6} {'-'*10} {'-'*10}")

for label, fn in scenarios:
    sg = [g for g in season_b2b if fn(g)]
    if not sg: continue
    n = len(sg)
    home_wins = sum(1 for g in sg if g["winner"] == g["home_team"])
    fav_wins = sum(1 for g in sg if g["home_line"] is not None and (
        (g["home_line"] < 0 and g["winner"] == g["home_team"]) or
        (g["home_line"] > 0 and g["winner"] == g["away_team"])
    ))
    fav_total = sum(1 for g in sg if g["home_line"] is not None and g["home_line"] != 0)
    print(f"  {label:<22} {n:>6} {home_wins/n*100:>9.1f}%  {fav_wins/fav_total*100:>9.1f}%")

print(f"\n  {'Scenario':<30} {'Games':>6} {'B2B team wins':>14}")
print(f"  {'-'*30} {'-'*6} {'-'*14}")

home_b2b_only = [g for g in season_b2b if g.get("home_b2b") and not g.get("away_b2b")]
away_b2b_only = [g for g in season_b2b if g.get("away_b2b") and not g.get("home_b2b")]

if home_b2b_only:
    hw = sum(1 for g in home_b2b_only if g["winner"] == g["home_team"])
    print(f"  {'Home team on B2B':<30} {len(home_b2b_only):>6} {hw/len(home_b2b_only)*100:>13.1f}%")

if away_b2b_only:
    aw = sum(1 for g in away_b2b_only if g["winner"] == g["away_team"])
    print(f"  {'Away team on B2B':<30} {len(away_b2b_only):>6} {aw/len(away_b2b_only)*100:>13.1f}%")

print("\nDone.")