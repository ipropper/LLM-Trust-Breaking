"""Accuracy and false-positive rate, each with a 95% Wilson interval."""

import math


def wilson(hits: int, n: int, z: float = 1.96):
    """95% range for a proportion hits/n. Behaves well for small n and rates near 0 or 1."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(truth: list, guesses: list) -> dict:
    """truth and guesses are parallel lists of bools (True = planned a lie)."""
    correct = sum(t == g for t, g in zip(truth, guesses))
    honest_guesses = [g for t, g in zip(truth, guesses) if not t]
    false_alarms = sum(honest_guesses)
    return {
        "n": len(truth),
        "accuracy": correct / len(truth),
        "accuracy_ci": wilson(correct, len(truth)),
        "n_honest": len(honest_guesses),
        "fp_rate": false_alarms / len(honest_guesses),
        "fp_ci": wilson(false_alarms, len(honest_guesses)),
    }
