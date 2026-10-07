"""WG Craft inspection acts automation - entry point.

Usage:
    python main.py --dry-run      # no browser: list the acts that would be processed
    python main.py                # process all pending acts
    python main.py --limit 20     # process only the first 20 pending acts

Settings: config.json, selectors.json, .env
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException

from browser import Browser
import inspection_acts as acts_flow

BASE = Path(__file__).parent
MAX_ERRORS_IN_ROW = 5


def load_json(name):
    with open(BASE / name, encoding="utf-8") as f:
        return json.load(f)


def read_acts(cfg, excel_path):
    """Read (excel_row, act_number) pairs from the Excel file."""
    df = pd.read_excel(excel_path, sheet_name=cfg.get("sheet", 0), dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    col = cfg["act_column"]
    if col not in df.columns:
        sys.exit(f"Column '{col}' not found in Excel. Available columns: {list(df.columns)}")

    start, end = cfg.get("start_row") or 2, cfg.get("end_row")
    acts = []
    for i, val in df[col].items():
        row = i + 2  # row 1 is the header
        if row < start or (end and row > end):
            continue
        if isinstance(val, str) and val.strip():
            acts.append((row, val.strip()))
    return acts


def load_done(results_path):
    """Acts already processed successfully (skipped on the next run)."""
    if not results_path.exists():
        return set()
    with open(results_path, encoding="utf-8-sig") as f:
        return {r["act"] for r in csv.DictReader(f) if r["status"] == acts_flow.OK}


def write_result(results_path, row, act, status, message):
    new = not results_path.exists()
    with open(results_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "excel_row", "act", "status", "message"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row, act, status, message])


def main():
    ap = argparse.ArgumentParser(description="Accept new inspection acts and confirm their GPS records.")
    ap.add_argument("--excel", help="path to the Excel file (default: excel_file in config.json)")
    ap.add_argument("--limit", type=int, help="process only this many pending acts")
    ap.add_argument("--dry-run", action="store_true", help="no browser: only list the pending acts")
    args = ap.parse_args()

    cfg, sel = load_json("config.json"), load_json("selectors.json")
    excel_path = Path(args.excel) if args.excel else BASE / cfg["excel_file"]
    if not excel_path.exists():
        sys.exit(f"Excel file not found: {excel_path}")

    log_dir = BASE / cfg.get("log_dir", "logs")
    log_dir.mkdir(exist_ok=True)
    results_path = log_dir / cfg.get("results_file", "results.csv")

    done = load_done(results_path)
    acts = [(r, a) for r, a in read_acts(cfg, excel_path) if a not in done]
    limit = args.limit or cfg.get("limit")
    if limit:
        acts = acts[:limit]
    if not acts:
        sys.exit("No pending acts left.")

    print(f"Pending acts: {len(acts)} ({len(done)} already done were skipped)\n")

    if args.dry_run:
        for row, act in acts[:50]:
            print(f"  row {row}: {act}")
        if len(acts) > 50:
            print(f"  ... and {len(acts) - 50} more")
        return

    load_dotenv(BASE / ".env")
    cfg["url"] = os.getenv("WGCRAFT_URL") or cfg.get("url")
    user, pwd = os.getenv("WGCRAFT_LOGIN"), os.getenv("WGCRAFT_PASSWORD")
    if not cfg["url"] or not user or not pwd:
        sys.exit(".env must contain WGCRAFT_URL, WGCRAFT_LOGIN and WGCRAFT_PASSWORD (see .env.example).")

    b = Browser(cfg, sel)
    stats = {}
    errors_in_row = 0
    try:
        b.login(user, pwd)
        for n, (row, act) in enumerate(acts, 1):
            print(f"[{n}/{len(acts)}] Row {row}: {act}")
            try:
                status, message = acts_flow.process_act(b, act, cfg["note_text"])
            except Exception as e:  # noqa: BLE001 - log any failure and move on
                status, message = acts_flow.ERROR, f"{type(e).__name__}: {str(e)[:150]}"
                b.screenshot(str(log_dir / f"error_{act}.png"))
                b.save_page(str(log_dir / f"error_{act}.html"))
                b.press_escape(3)
                b.reload_home()
            print(f"    = {status}: {message}\n")
            write_result(results_path, row, act, status, message)
            stats[status] = stats.get(status, 0) + 1

            errors_in_row = errors_in_row + 1 if status == acts_flow.ERROR else 0
            if errors_in_row >= MAX_ERRORS_IN_ROW:
                print(f"{MAX_ERRORS_IN_ROW} errors in a row - stopping.")
                print("Check the latest screenshot and HTML in the logs folder.")
                break
    except TimeoutException as e:
        print(f"\nSTOPPED: {e.msg}")
        b.screenshot(str(log_dir / "stopped_here.png"))
        b.save_page(str(log_dir / "stopped_here.html"))
        print(f"Screenshot and page HTML saved to: {log_dir}")
    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C). Run again to resume.")
    finally:
        print("Summary:", ", ".join(f"{k}: {v}" for k, v in stats.items()) or "nothing processed")
        print(f"Results: {results_path}")
        input("Press [Enter] to close the browser...")
        b.quit()


if __name__ == "__main__":
    main()
