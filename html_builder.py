"""
html_builder.py — Build app.html from games data and the running record.
"""

from datetime import date, datetime

from utils import calc_ev, fmt_odds, fmt_ev, ev_color


# ── CONFIDENCE BUCKET CELL ────────────────────────────────────────────────────
def _conf_cell(record, cb):
    r   = record.get("by_conf", {}).get(cb, {"W": 0, "L": 0, "pnl": 0.0})
    w   = r.get("W", 0)
    l   = r.get("L", 0)
    t   = w + l
    pnl = r.get("pnl", 0.0)
    pct = f"{round(w / t * 100)}%" if t else "—"
    col = "#16a34a" if t and w / t >= .65 else "#d97706" if t and w / t >= .52 else "#6b7280"
    pnl_col = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#9ca3af"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "—"
    return (
        f'<div style="background:#fff;border-radius:8px;padding:10px 6px;'
        f'text-align:center;border:0.5px solid #e5e7eb;">'
        f'<div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">{cb}%</div>'
        f'<div style="font-size:13px;font-weight:500;">{w}-{l}</div>'
        f'<div style="font-size:10px;color:{col};margin-top:1px;">{pct}</div>'
        f'<div style="font-size:11px;font-weight:600;color:{pnl_col};'
        f'margin-top:4px;border-top:0.5px solid #f3f4f6;padding-top:4px;">'
        f'$10 flat: {pnl_str}</div>'
        f'</div>'
    )


# ── TOTAL DIRECTION CELL ──────────────────────────────────────────────────────
def _tot_cell(label, r, accent):
    w   = r.get("W", 0)
    l   = r.get("L", 0)
    t   = w + l
    pnl = r.get("pnl", 0.0)
    pct = f"{round(w / t * 100)}%" if t else "—"
    col = "#16a34a" if t and w / t >= .55 else "#d97706" if t and w / t >= .50 else "#6b7280"
    pnl_col = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#9ca3af"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "—"
    return (
        f'<div style="background:#fff;border-radius:8px;padding:10px 6px;'
        f'text-align:center;border:0.5px solid #e5e7eb;flex:1;">'
        f'<div style="font-size:11px;font-weight:600;color:{accent};margin-bottom:3px;">{label}</div>'
        f'<div style="font-size:20px;font-weight:500;color:#111;">{w}-{l}</div>'
        f'<div style="font-size:10px;color:{col};margin-top:1px;">{pct}</div>'
        f'<div style="font-size:11px;font-weight:600;color:{pnl_col};'
        f'margin-top:4px;border-top:0.5px solid #f3f4f6;padding-top:4px;">'
        f'$10 flat: {pnl_str}</div>'
        f'</div>'
    )


# ── PROP CONFIDENCE CELL ─────────────────────────────────────────────────────
def _prop_conf_cell(record, cb):
    r   = record.get("by_conf_prop", {}).get(cb, {"W": 0, "L": 0, "pnl": 0.0})
    w   = r.get("W", 0)
    l   = r.get("L", 0)
    t   = w + l
    pnl = r.get("pnl", 0.0)
    pct = f"{round(w / t * 100)}%" if t else "—"
    col = "#16a34a" if t and w / t >= .65 else "#d97706" if t and w / t >= .52 else "#6b7280"
    pnl_col = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#9ca3af"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "—"
    return (
        f'<div style="background:#fff;border-radius:8px;padding:10px 6px;'
        f'text-align:center;border:0.5px solid #e5e7eb;">'
        f'<div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">{cb}%</div>'
        f'<div style="font-size:13px;font-weight:500;">{w}-{l}</div>'
        f'<div style="font-size:10px;color:{col};margin-top:1px;">{pct}</div>'
        f'<div style="font-size:11px;font-weight:600;color:{pnl_col};'
        f'margin-top:4px;border-top:0.5px solid #f3f4f6;padding-top:4px;">'
        f'$10 flat: {pnl_str}</div>'
        f'</div>'
    )


