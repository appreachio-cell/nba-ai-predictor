"""
groq_ai.py — OpenRouter free tier drop-in replacement for claude_ai.py.
Uses Llama 3.3 70B via OpenRouter. Completely free.
"""

import json, re, time
import urllib.request
from datetime import date as _date

from utils import today_str, fmt_odds

OPENROUTER_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/auto"


def groq_analyze_all(games_info):
    today       = _date.today()
    is_playoffs = today.month > 4 or (today.month == 4 and today.day >= 19)
    game_type   = "PLAYOFF" if is_playoffs else "regular season"

    game_lines = []
    for i, gi in enumerate(games_info):
        g      = gi["game"]
        pred   = gi["pred"]
        detail = gi["detail"]
        h_rec  = g["homeRec"]
        a_rec  = g["awayRec"]
        inj    = "; ".join(detail.get("injuries", [])[:6]) or "none reported"
        has_o  = pred["prob_source"] == "odds"
        bh     = round(pred["h_prob"] * 100)
        ba     = round(pred["a_prob"] * 100)

        odds_str = (
            f"{g['awayAbbr']} {fmt_odds(pred['a_odds'])} ({ba}% implied) "
            f"vs {g['homeAbbr']} {fmt_odds(pred['h_odds'])} ({bh}% implied)"
        ) if has_o else (
            f"no book odds — records: "
            f"{g['awayAbbr']} {a_rec['summary']} vs {g['homeAbbr']} {h_rec['summary']}"
        )

        b2b_notes = []
        if g.get("home_b2b"): b2b_notes.append(f"{g['homeAbbr']} B2B")
        if g.get("away_b2b"): b2b_notes.append(f"{g['awayAbbr']} B2B")
        b2b_str = " | ⚠ " + ", ".join(b2b_notes) if b2b_notes else ""

        # Use PrizePicks props for prompt (guaranteed to exist in PP for backfill)
        props_list = gi.get("pp_props") or gi.get("props", [])
        props_list = props_list[:4]
        if props_list:
            print(f"    Props for GAME {i+1}: {[(p['player'], p['stat'], p['line']) for p in props_list]}")
        else:
            print(f"    No props for GAME {i+1}")
        if props_list:
            prop_lines = []
            for p in props_list:
                ctx = p.get("search_ctx", "")
                prop_lines.append(
                    f"{p['player']} {p['stat']} line={p['line']}"
                    + (f" [context: {ctx[:150]}]" if ctx else "")
                )
            props_ctx = " | Available props: " + "; ".join(prop_lines)
        else:
            props_ctx = ""

        prop_ctx = gi.get("prop_ctx", "")

        game_lines.append(
            f"GAME {i+1}: {g['awayTeam']} ({a_rec['summary']}) @ "
            f"{g['homeTeam']} ({h_rec['summary']}) | "
            f"{odds_str} | total line: {pred['total_line']} | "
            f"injuries: {inj}{b2b_str}{props_ctx}{prop_ctx}"
        )

    playoff_notes = (
        "These are playoff games. Weight series momentum, home court (59% win rate), "
        "rest days, and elimination game motivation.\n\n"
    ) if is_playoffs else ""

    prompt = (
        f"Today is {today_str()}. Analyze these {len(games_info)} NBA {game_type} games.\n\n"
        + "\n".join(game_lines) + "\n\n"
        + playoff_notes
        + "Rules:\n"
        + "1. Only raise ML confidence above implied odds if you have a clear reason\n"
        + "2. total_lean MUST be OVER or UNDER for every game\n"
        + "3. total_confidence MUST be an integer 50-95 for every game\n"
        + "4. prop_picks: only include props with genuine edge, use [] if none\n\n"
        + "Return ONLY a raw JSON array, no markdown, no explanation:\n"
        + '[{"game":1,"pick":"home","pick_team":"Cleveland Cavaliers","my_prob":0.78,'
        + '"confidence":75,"reasoning":"CLE dominant at home, TOR missing key players.",'
        + '"total_lean":"UNDER","total_confidence":65,'
        + '"total_reason":"Both teams play slow half-court offense.",'
        + '"prop_picks":[]}]'
    )

    def fallbacks():
        return [{
            "game":             i + 1,
            "pick":             "home" if gi["pred"]["h_prob"] >= gi["pred"]["a_prob"] else "away",
            "pick_team":        gi["game"]["homeTeam"] if gi["pred"]["h_prob"] >= gi["pred"]["a_prob"] else gi["game"]["awayTeam"],
            "my_prob":          max(gi["pred"]["h_prob"], gi["pred"]["a_prob"]),
            "confidence":       round(max(gi["pred"]["h_prob"], gi["pred"]["a_prob"]) * 100),
            "reasoning":        "Model pick (OpenRouter unavailable).",
            "edge_found":       False,
            "total_lean":       None,
            "total_confidence": None,
            "total_reason":     "",
            "prop_picks":       [],
        } for i, gi in enumerate(games_info)]

    for attempt in range(3):
        try:
            if attempt > 0:
                wait = 20 * attempt
                print(f"  Retrying OpenRouter in {wait}s (attempt {attempt + 1})...")
                time.sleep(wait)

            body = json.dumps({
                "model": OPENROUTER_MODEL,
                "max_tokens": 2048,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an expert NBA analyst. Output valid JSON only. "
                            "No markdown fences, no explanation — ONLY the raw JSON array. "
                            "total_lean and total_confidence are required for every game object."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
            }).encode()

            req = urllib.request.Request(
                OPENROUTER_URL,
                data=body,
                headers={
                    "Content-Type":    "application/json",
                    "Authorization":   f"Bearer {OPENROUTER_KEY}",
                    "HTTP-Referer":    "https://openrouter.ai",
                    "X-Title":         "NBA AI Predictor",
                    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept":          "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())

            text = resp["choices"][0]["message"]["content"].strip()
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text).strip()

            m = re.search(r"\[[\s\S]+\]", text)
            if not m:
                raise ValueError(f"No JSON array: {text[:200]}")

            arr = json.loads(m.group(0))
            if len(arr) != len(games_info):
                raise ValueError(f"Expected {len(games_info)}, got {len(arr)}")

            ou_count   = sum(1 for r in arr if r.get("total_lean"))
            prop_count = sum(len(r.get("prop_picks", [])) for r in arr)
            print(f"  OpenRouter ✓ ({len(arr)} games | O/U: {ou_count} | Props: {prop_count})")
            return arr

        except urllib.error.HTTPError as e:
            err = e.read().decode()
            if e.code == 429:
                print(f"  OpenRouter HTTP 429 full response: {err}")
                time.sleep(30)
                continue
            print(f"  OpenRouter HTTP {e.code} full response: {err}")
            break
        except Exception as e:
            print(f"  OpenRouter error (attempt {attempt + 1}): {e}")
            if attempt == 2:
                break

    print("  OpenRouter failed — using model fallback")
    return fallbacks()