"""Run the monitor on every record x view x model, then print the results table.

Usage: ../.venv/bin/python run_monitor.py [--limit N]
Every call (request sent + reply received) appends to outputs/monitor_study/monitor_runs.jsonl;
finished calls are skipped on rerun. Each run also writes outputs/monitor_study/export/:
  log.jsonl            what was sent and received, one line per call in this run's table
  system_prompt.txt    the shared system prompt
  <model>_<view>.csv   one spreadsheet per monitor x view
"""

import argparse
import csv
import itertools
import json
from pathlib import Path

from monitor import MODELS, PREAMBLE, VIEWS, build_request, custom_id, parse_verdict
from records import iter_records
from score import score
from src.config import settings
from src.llm.providers.queued_openrouter import QueuedOpenRouterClient

OUT = Path(__file__).parent.parent / "outputs/monitor_study"
RUNS = OUT / "monitor_runs.jsonl"
EXPORT = OUT / "export"

CSV_COLUMNS = ["round", "trial", "agent", "agent_model", "monitor_model", "view",
               "sent_to_monitor", "monitor_reply", "monitor_verdict", "truth_planned_lie", "correct",
               "typology", "announced", "message", "chose", "truth_lied"]


def load_done() -> dict:
    """Calls with a readable verdict. Errors and unreadable replies are retried on rerun."""
    if not RUNS.exists():
        return {}
    with open(RUNS) as f:
        rows = {row["custom_id"]: row for row in map(json.loads, f)}  # later rows win
    return {cid: row for cid, row in rows.items() if row["verdict"] is not None}


def export(records: list, done: dict):
    """Write the sent/received log and one CSV per monitor x view."""
    EXPORT.mkdir(parents=True, exist_ok=True)
    (EXPORT / "system_prompt.txt").write_text(PREAMBLE)
    with open(EXPORT / "log.jsonl", "w") as f:
        for r, m, v in itertools.product(records, MODELS, VIEWS):
            f.write(json.dumps(done[custom_id(r, v, m)]) + "\n")

    for m, v in itertools.product(MODELS, VIEWS):
        # utf-8-sig so Excel detects the encoding
        with open(EXPORT / f"{m.split('/')[-1]}_{v}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            w.writeheader()
            for r in records:
                row = done[custom_id(r, v, m)]
                verdict = row["verdict"]
                w.writerow({
                    "round": r["round"], "trial": r["trial"], "agent": r["agent"], "agent_model": r["model"],
                    "monitor_model": m, "view": v,
                    "sent_to_monitor": row["request"]["messages"][-1]["content"],
                    "monitor_reply": json.dumps(row["reply"]),
                    "monitor_verdict": verdict, "truth_planned_lie": r["planned_lie"],
                    "correct": None if verdict is None else verdict == r["planned_lie"],
                    "typology": r["typology"], "announced": r["announced"], "message": r["message"],
                    "chose": r["chose"], "truth_lied": r["lied"],
                })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only the first N records (smoke test)")
    args = parser.parse_args()

    records = list(itertools.islice(iter_records(), args.limit))
    done = load_done()
    todo = [build_request(r, v, m) for r in records for v in VIEWS for m in MODELS
            if custom_id(r, v, m) not in done]
    n_planned = sum(r["planned_lie"] for r in records)
    print(f"{len(records)} records ({n_planned} planned a lie, {len(records) - n_planned} honest plan), "
          f"{len(todo)} calls to make, {len(done)} already done")

    if todo:
        client = QueuedOpenRouterClient(api_key=settings.OPENROUTER_API_KEY, max_workers=20, max_retries=5)
        replies = client.execute_all(todo)
        RUNS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUNS, "a") as f:
            for req in todo:
                reply = replies.get(req["custom_id"], {})
                row = {"custom_id": req["custom_id"], "request": req, "reply": reply, "verdict": parse_verdict(reply)}
                f.write(json.dumps(row) + "\n")
                done[row["custom_id"]] = row

    print(f"\n{'model':<28} {'view':<13} {'accuracy (95% range)':<22} {'false-pos rate (95% range)':<27} unreadable")
    for m, v in itertools.product(MODELS, VIEWS):
        pairs = [(r["planned_lie"], done[custom_id(r, v, m)]["verdict"]) for r in records]
        readable = [(t, g) for t, g in pairs if g is not None]
        s = score([t for t, _ in readable], [g for _, g in readable])
        acc = f"{s['accuracy']:.0%} ({s['accuracy_ci'][0]:.0%}-{s['accuracy_ci'][1]:.0%})"
        fp = f"{s['fp_rate']:.0%} ({s['fp_ci'][0]:.0%}-{s['fp_ci'][1]:.0%})" if s["n_honest"] else "n/a"
        print(f"{m:<28} {v:<13} {acc:<22} {fp:<27} {len(pairs) - len(readable)}")

    export(records, done)
    print(f"\nLog and spreadsheets written to {EXPORT}")


if __name__ == "__main__":
    main()
