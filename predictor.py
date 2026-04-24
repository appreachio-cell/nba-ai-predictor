"""
predictor.py — Build a statistical prediction (before Claude's AI analysis).
Uses book odds (de-vigged) or team records to estimate win probabilities,
projected scores, and total lines.
"""

from utils import true_probs, calc_ev


def predict(game, ml_odds, total_odds, detail):
    """
    Return a prediction dict for a single game.

    Parameters
    ----------
    game       : game dict from espn_schedule()
    ml_odds    : {team_name: american_odds}
    total_odds : {"over_<line>": price, "under_<line>": price}
    detail     : dict from espn_game_detail()
    """
    home  = game["homeTeam"]
    away  = game["awayTeam"]
    h_rec = game["homeRec"]
    a_rec = game["awayRec"]

    # ── Win probabilities ──────────────────────────────────────────────────────
    def find_ml(team):
        tl = team.lower()
        for nm, pr in ml_odds.items():
            nl = nm.lower()
            if nl in tl or tl in nl or nl.split()[-1] in tl.split()[-1]:
                return pr
        return None

    h_odds = find_ml(home)
    a_odds = find_ml(away)

    if h_odds and a_odds:
        h_prob, a_prob = true_probs(h_odds, a_odds)
        prob_source    = "odds"
    else:
        hp    = h_rec["pct"]
        ap    = a_rec["pct"]
        raw_h = hp * 0.55 + 0.025  # home court ~2-2.5pt edge
        raw_a = ap * 0.55
        denom = (raw_h + raw_a) or 1
        h_prob      = max(0.20, min(raw_h / denom, 0.85))
        a_prob      = 1 - h_prob
        prob_source = "records"

    # ── Total line ─────────────────────────────────────────────────────────────
    total_line = detail.get("total_line")
    if not total_line:
        for k in total_odds:
            if k.startswith("over_"):
                try:
                    total_line = float(k[5:])
                    break
                except:
                    pass
    if not total_line:
        from datetime import date as _d
        _today = _d.today()
        total_line = 212.0 if (_today.month > 4 or (_today.month == 4 and _today.day >= 19)) else 224.0

    # ── Projected scores (spread math, not naïve win_prob × total) ────────────
    # NBA calibration: 50% → 0 pt spread, 60% → ~5 pt, 70% → ~11 pt, 80% → ~18 pt
    spread = (h_prob - 0.5) * 46
    h_proj = round((total_line + spread) / 2)
    a_proj = round(total_line - h_proj)

    # ── Over/Under odds ────────────────────────────────────────────────────────
    over_o = under_o = None
    for k, v in total_odds.items():
        if k.startswith("over_"):
            over_o = v
        elif k.startswith("under_"):
            under_o = v

    return {
        "h_prob":      h_prob,
        "a_prob":      a_prob,
        "h_odds":      h_odds,
        "a_odds":      a_odds,
        "h_ev":        calc_ev(h_prob, h_odds),
        "a_ev":        calc_ev(a_prob, a_odds),
        "h_proj":      h_proj,
        "a_proj":      a_proj,
        "total_line":  total_line,
        "over_odds":   over_o,
        "under_odds":  under_o,
        "prob_source": prob_source,
    }