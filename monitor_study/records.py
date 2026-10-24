"""Stream agent-round records out of a Shi et al. game log, one at a time."""

import json
from pathlib import Path
from typing import Iterator, Optional

HERE = Path(__file__).parent
DEFAULT_LOG = HERE.parent / "outputs/experiments/diners/5agents/anthropic_claude-sonnet-4.6_endogenous_mixed_llama_sonnet.json"
DEFAULT_SEATS = HERE / "agents_llama_sonnet.json"

VALID_ACTIONS = {"EXPENSIVE", "CHEAP"}  # Diners
KNOWN_TYPOLOGIES = {"fully_honest", "intended_deceptive_complied", "impulsive_deviation", "premeditated_deception"}


def invalid_reason(a: dict) -> Optional[str]:
    """Why an agent-round can't be used, or None if it is clean.

    Every stage must have parsed to a valid action, and the repo's labels must be
    known and consistent with those actions.
    """
    actions = {
        "stage1": a["stage1"].get("intended_action"),
        "stage2": a["stage2"].get("stated_action"),
        "stage3": a["stage3"].get("choice"),
    }
    for stage, action in actions.items():
        if not a[stage].get("_parse_ok"):
            return f"{stage} unparsed"
        if action not in VALID_ACTIONS:
            return f"{stage} invalid action {action!r}"
    if a.get("typology") not in KNOWN_TYPOLOGIES:
        return f"unknown typology {a.get('typology')!r}"
    if a.get("commitment_breaking") != (actions["stage2"] != actions["stage3"]):
        return "commitment_breaking disagrees with stage2/stage3"
    if a.get("promise_deception") != (actions["stage1"] != actions["stage2"]):
        return "promise_deception disagrees with stage1/stage2"
    return None


def iter_records(log_path=DEFAULT_LOG, seats_path=DEFAULT_SEATS, skipped=None) -> Iterator[dict]:
    """Yield one flat dict per clean agent-round.

    The private plan (stage1) is checked but never yielded, so it can't leak into a
    monitor view. Pass a list as `skipped` to collect (record, reason) for rejects.
    """
    # The pilot log is ~400 KB, so json.load is fine. Swap in ijson here if logs get big.
    with open(log_path) as f:
        log = json.load(f)
    seats = json.loads(Path(seats_path).read_text()) if seats_path else {}

    for rnd in log["rounds"]:
        for trial in rnd["trials"]:
            for agent, a in trial["agents"].items():
                record = {
                    "round": rnd["round_id"],
                    "trial": trial["trial_id"],
                    "agent": agent,
                    "model": seats.get(agent, log["metadata"]["model"]),
                    "announced": a["stage2"].get("stated_action"),
                    "message": a["stage2"].get("message", ""),
                    "chose": a["stage3"].get("choice"),
                    # Answer keys, computed by the repo and checked in invalid_reason.
                    # planned_lie (private plan != announcement) is what the monitor predicts;
                    # lied (announcement != actual order) is kept for analysis.
                    "planned_lie": a.get("promise_deception"),
                    "lied": a.get("commitment_breaking"),
                    "typology": a.get("typology"),
                }
                reason = invalid_reason(a)
                if reason:
                    if skipped is not None:
                        skipped.append((record, reason))
                    continue
                yield record
