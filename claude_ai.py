"""
claude_ai.py — Batched Claude Sonnet call with web search for all games.
One API call per run; retries with back-off on rate limits.
"""

import json, re, time
import urllib.request

from config import ANTHROPIC_KEY
from utils import today_str, fmt_odds


def claude_analyze_all(games_info):
    """
    Analyze ALL games in ONE Claude call with web search.

    Parameters
    ----------
    games_info : list of dicts, each with keys: game, pred, detail, props

    Returns
    -------
    list of ai result dicts in the same order as games_info
    """
    game_lines = []
    for i, gi in enumerate(games_info):
        g      = gi["game"]
        pred   = gi["pred"]
        detail = gi["detail"]
        h_rec  = g["homeRec"]
        a_rec  = g["awayRec"]
        inj    = "; ".join(detail.get("injuries", [])[:4]) or "none reported by ESPN"
        has_o  = pred["prob_source"] == "odds"
        bh     = round(pred["h_prob"] * 100)
        ba     = round(pred["a_prob"] * 100)

        if has_o:
            odds_str = (
                f"{g['awayAbbr']} {fmt_odds(pred['a_odds'])} ({ba}% implied) "
                f"vs {g['homeAbbr']} {fmt_odds(pred['h_odds'])} ({bh}% implied)"
            )
        else:
            odds_str = (
                f"no book odds, records: "
                f"{g['awayAbbr']} {a_rec['summary']} vs {g['homeAbbr']} {h_rec['summary']}"
            )

        # Back-to-back flags
        b2b_notes = []
        if g.get("home_b2b"):
            b2b_notes.append(f"{g['homeAbbr']} on B2B")
        if g.get("away_b2b"):
            b2b_notes.append(f"{g['awayAbbr']} on B2B")
        b2b_str = " | ⚠ " + ", ".join(b2b_notes) if b2b_notes else ""

        # Top props for this game
        props_list = gi.get("props", [])[:4]
        if props_list:
            prop_strs = [
                f"{p['player']} {p['dir']} {p['line']} {p['stat']} ({fmt_odds(p.get('odds'))})"
                for p in props_list
            ]
            props_ctx = " | Props: " + "; ".join(prop_strs)
        else:
            props_ctx = ""

        game_lines.append(
            f"GAME {i + 1}: {g['awayTeam']} ({a_rec['summary']}) @ "
            f"{g['homeTeam']} ({h_rec['summary']}) | "
            f"{odds_str} | total line: {pred['total_line']} | "
            f"ESPN injuries: {inj}{b2b_str}{props_ctx}"
        )

    prompt = (
        f"Today is {today_str()}. Analyze these {len(games_info)} NBA games.\n\n"
        + "\n".join(game_lines)
        + "\n\nDo ONE web search for today's NBA injury report to cover all teams at once, "
        + "then analyze each game using what you find.\n\n"
        + "IMPORTANT FACTORS TO WEIGH:\n"
        + "1. Injuries — especially star players (20+ PPG) missing significantly shifts win probability\n"
        + "2. Back-to-back fatigue — teams marked ⚠ B2B played last night. "
        + "B2B teams underperform the spread by 2-3 points on average. "
        + "Factor this into both your pick and your confidence level.\n"
        + "3. Only increase confidence above the implied odds if you have a clear reason "
        + "(injury edge, B2B disadvantage, etc.)\n\n"
        + "Return a JSON ARRAY with one object per game in order:\n"
        + '[{"game":1,"pick":"home or away","pick_team":"full name","my_prob":0.62,'
        + '"confidence":68,"reasoning":"1-2 sentences on key injuries/B2B/edge found",'
        + '"total_lean":"OVER or UNDER or null","total_reason":"one sentence or null",'
        + '"edge_found":true or false,"prop_picks":[{"player":"full name","stat":"Points","line":22.5,"dir":"OVER or UNDER","confidence":68,"reasoning":"one sentence","odds":-115}] or []}, ...]'
    )

    def fallbacks():
        results = []
        for gi in games_info:
            pred = gi["pred"]
            side = "home" if pred["h_prob"] >= pred["a_prob"] else "away"
            g    = gi["game"]
            results.append({
                "pick":         side,
                "pick_team":    g["homeTeam"] if side == "home" else g["awayTeam"],
                "my_prob":      pred["h_prob"] if side == "home" else pred["a_prob"],
                "confidence":   round((pred["h_prob"] if side == "home" else pred["a_prob"]) * 100),
                "reasoning":    "Model pick (Claude unavailable).",
                "total_lean":   None,
                "total_reason": None,
                "edge_found":   False,
                "prop_picks":   [],
            })
        return results

    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 25 * attempt
                print(f"  Retrying in {wait}s (attempt {attempt + 1})...")
                time.sleep(wait)

            body = json.dumps({
                "model":      "claude-sonnet-4-5-20251001",
                "max_tokens": 2048,
                "tools":      [{"type": "web_search_20250305", "name": "web_search"}],
                "messages":   [{"role": "user", "content": prompt}],
            }).encode()

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=body,
                headers={
                    "Content-Type":      "application/json",
                    "x-api-key":         ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                resp = json.loads(r.read())

            text = " ".join(
                b.get("text", "")
                for b in resp.get("content", [])
                if b.get("type") == "text"
            ).strip()

            if not text:
                raise ValueError("Empty response from Claude")

            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text).strip()

            m = re.search(r"\[[\s\S]+\]", text)
            if not m:
                raise ValueError(f"No JSON array in response: {text[:300]}")

            arr = json.loads(m.group(0))
            if len(arr) != len(games_info):
                raise ValueError(
                    f"Expected {len(games_info)} results, got {len(arr)}"
                )

            return arr

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  Rate limited — waiting 30s...")
                time.sleep(30)
                continue
            try:
                err_body = e.read().decode()
                print(f"  Claude HTTP {e.code}: {err_body}")
            except:
                print(f"  Claude HTTP {e.code}: {e}")
            break
        except Exception as e:
            print(f"  Claude error (attempt {attempt + 1}): {e}")
            if attempt == 2:
                break

    return fallbacks()