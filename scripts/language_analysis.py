import argparse
import json
import logging
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SpeciEval language comparison table"
    )
    parser.add_argument("--logs-dir", default="logs", help="Directory containing logs")
    parser.add_argument("--output-dir", default="images", help="Output directory")
    return parser.parse_args()


def parse_logs(logs_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    try:
        with open(logs_path, "r") as f:
            logs = json.load(f)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()
    scores, samples = [], []
    for _, log in logs.items():
        if log.get("status") != "success":
            continue
        model = log["eval"]["model"].split("/")[-1]
        task = log["eval"]["task_registry_name"].split("/")[-1]
        lang = log["eval"]["task_args"].get("language", "en")
        try:
            score = log["results"]["scores"][0]["metrics"]["mean"]["value"]
        except Exception:
            score = None
        scores.append({"model": model, "task": task, "language": lang, "score": score})
        try:
            for sample in log["reductions"][0]["samples"]:
                if sample.get("sample_id"):
                    samples.append(
                        {
                            "model": model,
                            "language": lang,
                            "question": sample["sample_id"],
                            "score": sample.get("value", 0),
                        }
                    )
        except Exception:
            pass
    return pd.DataFrame(scores), pd.DataFrame(samples)


def main() -> None:
    args = parse_args()
    logs_dir, output_dir = Path(args.logs_dir), Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_paths = sorted(list(logs_dir.glob("**/logs.json")))

    df_scores_lang = pd.DataFrame()
    exclude_models = [
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-pro-preview-03-25",
    ]

    for path in logs_paths:
        scores, _ = parse_logs(path)
        if scores.empty:
            continue
        pivot = scores.pivot_table(
            index=["model", "language"], columns="task", values="score"
        )
        pivot.columns = pivot.columns.str.replace("_task", "")
        pivot = pivot[~pivot.index.get_level_values(0).isin(exclude_models)]
        df_scores_lang = pd.concat([df_scores_lang, pivot], axis=0)

    if df_scores_lang.empty:
        return
    df_scores_lang = df_scores_lang.groupby(level=[0, 1]).mean()
    task_to_assessment = {
        "speciesism": "spec",
        "sentience": "bfas",
        "attitude_meat": "la4N",
        "attitude_seafood": "se4N",
    }
    languages_df = df_scores_lang.rename(columns=task_to_assessment)
    cols = [c for c in task_to_assessment.values() if c in languages_df.columns]
    languages_df = languages_df[cols]

    models = [
        m
        for m in languages_df.index.get_level_values(0).unique()
        if len(languages_df.loc[m]) > 1
    ]
    if not models:
        return

    fig, axes = plt.subplots(1, len(models), figsize=(12, 7))
    if len(models) == 1:
        axes = [axes]

    for i, model in enumerate(models):
        data = languages_df.loc[model]
        if "en" not in data.index:
            continue
        diff = data.subtract(data.loc["en"], axis=1)
        vmin, vmax = diff.min().min(), diff.max().max()
        if pd.isna(vmin) or vmin == vmax:
            vmin, vmax = -1, 1
        norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
        table = axes[i].table(
            cellText=data.round(2).values,
            rowLabels=data.index,
            colLabels=data.columns,
            cellLoc="center",
            loc="center",
        )
        for r_idx, row in enumerate(data.index):
            for c_idx, col in enumerate(data.columns):
                d_val = diff.loc[row, col]
                if pd.isna(d_val):
                    continue
                c_val = d_val if col == "bfas" else -d_val
                color = plt.cm.PiYG(norm(c_val))
                table[(r_idx + 1, c_idx)].set_facecolor(color)
                if np.mean(color[:3]) < 0.5:
                    table[(r_idx + 1, c_idx)].set_text_props(color="white")
        axes[i].set_title(model, fontsize=16, fontweight="bold", pad=20)
        axes[i].axis("off")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.4, 2.0)

    plt.tight_layout(pad=2.0)
    plt.savefig(output_dir / "table.png", bbox_inches="tight", dpi=300)
    logger.info(f"Saved language table to {output_dir / 'table.png'}")


if __name__ == "__main__":
    main()
