"""
record.py — Load, save, and update the running W/L record.
"""
import json
import os
from datetime import datetime
from config import RECORD_FILE

def load_record():
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE) as f:
            return json.load(f)
    return {
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
        "by_conf_ou": {
            "50-59": {"W": 0, "L": 0, "pnl": 0.0},
            "60-69": {"W": 0, "L": 0, "pnl": 0.0},
            "70-79": {"W": 0, "L": 0, "pnl": 0.0},
            "80+":   {"W": 0, "L": 0, "pnl": 0.0},
        },
    }

def save_record(r):
    with open(RECORD_FILE, "w") as f:
        json.dump(r, f, indent=2)

def add_result(rec, result, btype, ds, conf=None, odds=None, tot_dir=None):
    """
    Record a single graded result.
    result  : "W" or "L"
    btype   : "ml", "total", or "prop"
    ds      : date string "YYYY-MM-DD"
    conf    : confidence integer (e.g. 68)
    odds    : American odds integer (e.g. -325 or +270)
    tot_dir : "OVER" or "UNDER" (for total picks)
    """
    if result not in ("W", "L"):
        return

    rec["alltime"][result] = rec["alltime"].get(result, 0) + 1

    # By day
    rec["by_day"].setdefault(ds, {"W": 0, "L": 0})[result] += 1

    # By week
    d  = datetime.strptime(ds, "%Y-%m-%d")
    wk = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
    rec["by_week"].setdefault(wk, {"W": 0, "L": 0})[result] += 1

    # By month
    rec["by_month"].setdefault(ds[:7], {"W": 0, "L": 0})[result] += 1

    # By bet type
    if btype in rec.get("by_type", {}):
        rec["by_type"][btype][result] = rec["by_type"][btype].get(result, 0) + 1

    # By confidence bucket with $10 flat-bet P&L (ML only)
    if conf is not None and btype == "ml":
        if conf >= 80:
            cb = "80+"
        elif conf >= 70:
            cb = "70-79"
        elif conf >= 60:
            cb = "60-69"
        else:
            cb = "50-59"
        bucket = rec.setdefault("by_conf", {}).setdefault(
            cb, {"W": 0, "L": 0, "pnl": 0.0}
        )
        bucket[result] = bucket.get(result, 0) + 1
        if odds is not None:
            try:
                o = float(odds)
                if result == "W":
                    profit = 10 * (100 / abs(o)) if o < 0 else 10 * (o / 100)
                else:
                    profit = -10.0
                bucket["pnl"] = round(bucket.get("pnl", 0.0) + profit, 2)
            except:
                pass

    # By prop confidence bucket with P&L
    if conf is not None and btype == "prop":
        if conf >= 80:
            cb = "80+"
        elif conf >= 70:
            cb = "70-79"
        elif conf >= 60:
            cb = "60-69"
        else:
            cb = "50-59"
        bucket = rec.setdefault("by_conf_prop", {}).setdefault(
            cb, {"W": 0, "L": 0, "pnl": 0.0}
        )
        bucket[result] = bucket.get(result, 0) + 1
        if odds is not None:
            try:
                o = float(odds)
                if result == "W":
                    profit = 10 * (100 / abs(o)) if o < 0 else 10 * (o / 100)
                else:
                    profit = -10.0
                bucket["pnl"] = round(bucket.get("pnl", 0.0) + profit, 2)
            except:
                pass

    # By O/U confidence bucket with P&L
    if conf is not None and btype == "total":
        if conf >= 80:
            cb = "80+"
        elif conf >= 70:
            cb = "70-79"
        elif conf >= 60:
            cb = "60-69"
        else:
            cb = "50-59"
        bucket = rec.setdefault("by_conf_ou", {}).setdefault(
            cb, {"W": 0, "L": 0, "pnl": 0.0}
        )
        bucket[result] = bucket.get(result, 0) + 1
        if odds is not None:
            try:
                o = float(odds)
                if result == "W":
                    profit = 10 * (100 / abs(o)) if o < 0 else 10 * (o / 100)
                else:
                    profit = -10.0
                bucket["pnl"] = round(bucket.get("pnl", 0.0) + profit, 2)
            except:
                pass

    # By total direction (OVER/UNDER) with P&L
    if btype == "total" and tot_dir in ("OVER", "UNDER"):
        rec.setdefault("by_conf_total", {
            "OVER":  {"W": 0, "L": 0, "pnl": 0.0},
            "UNDER": {"W": 0, "L": 0, "pnl": 0.0},
        })
        tb = rec["by_conf_total"].setdefault(
            tot_dir, {"W": 0, "L": 0, "pnl": 0.0}
        )
        tb[result] = tb.get(result, 0) + 1
        if odds is not None:
            try:
                o = float(odds)
                if result == "W":
                    profit = 10 * (100 / abs(o)) if o < 0 else 10 * (o / 100)
                else:
                    profit = -10.0
                tb["pnl"] = round(tb.get("pnl", 0.0) + profit, 2)
            except:
                pass