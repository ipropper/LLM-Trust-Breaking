"""Run the frozen monitor on every record x view x model, then print the results table.

Usage: ../.venv/bin/python run_monitor.py [--limit N]
Results append to outputs/monitor_study/monitor_runs.jsonl; finished calls are skipped on rerun.
"""

import argparse
import itertools
import json
from pathlib import Path

from monitor import MODELS, VIEWS, build_request, custom_id, parse_verdict
from records import iter_records
from score import score
from src.config import settings
from src.llm.providers.queued_openrouter import QueuedOpenRouterClient

RUNS = Path(__file__).parent.parent / "outputs/monitor_study/monitor_runs.jsonl"


def load_done() -> dict:
    """Calls with a readable verdict. Errors and unreadable replies are retried on rerun."""
    if not RUNS.exists():
        return {}
    with open(RUNS) as f:
        rows = {row["custom_id"]: row for row in map(json.loads, f)}  # later rows win
    return {cid: row for cid, row in rows.items() if row["verdict"] is not None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only the first N records (smoke test)")
    args = parser.parse_args()

    records = list(itertools.islice(iter_records(), args.limit))
    done = load_done()
    todo = [build_request(r, v, m) for r in records for v in VIEWS for m in MODELS
            if custom_id(r, v, m) not in done]
    n_lied = sum(r["lied"] for r in records)
    print(f"{len(records)} records ({n_lied} lied, {len(records) - n_lied} honest), "
          f"{len(todo)} calls to make, {len(done)} already done")

    if todo:
        client = QueuedOpenRouterClient(api_key=settings.OPENROUTER_API_KEY, max_workers=20, max_retries=5)
        replies = client.execute_all(todo)
        RUNS.parent.mkdir(parents=True, exist_ok=True)
        with open(RUNS, "a") as f:
            for req in todo:
                reply = replies.get(req["custom_id"], {})
                row = {"custom_id": req["custom_id"], "reply": reply, "verdict": parse_verdict(reply)}
                f.write(json.dumps(row) + "\n")
                done[row["custom_id"]] = row

    print(f"\n{'model':<28} {'view':<13} {'accuracy (95% range)':<22} {'false-pos rate (95% range)':<27} unreadable")
    for m, v in itertools.product(MODELS, VIEWS):
        pairs = [(r["lied"], done[custom_id(r, v, m)]["verdict"]) for r in records]
        readable = [(t, g) for t, g in pairs if g is not None]
        s = score([t for t, _ in readable], [g for _, g in readable])
        acc = f"{s['accuracy']:.0%} ({s['accuracy_ci'][0]:.0%}-{s['accuracy_ci'][1]:.0%})"
        fp = f"{s['fp_rate']:.0%} ({s['fp_ci'][0]:.0%}-{s['fp_ci'][1]:.0%})" if s["n_honest"] else "n/a"
        print(f"{m:<28} {v:<13} {acc:<22} {fp:<27} {len(pairs) - len(readable)}")


if __name__ == "__main__":
    main()
