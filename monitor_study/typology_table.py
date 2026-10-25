"""Print the paper's deception typology chart (Table 1) for a game log, overall and per model.

Counts only the clean records that iter_records yields, so the chart always matches the dataset.
Usage: ../.venv/bin/python typology_table.py [game_log.json] [seats.json]
"""

import collections
import sys

from records import DEFAULT_LOG, DEFAULT_SEATS, iter_records

# (repo typology label, display name, plan->pub, pub->act)
CATEGORIES = [
    ("fully_honest", "fully honest", "honest", "honest"),
    ("intended_deceptive_complied", "intended deceptive", "DECEPTIVE", "honest"),
    ("impulsive_deviation", "impulsive deviation", "honest", "DECEPTIVE"),
    ("premeditated_deception", "premeditated deception", "DECEPTIVE", "DECEPTIVE"),
]


def main():
    log_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    seats_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SEATS
    skipped = []
    counts = collections.Counter((r["model"], r["typology"]) for r in iter_records(log_path, seats_path, skipped))
    models = sorted({m for m, _ in counts})
    short = [m.split("/")[-1] for m in models]

    print(f"{'category':<26} {'plan->pub':<10} {'pub->act':<10} {'all':>5}  " + "  ".join(f"{s:>22}" for s in short))
    for label, name, plan_pub, pub_act in CATEGORIES:
        per_model = [counts[(m, label)] for m in models]
        print(f"{name:<26} {plan_pub:<10} {pub_act:<10} {sum(per_model):>5}  " + "  ".join(f"{n:>22}" for n in per_model))
    print(f"\n{sum(counts.values())} clean records; {len(skipped)} excluded:")
    for reason, n in collections.Counter(reason for _, reason in skipped).most_common():
        print(f"  {n:>3}  {reason}")


if __name__ == "__main__":
    main()
