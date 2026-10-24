"""Print the paper's deception typology chart (Table 1) for a game log, overall and per model.

Usage: ../.venv/bin/python typology_table.py [game_log.json] [seats.json]
"""

import collections
import json
import sys
from pathlib import Path

from records import DEFAULT_LOG, DEFAULT_SEATS

# (repo typology label, display name, plan->pub, pub->act)
CATEGORIES = [
    ("fully_honest", "fully honest", "honest", "honest"),
    ("intended_deceptive_complied", "intended deceptive", "DECEPTIVE", "honest"),
    ("impulsive_deviation", "impulsive deviation", "honest", "DECEPTIVE"),
    ("premeditated_deception", "premeditated deception", "DECEPTIVE", "DECEPTIVE"),
    ("unknown", "unknown (parse failure)", "", ""),
]


def count_typologies(log_path, seats_path):
    """Counter of (model, typology), using the label the repo computed for each agent-round."""
    with open(log_path) as f:
        log = json.load(f)
    seats = json.loads(Path(seats_path).read_text()) if seats_path else {}
    counts = collections.Counter()
    for rnd in log["rounds"]:
        for trial in rnd["trials"]:
            for agent, a in trial["agents"].items():
                model = seats.get(agent, log["metadata"]["model"])
                counts[(model, a.get("typology", "unknown"))] += 1
    return counts


def main():
    log_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    seats_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SEATS
    counts = count_typologies(log_path, seats_path)
    models = sorted({m for m, _ in counts})
    short = [m.split("/")[-1] for m in models]

    print(f"{'category':<26} {'plan->pub':<10} {'pub->act':<10} {'all':>5}  " + "  ".join(f"{s:>22}" for s in short))
    for label, name, plan_pub, pub_act in CATEGORIES:
        per_model = [counts[(m, label)] for m in models]
        print(f"{name:<26} {plan_pub:<10} {pub_act:<10} {sum(per_model):>5}  " + "  ".join(f"{n:>22}" for n in per_model))


if __name__ == "__main__":
    main()
