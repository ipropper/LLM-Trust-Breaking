"""Stream agent-round records out of a Shi et al. game log, one at a time."""

import json
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).parent
DEFAULT_LOG = HERE.parent / "outputs/experiments/diners/5agents/anthropic_claude-sonnet-4.6_endogenous_mixed_llama_sonnet.json"
DEFAULT_SEATS = HERE / "agents_llama_sonnet.json"


def iter_records(log_path=DEFAULT_LOG, seats_path=DEFAULT_SEATS, skipped=None) -> Iterator[dict]:
    """Yield one flat dict per usable agent-round.

    The private plan (stage1) is never yielded, so it can't leak into a monitor view.
    Records the repo couldn't label (commitment_breaking is None) are skipped;
    pass a list as `skipped` to collect them.
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
                    # Answer key, computed by the repo: announced != chose
                    "lied": a.get("commitment_breaking"),
                }
                if record["lied"] is None:
                    if skipped is not None:
                        skipped.append(record)
                    continue
                yield record