# ── O/U CONFIDENCE CELL ──────────────────────────────────────────────────────
def _ou_conf_cell(record, cb):
    r   = record.get("by_conf_ou", {}).get(cb, {"W": 0, "L": 0, "pnl": 0.0})
    w   = r.get("W", 0)
    l   = r.get("L", 0)
    t   = w + l
    pnl = r.get("pnl", 0.0)
    pct = f"{round(w / t * 100)}%" if t else "—"
    col = "#16a34a" if t and w / t >= .65 else "#d97706" if t and w / t >= .52 else "#6b7280"
    pnl_col = "#16a34a" if pnl > 0 else "#dc2626" if pnl < 0 else "#9ca3af"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "—"
    return (
        f'<div style="background:#fff;border-radius:8px;padding:10px 6px;'
        f'text-align:center;border:0.5px solid #e5e7eb;">'
        f'<div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">{cb}%</div>'
        f'<div style="font-size:13px;font-weight:500;">{w}-{l}</div>'
        f'<div style="font-size:10px;color:{col};margin-top:1px;">{pct}</div>'
        f'<div style="font-size:11px;font-weight:600;color:{pnl_col};'
        f'margin-top:4px;border-top:0.5px solid #f3f4f6;padding-top:4px;">'
        f'$10 flat: {pnl_str}</div>'
        f'</div>'
    )


