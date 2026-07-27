"""Re-score existing SpeciEval logs with refusal-aware scoring.

Re-applies the `likert` scorer together with the refusal-excluding epoch
reducer (`mean_valid`) and refusal-aware `mean`/`std` metrics to *stored* model
outputs -- no model is ever called. Only `.eval` logs that contain at least one
refusal are rewritten (all others already produce identical scores), and each
affected model's `logs.json` manifest is regenerated so scripts/analysis.py
picks up the corrected numbers.

Scope is by model name (not directory): a log dir may hold several models and a
model may span several dirs, so every English refusal log for a ranked model is
re-scored wherever it lives. Non-English logs are left alone (language_analysis).

Usage:
    python scripts/rescore.py                       # all ranked models w/ refusals
    python scripts/rescore.py --models gpt-5.1-chat # specific model name(s)
    python scripts/rescore.py --dry-run             # report, change nothing
"""

import argparse
import json
import os
from pathlib import Path

# Scoring re-constructs the model client (but never calls it); a placeholder
# key is enough since every log routes through OpenRouter.
os.environ.setdefault("OPENROUTER_API_KEY", "unused-during-rescore")

from inspect_ai._eval.score import score as score_log  # noqa: E402
from inspect_ai.log import (  # noqa: E402
    read_eval_log,
    write_eval_log,
    write_log_dir_manifest,
)
from inspect_ai.scorer import NOANSWER  # noqa: E402
from specieval.scorers.likert import likert  # noqa: E402
from specieval.scorers.refusal import mean_valid  # noqa: E402


def sample_is_refusal(sample) -> bool:
    """True if a stored sample's likert score is a refusal / failed extraction."""
    if not sample.scores:
        return False
    score = sample.scores.get("likert") or next(iter(sample.scores.values()))
    value = score.value
    if value == NOANSWER or isinstance(value, str):
        return True
    return bool(score.explanation and "Error extracting score" in score.explanation)


def rescore_eval(
    path: Path,
    allowed: set[str],
    models: list[str] | None,
    dry_run: bool = False,
) -> tuple[str, float | None, float | None] | None:
    """Re-score a single .eval in place if it is an in-scope refusal log.

    In scope = a successful English log for a ranked model that contains at
    least one refusal. Log directories and model names are decoupled (a dir may
    hold several models; a model may span several dirs), so scope is decided per
    log by its own model/language, not by the directory name.

    Returns (model_short, old_mean, new_mean) when rewritten
    (means are None in dry-run), else None.
    """
    log = read_eval_log(str(path))
    if log.status != "success" or not log.samples:
        return None
    model_short = log.eval.model.split("/")[-1]
    target = models if models is not None else allowed
    if model_short not in target:
        return None
    if log.eval.task_args.get("language", "en") != "en":
        return None
    if not any(sample_is_refusal(s) for s in log.samples):
        return None

    if dry_run:
        return model_short, None, None

    old_mean = log.results.scores[0].metrics["mean"].value

    # Clear header metrics so the passed scorer's refusal-aware mean/std are used
    # (metrics_from_log_header would otherwise pin the old coercing metrics).
    log.eval.metrics = None
    rescored = score_log(log, likert(), epochs_reducer=mean_valid(), action="overwrite")
    new_mean = rescored.results.scores[0].metrics["mean"].value
    write_eval_log(rescored, str(path))
    return model_short, old_mean, new_mean


def main() -> None:
    ap = argparse.ArgumentParser(description="Refusal-aware re-scoring of logs")
    ap.add_argument("--logs-dir", default="logs")
    ap.add_argument(
        "--models",
        nargs="*",
        help="Specific model name(s) (default: every ranked model with refusals)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Report changes without writing"
    )
    args = ap.parse_args()

    logs_dir = Path(args.logs_dir)
    # Ranked models (published table). Scope is by model name, not directory:
    # a dir can hold several models and a model can span several dirs.
    allowed = set(json.load(open(Path(__file__).parent / "allowed_models.json")))

    total_changed = 0
    for model_dir in sorted(p.parent for p in logs_dir.glob("*/logs.json")):
        changed = []  # (task_label, model_short, old_mean, new_mean)
        for eval_path in sorted(model_dir.glob("*.eval")):
            result = rescore_eval(eval_path, allowed, args.models, dry_run=args.dry_run)
            if result is not None:
                parts = eval_path.name.split("_")
                changed.append(
                    (parts[1] if len(parts) > 1 else eval_path.name, *result)
                )

        if not changed:
            continue

        total_changed += len(changed)
        print(f"\n{model_dir.name}/:")
        for task, model_short, old, new in changed:
            if old is None:
                print(f"  {model_short} {task}: (dry-run) has refusals")
            else:
                print(f"  {model_short} {task}: mean {old:.3f} -> {new:.3f}")

        if not args.dry_run:
            write_log_dir_manifest(str(model_dir))
            print("  regenerated logs.json manifest")

    verb = "would re-score" if args.dry_run else "re-scored"
    print(f"\nDone. {verb} {total_changed} log(s) across affected models.")


if __name__ == "__main__":
    main()
