"""Write one standard CSV per game log, then all_games.csv stacking every per-game CSV.

Usage: ../.venv/bin/python export_dataset.py GAME_LOG.json [GAME_LOG.json ...]
No API calls. Every game gets the same columns, so the CSVs stack into one sheet.
Monitor guess columns fill from outputs/monitor_study/<game log name>/monitor_runs.jsonl
when a monitor has run on that log; otherwise they stay blank.
Writes to outputs/monitor_study/datasets/.
"""

import collections
import csv
import json
import sys
from pathlib import Path

from monitor import VIEWS
from records import iter_records

OUT_ROOT = Path(__file__).parent.parent / "outputs/monitor_study"
DATASETS = OUT_ROOT / "datasets"

# Shorter names in the spreadsheet; the raw game logs keep the repo's labels
TYPOLOGY_NAMES = {"intended_deceptive_complied": "intended_deceptive"}
GUESS_COLUMNS = {"A_says": "guess_message", "B_does": "guess_action", "C_says_does": "guess_message_action"}
COLUMNS = ["id", "game", "agent_model", "source_log", "round", "trial", "agent",
           "planned_action", "announced_action", "actual_action", "message",
           "intended", "typology", "monitor_model", *GUESS_COLUMNS.values()]


def results_dir(log_path: Path, game: str) -> Path:
    """Monitor results folder for one game log. Includes the game because logs from
    different games can share a file name (e.g. every game's ..._1game.json)."""
    return OUT_ROOT / f"{game}__{log_path.stem}"


def intent_label(planned_lie) -> str:
    return {True: "deceitful", False: "honest"}.get(planned_lie, "unreadable")


def load_guesses(runs: Path) -> dict:
    """{monitor model: {(agent key, view): verdict}} from a monitor_runs.jsonl, later rows winning."""
    guesses = collections.defaultdict(dict)
    if runs.exists():
        with open(runs) as f:
            for row in map(json.loads, f):
                key, view, model = row["custom_id"].split("|")
                guesses[model][(key, view)] = row["verdict"]
    return guesses


def build_rows(records: list, guesses: dict) -> list:
    """One row per record per monitor model, or one row with blank guesses if no monitor has run."""
    rows = []
    for r in records:
        key = f"r{r['round']}_t{r['trial']}_{r['agent']}"  # same prefix as monitor.custom_id
        base = {
            "id": f"{r['game']}|{r['source_log']}|{key}",
            "game": r["game"],
            "agent_model": r["model"],
            "source_log": r["source_log"],
            "round": r["round"],
            "trial": r["trial"],
            "agent": r["agent"],
            "planned_action": r["plan"],
            "announced_action": r["announced"],
            "actual_action": r["chose"],
            "message": r["message"],
            "intended": intent_label(r["planned_lie"]),
            "typology": TYPOLOGY_NAMES.get(r["typology"], r["typology"]),
        }
        for model, verdicts in (guesses.items() or [("", {})]):
            row = {**base, "monitor_model": model}
            for view, col in GUESS_COLUMNS.items():
                found = (key, view) in verdicts
                row[col] = intent_label(verdicts[(key, view)]) if found else ""
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel detects the encoding
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def export_log(log_path: Path) -> Path:
    records = list(iter_records(log_path, None))
    rows = build_rows(records, load_guesses(results_dir(log_path, records[0]["game"]) / "monitor_runs.jsonl"))
    path = DATASETS / f"{records[0]['game']}__{log_path.stem}.csv"
    write_csv(path, rows)
    return path


def combine() -> Path:
    """Stack every per-game CSV in datasets/ into all_games.csv."""
    rows = []
    for path in sorted(DATASETS.glob("*__*.csv")):
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows.extend(csv.DictReader(f))
    out = DATASETS / "all_games.csv"
    write_csv(out, rows)
    return out


def main():
    for log in map(Path, sys.argv[1:]):
        print(f"wrote {export_log(log)}")
    out = combine()
    with open(out, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    agent_rounds = {r["id"]: r for r in rows}  # one per agent-round, even if several monitors ran
    counts = collections.Counter((r["game"], r["intended"]) for r in agent_rounds.values())
    print(f"\n{out}: {len(rows)} rows, {len(agent_rounds)} agent-rounds")
    print(f"{'game':<13} {'honest':>7} {'deceitful':>10}")
    for game in sorted({g for g, _ in counts}):
        print(f"{game:<13} {counts[(game, 'honest')]:>7} {counts[(game, 'deceitful')]:>10}")


if __name__ == "__main__":
    main()