# ── MAIN HTML BUILDER ─────────────────────────────────────────────────────────
def build_html(games_data, record, history=None, active_date=None):
    td  = date.today()
    at  = record["alltime"]
    tot = at.get("W", 0) + at.get("L", 0)
    wr  = round(at["W"] / tot * 100, 1) if tot else None
    wrc = "#16a34a" if (wr or 0) >= 65 else "#d97706" if (wr or 0) >= 52 else "#6b7280"
    mo  = td.strftime("%Y-%m")
    wk  = f"{td.isocalendar()[0]}-W{td.isocalendar()[1]:02d}"
    yd  = (td - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")

    def rs(r):
        return f"{r.get('W', 0)}-{r.get('L', 0)}" if r.get("W", 0) + r.get("L", 0) else "—"

    mo_r = record.get("by_month", {}).get(mo, {})
    wk_r = record.get("by_week",  {}).get(wk, {})
    yd_r = record.get("by_day",   {}).get(yd, {})

    # ── Day navigation tabs ────────────────────────────────────────────────────
    day_tabs = ""
    if history:
        is_today     = not active_date or active_date == str(td)
        tab_active   = "background:#111;color:#fff;border:none;"
        tab_inactive = "background:#f3f4f6;color:#374151;border:none;"
        today_label  = td.strftime("%b %d")

        day_tabs += (
            f'<a href="app.html" style="display:inline-block;padding:7px 14px;'
            f'border-radius:20px;font-size:12px;font-weight:500;text-decoration:none;'
            f'margin-right:6px;{tab_active if is_today else tab_inactive}">'
            f'Today · {today_label}</a>'
        )

        for hday in history:
            ds = hday.get("date", "")
            if ds == str(td):
                continue
            try:
                dlabel = datetime.strptime(ds, "%Y-%m-%d").strftime("%b %d")
            except:
                dlabel = ds

            wins   = sum(1 for g in hday.get("games", []) if g.get("result") == "W")
            graded = sum(1 for g in hday.get("games", []) if g.get("result") in ("W", "L"))
            rec    = f" {wins}-{graded - wins}" if graded else ""
            rc     = "#16a34a" if graded and wins / graded >= .6 else "#dc2626" if graded else "#9ca3af"
            is_a   = active_date == ds

            day_tabs += (
                f'<a href="history_{ds}.html" style="display:inline-block;padding:7px 14px;'
                f'border-radius:20px;font-size:12px;font-weight:500;text-decoration:none;'
                f'margin-right:6px;{tab_active if is_a else tab_inactive}">'
                f'{dlabel}<span style="font-size:11px;color:{"#aaa" if is_a else rc};">{rec}</span></a>'
            )

        day_tabs = (
            f'<div style="overflow-x:auto;white-space:nowrap;margin-bottom:16px;'
            f'padding-bottom:4px;">{day_tabs}</div>'
        )

    # ── ML Record board ────────────────────────────────────────────────────────
    type_cells = "".join(
        f'<div style="background:#fff;border-radius:8px;padding:8px 10px;text-align:center;'
        f'border:0.5px solid #e5e7eb;">'
        f'<div style="font-size:10px;color:#9ca3af;">{t.upper()}</div>'
        f'<div style="font-size:14px;font-weight:500;">'
        f'{record.get("by_type",{}).get(t,{}).get("W",0)}-'
        f'{record.get("by_type",{}).get(t,{}).get("L",0)}</div></div>'
        for t in ["ml", "total", "prop"]
    )
    conf_cells = "".join(_conf_cell(record, cb) for cb in ["50-59", "60-69", "70-79", "80+"])

    rec_html = f"""
<div style="background:#f9fafb;border-radius:12px;border:0.5px solid #e5e7eb;padding:16px 18px;margin-bottom:20px;">
  <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:12px;">Model record · Moneyline</div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px;">
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">All time</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{at.get('W',0)}-{at.get('L',0)}</div>
      <div style="font-size:11px;color:{wrc};">{f'{wr}%' if wr else '—'}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">This month</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{rs(mo_r)}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">This week</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{rs(wk_r)}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">Yesterday</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{rs(yd_r)}</div>
    </div>
  </div>
  <div style="height:5px;background:#e5e7eb;border-radius:99px;overflow:hidden;margin-bottom:4px;">
    <div style="width:{wr or 0}%;height:100%;background:{wrc};border-radius:99px;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;">
    <span>Hit rate</span><span>Target 65% · Break-even 52.4%</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px;">
    {type_cells}
  </div>
  <div style="margin-top:12px;">
    <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.07em;color:#9ca3af;margin-bottom:8px;">ML record by confidence</div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
      {conf_cells}
    </div>
  </div>
</div>"""

    # ── O/U Record board ───────────────────────────────────────────────────────
    tot_record = record.get("by_conf_total", {})
    over_r     = tot_record.get("OVER",  {"W": 0, "L": 0, "pnl": 0.0})
    under_r    = tot_record.get("UNDER", {"W": 0, "L": 0, "pnl": 0.0})
    ot         = record.get("by_type", {}).get("total", {"W": 0, "L": 0})
    ot_total   = ot.get("W", 0) + ot.get("L", 0)
    ot_wr      = round(ot.get("W", 0) / ot_total * 100, 1) if ot_total else None
    ot_wrc     = "#16a34a" if (ot_wr or 0) >= 55 else "#d97706" if (ot_wr or 0) >= 50 else "#6b7280"

    tot_html = f"""
<div style="background:#f9fafb;border-radius:12px;border:0.5px solid #e5e7eb;padding:16px 18px;margin-bottom:20px;">
  <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:12px;">Model record · Over/Under</div>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px;">
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">All time O/U</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{ot.get('W',0)}-{ot.get('L',0)}</div>
      <div style="font-size:11px;color:{ot_wrc};">{f'{ot_wr}%' if ot_wr else '—'}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">Target</div>
      <div style="font-size:14px;font-weight:500;color:#111;">55%+</div>
      <div style="font-size:11px;color:#9ca3af;">Break-even 52.4%</div>
    </div>
  </div>
  <div style="height:5px;background:#e5e7eb;border-radius:99px;overflow:hidden;margin-bottom:4px;">
    <div style="width:{ot_wr or 0}%;height:100%;background:{ot_wrc};border-radius:99px;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;margin-bottom:12px;">
    <span>Hit rate</span><span>Overs vs Unders breakdown below</span>
  </div>
  <div style="display:flex;gap:8px;">
    {_tot_cell("⬆ OVER", over_r, "#2563eb")}
    {_tot_cell("⬇ UNDER", under_r, "#7c3aed")}
  </div>
  <div style="margin-top:12px;">
    <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.07em;color:#9ca3af;margin-bottom:8px;">O/U record by confidence</div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
      {"".join(_ou_conf_cell(record, cb) for cb in ["50-59", "60-69", "70-79", "80+"])}
    </div>
  </div>
</div>"""

    # ── Game cards ─────────────────────────────────────────────────────────────
    cards = ""
    for idx, gd in enumerate(games_data):
        g      = gd["game"]
        pred   = gd["pred"]
        ai     = gd["ai"]
        props  = gd.get("props", [])
        detail = gd.get("detail", {})

        ai_side = ai.get("pick", "home" if pred["h_prob"] >= pred["a_prob"] else "away")
        ai_team = ai.get("pick_team", g["homeTeam"] if ai_side == "home" else g["awayTeam"])
        my_prob = ai.get("my_prob", pred["h_prob"] if ai_side == "home" else pred["a_prob"])
        conf    = ai.get("confidence", round(my_prob * 100))
        edge    = ai.get("edge_found", False)

        h_proj = pred["h_proj"]
        a_proj = pred["a_proj"]
        h_pct  = round(pred["h_prob"] * 100)
        a_pct  = 100 - h_pct

        win_odds = pred["h_odds"] if ai_side == "home" else pred["a_odds"]
        real_ev  = calc_ev(my_prob, win_odds)
        edge     = edge and real_ev is not None and real_ev > 0

        cc = "#16a34a" if conf >= 70 else "#d97706" if conf >= 58 else "#6b7280"

        proj_home_wins = h_proj >= a_proj
        h_score_style  = f"font-size:28px;font-weight:500;color:{'#111' if proj_home_wins else '#bbb'};"
        a_score_style  = f"font-size:28px;font-weight:500;color:{'#111' if not proj_home_wins else '#bbb'};"

        # Result badge
        result = pred.get("result") or gd.get("pick", {}).get("result")
        result_html = ""
        if result == "W":
            score_s     = pred.get("result_score") or gd.get("pick", {}).get("result_score", "")
            result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#dcfce7;color:#166534;margin-left:8px;">'
                f'✓ WIN{" · " + score_s if score_s else ""}</span>'
            )
        elif result == "L":
            score_s     = pred.get("result_score") or gd.get("pick", {}).get("result_score", "")
            result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#fee2e2;color:#991b1b;margin-left:8px;">'
                f'✗ LOSS{" · " + score_s if score_s else ""}</span>'
            )

        # Edge badge
        edge_html = ""
        if edge:
            edge_html = (
                f'<span style="font-size:11px;font-weight:500;padding:2px 8px;border-radius:20px;'
                f'background:#dcfce7;color:#166534;margin-left:6px;">'
                f'Edge {fmt_ev(real_ev)}</span>'
            )

        # Tight spread warning
        tight_spread = max(pred["h_prob"], pred["a_prob"]) < 0.60
        tight_html = ""
        if tight_spread:
            tight_html = (
                f'<span style="font-size:11px;font-weight:500;padding:2px 8px;border-radius:20px;'
                f'background:#fef3c7;color:#92400e;margin-left:6px;">'
                f'⚠️ Tight line</span>'
            )

        bet_is_underdog = (ai_side == "home") != proj_home_wins
        bet_label_style = (
            "background:#fef3c7;color:#92400e;" if bet_is_underdog
            else "background:#f0fdf4;color:#166534;"
        )

        # Injury section
        injuries = detail.get("injuries", [])
        if injuries:
            inj_rows = "".join(
                f'<div style="font-size:12px;color:#374151;padding:3px 0;'
                f'border-bottom:0.5px solid #f9fafb;">{inj}</div>'
                for inj in injuries[:8]
            )
            inj_html = (
                f'<div style="margin-top:14px;">'
                f'<div style="font-size:10px;font-weight:500;text-transform:uppercase;'
                f'letter-spacing:.07em;color:#9ca3af;margin-bottom:6px;">Injury report</div>'
                f'{inj_rows}</div>'
            )
        else:
            inj_html = '<div style="margin-top:14px;font-size:12px;color:#9ca3af;">No injuries reported</div>'

        # Props section
        if props:
            prop_rows = "".join(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:6px 0;border-bottom:0.5px solid #f9fafb;">'
                f'<div><span style="font-size:13px;font-weight:500;color:#111;">{p["player"]}</span>'
                f'<span style="font-size:11px;color:#9ca3af;margin-left:6px;">'
                f'{p["dir"]} {p["line"]} {p["stat"]}</span></div>'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'<span style="font-size:12px;color:#374151;">{fmt_odds(p.get("odds"))}</span>'
                f'<span style="font-size:12px;font-weight:500;color:{ev_color(p.get("ev"))};">'
                f'EV {fmt_ev(p.get("ev"))}</span>'
                f'</div></div>'
                for p in props
            )
            props_html = (
                f'<div style="margin-top:14px;">'
                f'<div style="font-size:10px;font-weight:500;text-transform:uppercase;'
                f'letter-spacing:.07em;color:#9ca3af;margin-bottom:6px;">Top props</div>'
                f'{prop_rows}</div>'
            )
        else:
            props_html = '<div style="margin-top:14px;font-size:12px;color:#9ca3af;">No props available</div>'

        # Total
        tot_lean   = ai.get("total_lean")
        tot_line   = pred.get("total_line", 224.0)
        tot_odds   = pred.get("over_odds") if tot_lean == "OVER" else pred.get("under_odds")
        tot_ev     = calc_ev(0.52, tot_odds)
        tot_reason = ai.get("total_reason", "")

        # Total result badge
        tot_result = gd.get("tot_result") or pred.get("tot_result")
        tot_result_html = ""
        if tot_result == "W":
            tot_result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 6px;border-radius:20px;'
                f'background:#dcfce7;color:#166534;margin-left:6px;">✓ HIT</span>'
            )
        elif tot_result == "L":
            tot_result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 6px;border-radius:20px;'
                f'background:#fee2e2;color:#991b1b;margin-left:6px;">✗ MISS</span>'
            )

        cards += f"""
<div style="background:#fff;border-radius:12px;border:0.5px solid #e5e7eb;margin-bottom:12px;overflow:hidden;">
  <div onclick="toggle({idx})" style="padding:16px 18px;cursor:pointer;user-select:none;">

    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span style="font-size:11px;color:#9ca3af;">{g["startTime"]}</span>
      <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;">
        <span style="font-size:13px;font-weight:500;color:{cc};">{conf}% confidence</span>
        {tight_html}
        {edge_html}
        {result_html}
      </div>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
      <div style="flex:1;min-width:0;">
        <div style="font-size:15px;font-weight:500;color:#111;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{g["awayTeam"]}</div>
        <div style="font-size:11px;color:#9ca3af;">{g["awayRec"]["summary"]} · Away</div>
        <div style="font-size:12px;font-weight:500;color:#374151;margin-top:2px;">{fmt_odds(pred.get("a_odds"))}</div>
      </div>
      <div style="text-align:center;padding:0 10px;flex-shrink:0;">
        <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">Projected</div>
        <div style="display:flex;align-items:center;gap:5px;">
          <span style="{a_score_style}">{a_proj}</span>
          <span style="font-size:14px;color:#d1d5db;">–</span>
          <span style="{h_score_style}">{h_proj}</span>
        </div>
      </div>
      <div style="flex:1;min-width:0;text-align:right;">
        <div style="font-size:15px;font-weight:500;color:#111;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{g["homeTeam"]}</div>
        <div style="font-size:11px;color:#9ca3af;">{g["homeRec"]["summary"]} · Home</div>
        <div style="font-size:12px;font-weight:500;color:#374151;margin-top:2px;">{fmt_odds(pred.get("h_odds"))}</div>
      </div>
    </div>

    <div style="margin-top:10px;">
      <div style="height:5px;background:#f3f4f6;border-radius:99px;overflow:hidden;display:flex;">
        <div style="width:{a_pct}%;background:#93c5fd;border-radius:99px 0 0 99px;"></div>
        <div style="width:{h_pct}%;background:{cc};border-radius:0 99px 99px 0;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;margin-top:3px;">
        <span>{g["awayAbbr"]} {a_pct}%</span>
        <span style="color:#374151;font-weight:500;">Proj: {g["homeAbbr"] if proj_home_wins else g["awayAbbr"]} wins</span>
        <span>{g["homeAbbr"]} {h_pct}%</span>
      </div>
    </div>

    <div style="margin-top:10px;border-top:0.5px solid #f3f4f6;padding-top:10px;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">{"VALUE BET — UNDERDOG" if bet_is_underdog else "MODEL PICK"}</div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-size:15px;font-weight:600;color:#111;">{ai_team}</span>
            <span style="font-size:14px;font-weight:500;padding:2px 10px;border-radius:20px;{bet_label_style}">{fmt_odds(win_odds)}</span>
            {"<span style='font-size:11px;color:#d97706;'>Proj. loser — book has them too cheap</span>" if bet_is_underdog else "<span style='font-size:11px;color:#16a34a;'>Proj. winner</span>"}
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:12px;font-weight:500;color:{ev_color(real_ev)};">EV {fmt_ev(real_ev)}</div>
          <div style="font-size:11px;color:#d1d5db;margin-top:4px;" id="hint{idx}">details ▾</div>
        </div>
      </div>
    </div>
  </div>

  <div id="body{idx}" style="display:none;border-top:0.5px solid #f3f4f6;padding:16px 18px;">

    <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.07em;color:#9ca3af;margin-bottom:6px;">Moneyline pick</div>
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
      <span style="font-size:19px;font-weight:500;color:#111;">{ai_team}</span>
      <span style="font-size:14px;font-weight:500;color:#374151;">{fmt_odds(win_odds)}</span>
      <span style="font-size:12px;color:#9ca3af;">book {round((1-pred["h_prob"] if ai_side=="away" else pred["h_prob"])*100)}% → model {round(my_prob*100)}%</span>
      <span style="font-size:13px;font-weight:500;color:{ev_color(real_ev)};">EV {fmt_ev(real_ev)}</span>
    </div>
    <div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">EV = expected value per $100 using model probability vs book price</div>
    <div style="font-size:13px;color:#374151;line-height:1.65;background:#f9fafb;border-radius:8px;padding:10px 12px;">{ai.get("reasoning", "—")}</div>
    {"<div style='font-size:11px;color:#f59e0b;margin-top:4px;'>⚠ No book odds — using team records</div>" if pred["prob_source"] != "odds" else ""}

    <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:8px;">
      <div style="background:#f9fafb;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">{g["awayAbbr"]} ML</div>
        <div style="font-size:14px;font-weight:500;color:#111;">{fmt_odds(pred.get("a_odds"))}</div>
        <div style="font-size:12px;color:{ev_color(calc_ev(my_prob if ai_side=="away" else 1-my_prob, pred.get("a_odds")))};">EV {fmt_ev(calc_ev(my_prob if ai_side=="away" else 1-my_prob, pred.get("a_odds")))}</div>
      </div>
      <div style="background:#f9fafb;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:11px;color:#9ca3af;margin-bottom:2px;">{g["homeAbbr"]} ML</div>
        <div style="font-size:14px;font-weight:500;color:#111;">{fmt_odds(pred.get("h_odds"))}</div>
        <div style="font-size:12px;color:{ev_color(calc_ev(my_prob if ai_side=="home" else 1-my_prob, pred.get("h_odds")))};">EV {fmt_ev(calc_ev(my_prob if ai_side=="home" else 1-my_prob, pred.get("h_odds")))}</div>
      </div>
    </div>

    {f'''<div style="margin-top:14px;">
      <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.07em;color:#9ca3af;margin-bottom:6px;">Total points</div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:16px;font-weight:500;color:#111;">{tot_lean} {tot_line}</span>
        <span style="font-size:12px;color:#374151;">{fmt_odds(tot_odds)}</span>
        <span style="font-size:12px;font-weight:500;color:{ev_color(tot_ev)};">EV {fmt_ev(tot_ev)}</span>
        {tot_result_html}
      </div>
      {f'<div style="font-size:12px;color:#6b7280;margin-top:4px;">{tot_reason}</div>' if tot_reason else ""}
    </div>''' if tot_lean else ''}

    {inj_html}
    {props_html}

    <div style="text-align:center;margin-top:14px;">
      <span onclick="toggle({idx})" style="font-size:11px;color:#d1d5db;cursor:pointer;">collapse ▴</span>
    </div>
  </div>
</div>"""


    # ── O/U cards ──────────────────────────────────────────────────────────────
    ou_cards = ""
    ou_sorted = sorted(
        [gd for gd in games_data if gd["ai"].get("total_lean")],
        key=lambda gd: gd["ai"].get("total_confidence") or 0,
        reverse=True
    )
    for idx, gd in enumerate(ou_sorted):
        g        = gd["game"]
        pred     = gd["pred"]
        ai       = gd["ai"]
        tot_lean = ai.get("total_lean")

        tot_line   = pred.get("total_line")
        tot_odds   = pred.get("over_odds") if tot_lean == "OVER" else pred.get("under_odds")
        tot_reason = ai.get("total_reason", "")
        tot_ev     = calc_ev(0.52, tot_odds)
        tot_result = gd.get("tot_result") or pred.get("tot_result")

        is_over    = tot_lean == "OVER"
        accent     = "#2563eb" if is_over else "#7c3aed"
        lean_icon  = "⬆" if is_over else "⬇"
        lean_bg    = "#eff6ff" if is_over else "#f5f3ff"
        lean_bdr   = "#bfdbfe" if is_over else "#ddd6fe"

        ou_result_html = ""
        if tot_result == "W":
            ou_result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#dcfce7;color:#166534;">✓ HIT</span>'
            )
        elif tot_result == "L":
            ou_result_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#fee2e2;color:#991b1b;">✗ MISS</span>'
            )

        tot_conf = ai.get("total_confidence")
        ev_str = f"EV {fmt_ev(tot_ev)}" if tot_ev is not None else ""
        ev_col = ev_color(tot_ev) if tot_ev is not None else "#9ca3af"

        ou_cards += f"""
<div style="background:#fff;border-radius:12px;border:0.5px solid #e5e7eb;margin-bottom:12px;overflow:hidden;">
  <div style="padding:16px 18px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
      <span style="font-size:11px;color:#9ca3af;">{g["startTime"]}</span>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:13px;font-weight:500;color:{'#16a34a' if (tot_conf or 0)>=70 else '#d97706' if (tot_conf or 0)>=58 else '#6b7280'};">{tot_conf or '—'}% confidence</span>
        {ou_result_html}
      </div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:12px;">
      <div style="flex:1;min-width:0;">
        <div style="font-size:13px;font-weight:500;color:#111;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{g["awayTeam"]}</div>
        <div style="font-size:11px;color:#9ca3af;">{g["awayRec"]["summary"]} · Away</div>
      </div>
      <div style="font-size:11px;color:#9ca3af;padding:0 8px;">@</div>
      <div style="flex:1;min-width:0;text-align:right;">
        <div style="font-size:13px;font-weight:500;color:#111;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{g["homeTeam"]}</div>
        <div style="font-size:11px;color:#9ca3af;">{g["homeRec"]["summary"]} · Home</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 14px;border-radius:10px;background:{lean_bg};border:0.5px solid {lean_bdr};">
      <span style="font-size:20px;font-weight:600;color:{accent};">{lean_icon} {tot_lean}</span>
      <span style="font-size:18px;font-weight:500;color:#111;">{tot_line}</span>
      <span style="font-size:13px;color:#374151;">{fmt_odds(tot_odds)}</span>
      <span style="font-size:13px;font-weight:500;color:{ev_col};">{ev_str}</span>
    </div>
    {f'<div style="font-size:13px;color:#374151;line-height:1.65;margin-top:10px;padding:10px 12px;background:#f9fafb;border-radius:8px;">{tot_reason}</div>' if tot_reason else ""}
  </div>
</div>"""

    # ── Props record board ────────────────────────────────────────────────────
    pr_type   = record.get("by_type", {}).get("prop", {"W": 0, "L": 0})
    pr_total  = pr_type.get("W", 0) + pr_type.get("L", 0)
    pr_wr     = round(pr_type.get("W", 0) / pr_total * 100, 1) if pr_total else None
    pr_wrc    = "#16a34a" if (pr_wr or 0) >= 65 else "#d97706" if (pr_wr or 0) >= 52 else "#6b7280"
    pr_conf_cells = "".join(_prop_conf_cell(record, cb) for cb in ["50-59", "60-69", "70-79", "80+"])

    prop_rec_html = f"""
<div style="background:#f9fafb;border-radius:12px;border:0.5px solid #e5e7eb;padding:16px 18px;margin-bottom:20px;">
  <div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:12px;">Model record · Player Props</div>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px;">
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">All time props</div>
      <div style="font-size:22px;font-weight:500;color:#111;">{pr_type.get('W',0)}-{pr_type.get('L',0)}</div>
      <div style="font-size:11px;color:{pr_wrc};">{f'{pr_wr}%' if pr_wr else '—'}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:10px;color:#9ca3af;margin-bottom:3px;">Target</div>
      <div style="font-size:14px;font-weight:500;color:#111;">65%+</div>
      <div style="font-size:11px;color:#9ca3af;">Break-even 52.4%</div>
    </div>
  </div>
  <div style="height:5px;background:#e5e7eb;border-radius:99px;overflow:hidden;margin-bottom:4px;">
    <div style="width:{pr_wr or 0}%;height:100%;background:{pr_wrc};border-radius:99px;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;margin-bottom:12px;">
    <span>Hit rate</span><span>Sorted by confidence below</span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
    {pr_conf_cells}
  </div>
</div>"""

    # ── Props cards ────────────────────────────────────────────────────────────
    prop_cards = ""
    all_props  = []
    for gd in games_data:
        g  = gd["game"]
        ai = gd["ai"]
        for prop in ai.get("prop_picks", []):
            all_props.append({"game": g, "prop": prop})

    all_props.sort(key=lambda x: x["prop"].get("confidence") or 0, reverse=True)

    for item in all_props:
        g    = item["game"]
        prop = item["prop"]
        pconf     = prop.get("confidence") or 0
        pdir      = prop.get("dir", "OVER")
        pplayer   = prop.get("player", "")
        pstat     = prop.get("stat", "")
        pline     = prop.get("line", 0)
        podds     = prop.get("odds")
        preason   = prop.get("reasoning", "")
        presult   = prop.get("prop_result")
        pactual   = prop.get("actual")

        is_over   = pdir == "OVER"
        accent    = "#2563eb" if is_over else "#7c3aed"
        lean_icon = "⬆" if is_over else "⬇"
        lean_bg   = "#eff6ff" if is_over else "#f5f3ff"
        lean_bdr  = "#bfdbfe" if is_over else "#ddd6fe"
        conf_col  = "#16a34a" if pconf >= 70 else "#d97706" if pconf >= 58 else "#6b7280"

        pev       = calc_ev(0.52, podds) if podds else None
        ev_str    = f"EV {fmt_ev(pev)}" if pev is not None else ""
        ev_col    = ev_color(pev)

        presult_html = ""
        if presult == "W":
            actual_str = f" · {pactual} actual" if pactual is not None else ""
            presult_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#dcfce7;color:#166534;">✓ HIT{actual_str}</span>'
            )
        elif presult == "L":
            actual_str = f" · {pactual} actual" if pactual is not None else ""
            presult_html = (
                f'<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;'
                f'background:#fee2e2;color:#991b1b;">✗ MISS{actual_str}</span>'
            )

        prop_cards += f"""
<div style="background:#fff;border-radius:12px;border:0.5px solid #e5e7eb;margin-bottom:12px;overflow:hidden;">
  <div style="padding:16px 18px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span style="font-size:11px;color:#9ca3af;">{g["awayAbbr"]} @ {g["homeAbbr"]} · {g.get("startTime","")}</span>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:12px;font-weight:500;color:{conf_col};">{pconf}% conf</span>
        {presult_html}
      </div>
    </div>
    <div style="font-size:16px;font-weight:600;color:#111;margin-bottom:8px;">{pplayer}</div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;border-radius:10px;background:{lean_bg};border:0.5px solid {lean_bdr};">
      <span style="font-size:18px;font-weight:600;color:{accent};">{lean_icon} {pdir}</span>
      <span style="font-size:16px;font-weight:500;color:#111;">{pline} {pstat}</span>
      <span style="font-size:13px;color:#374151;">{fmt_odds(podds)}</span>
      <span style="font-size:12px;font-weight:500;color:{ev_col};">{ev_str}</span>
    </div>
    {f'<div style="font-size:12px;color:#374151;line-height:1.65;margin-top:10px;padding:10px 12px;background:#f9fafb;border-radius:8px;">{preason}</div>' if preason else ""}
  </div>
</div>"""

    # ── Page skeleton ──────────────────────────────────────────────────────────
    no_games = """
<div style="text-align:center;padding:60px 20px;">
  <div style="font-size:40px;margin-bottom:12px;">🏀</div>
  <div style="font-size:16px;font-weight:500;color:#374151;">No games for this date</div>
</div>"""

    display_date = active_date or str(td)
    try:
        date_label = datetime.strptime(display_date, "%Y-%m-%d").strftime("%A, %B %d %Y")
    except:
        date_label = display_date

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>NBA AI Predictor</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;color:#111;min-height:100vh}}
  .wrap{{max-width:680px;margin:0 auto;padding:20px 14px 60px}}
  a{{cursor:pointer}}
  @media(max-width:480px){{.wrap{{padding:14px 10px 40px}}}}
