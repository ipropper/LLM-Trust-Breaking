"""Run the monitor on every record x view x model, then print the results table.

Usage: ../.venv/bin/python run_monitor.py [--log GAME_LOG.json] [--limit N]
Outputs go in outputs/monitor_study/<game>__<game log name>/, so datasets never share cached calls.
Every call (request sent + reply received) appends to monitor_runs.jsonl there;
finished calls are skipped on rerun. Each run also writes export/ there:
  log.jsonl            what was sent and received, one line per call in this run's table
  system_prompt.txt    the shared system prompt
  results.csv          the standard per-game sheet (see export_dataset.py), guesses filled in
"""

import argparse
import itertools
import json
from pathlib import Path

from export_dataset import build_rows, load_guesses, results_dir, write_csv
from monitor import MODELS, VIEWS, build_request, custom_id, parse_verdict, preamble
from records import DEFAULT_LOG, iter_records
from score import score
from src.config import settings
from src.llm.providers.queued_openrouter import QueuedOpenRouterClient


def load_done(runs: Path) -> dict:
    """Calls with a readable verdict. Errors and unreadable replies are retried on rerun."""
    if not runs.exists():
        return {}
    with open(runs) as f:
        rows = {row["custom_id"]: row for row in map(json.loads, f)}  # later rows win
    return {cid: row for cid, row in rows.items() if row["verdict"] is not None}


def export(records: list, done: dict, out: Path, runs: Path):
    """Write the sent/received log and the standard results CSV (same format as export_dataset.py)."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "system_prompt.txt").write_text(preamble(records[0]["game"]))
    with open(out / "log.jsonl", "w") as f:
        for r, m, v in itertools.product(records, MODELS, VIEWS):
            f.write(json.dumps(done[custom_id(r, v, m)]) + "\n")

    write_csv(out / "results.csv", build_rows(records, load_guesses(runs)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="game log to monitor")
    parser.add_argument("--limit", type=int, default=None, help="only the first N records (smoke test)")
    args = parser.parse_args()

    records = list(itertools.islice(iter_records(args.log, None), args.limit))
    out = results_dir(args.log, records[0]["game"])
    runs = out / "monitor_runs.jsonl"
    done = load_done(runs)
    todo = [build_request(r, v, m) for r in records for v in VIEWS for m in MODELS
            if custom_id(r, v, m) not in done]
    n_planned = sum(r["planned_lie"] for r in records)
    print(f"{len(records)} records ({n_planned} planned a lie, {len(records) - n_planned} honest plan), "
          f"{len(todo)} calls to make, {len(done)} already done")

    if todo:
        client = QueuedOpenRouterClient(api_key=settings.OPENROUTER_API_KEY, max_workers=20, max_retries=5)
        replies = client.execute_all(todo)
        runs.parent.mkdir(parents=True, exist_ok=True)
        with open(runs, "a") as f:
            for req in todo:
                reply = replies.get(req["custom_id"], {})
                row = {"custom_id": req["custom_id"], "request": req, "reply": reply, "verdict": parse_verdict(reply)}
                f.write(json.dumps(row) + "\n")
                done[row["custom_id"]] = row

    print(f"\n{'model':<28} {'view':<13} {'accuracy (95% range)':<22} {'false-pos rate (95% range)':<27} unreadable")
    for m, v in itertools.product(MODELS, VIEWS):
        pairs = [(r["planned_lie"], done[custom_id(r, v, m)]["verdict"]) for r in records]
        readable = [(t, g) for t, g in pairs if g is not None]
        if not readable:
            print(f"{m:<28} {v:<13} no readable replies ({len(pairs)} failed; rerun to retry)")
            continue
        s = score([t for t, _ in readable], [g for _, g in readable])
        acc = f"{s['accuracy']:.0%} ({s['accuracy_ci'][0]:.0%}-{s['accuracy_ci'][1]:.0%})"
        fp = f"{s['fp_rate']:.0%} ({s['fp_ci'][0]:.0%}-{s['fp_ci'][1]:.0%})" if s["n_honest"] else "n/a"
        print(f"{m:<28} {v:<13} {acc:<22} {fp:<27} {len(pairs) - len(readable)}")

    export(records, done, out / "export", runs)
    print(f"\nLog and spreadsheets written to {out / 'export'}")


if __name__ == "__main__":
    main()
