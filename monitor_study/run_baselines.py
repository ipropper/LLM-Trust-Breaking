"""Build the answer key and score the no-LLM baselines on every usable record."""

import json
import random
from collections import Counter
from pathlib import Path

from baselines import coin_flip, keyword_says_vs_does, says_vs_does
from records import iter_records
from score import score

SEED = 42
OUT_DIR = Path(__file__).parent.parent / "outputs/monitor_study"


def main():
    rng_says, rng_does = random.Random(SEED), random.Random(SEED + 1)
    skipped = []
    truth = []
    guesses = {"A says only (coin flip)": [], "B does only (coin flip)": [],
               "C says+does keyword": [], "D says+does structured": []}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "answer_key.jsonl", "w") as key_file:
        for r in iter_records(skipped=skipped):
            key_file.write(json.dumps({k: r[k] for k in ("round", "trial", "agent", "model", "planned_lie", "lied")}) + "\n")
            truth.append(r["planned_lie"])
            guesses["A says only (coin flip)"].append(coin_flip(r, rng_says))
            guesses["B does only (coin flip)"].append(coin_flip(r, rng_does))
            guesses["C says+does keyword"].append(keyword_says_vs_does(r))
            guesses["D says+does structured"].append(says_vs_does(r))

    print(f"records: {len(truth)} usable ({sum(truth)} planned a lie, {len(truth) - sum(truth)} honest plan), {len(skipped)} skipped")
    for reason, n in Counter(reason for _, reason in skipped).most_common():
        print(f"  skipped {n:>3}: {reason}")
    print()
    print(f"{'baseline':<26} {'accuracy (95% range)':<24} {'false-positive rate (95% range)'}")
    for name, g in guesses.items():
        s = score(truth, g)
        acc = f"{s['accuracy']:.0%} ({s['accuracy_ci'][0]:.0%}-{s['accuracy_ci'][1]:.0%})"
        fp = f"{s['fp_rate']:.0%} ({s['fp_ci'][0]:.0%}-{s['fp_ci'][1]:.0%})"
        print(f"{name:<26} {acc:<24} {fp}")


if __name__ == "__main__":
    main()