</style>
</head>
<body>
<div class="wrap">
  <div style="margin-bottom:20px;">
    <h1 style="font-size:22px;font-weight:500;">🏀 NBA AI Predictor</h1>
    <div style="font-size:13px;color:#9ca3af;margin-top:3px;">{date_label} · {len(games_data)} games</div>
  </div>
  {rec_html}
  {day_tabs}

  <div style="display:flex;gap:6px;margin-bottom:16px;">
    <button onclick="showTab('ml')" id="tab-ml"
      style="flex:1;padding:9px 0;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:600;background:#111;color:#fff;">
      📊 ML
    </button>
    <button onclick="showTab('ou')" id="tab-ou"
      style="flex:1;padding:9px 0;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:600;background:#f3f4f6;color:#374151;">
      📈 O/U
    </button>
    <button onclick="showTab('props')" id="tab-props"
      style="flex:1;padding:9px 0;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:600;background:#f3f4f6;color:#374151;">
      🎯 Props
    </button>
  </div>

  <div id="section-ml">
    <div style="display:flex;justify-content:flex-end;margin-bottom:12px;font-size:11px;color:#9ca3af;gap:5px;">
      EV: <span style="color:#16a34a;">+8 excellent</span> ·
      <span style="color:#65a30d;">+3 good</span> ·
      <span style="color:#d97706;">marginal</span> ·
      <span style="color:#dc2626;">neg = skip</span>
    </div>
    {cards if cards else no_games}
  </div>

  <div id="section-ou" style="display:none;">
    {tot_html}
    {ou_cards if ou_cards else no_games}
  </div>

  <div id="section-props" style="display:none;">
    {prop_rec_html}
    {prop_cards if prop_cards else no_games}
  </div>
  <div style="margin-top:20px;padding:12px 14px;background:#fffbeb;border-radius:8px;border:0.5px solid #fde68a;">
    <p style="font-size:11px;color:#92400e;line-height:1.6;">AI-generated picks for informational purposes only. Always gamble responsibly.</p>
  </div>
</div>
<script>
function toggle(i){{
  var b=document.getElementById('body'+i);
  var h=document.getElementById('hint'+i);
  var o=b.style.display!=='none';
  b.style.display=o?'none':'block';
  h.innerHTML=o?'tap for details &#9662;':'collapse &#9652;';
}}
function showTab(t){{
  ['ml','ou','props'].forEach(function(id){{
    var active = t===id;
    document.getElementById('section-'+id).style.display = active?'block':'none';
    document.getElementById('tab-'+id).style.background  = active?'#111':'#f3f4f6';
    document.getElementById('tab-'+id).style.color       = active?'#fff':'#374151';
  }});
}}
</script>
</body>
</html>"""