import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate SpeciEval analysis charts")
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Directory containing log subdirs with logs.json (default: logs)",
    )
    parser.add_argument(
        "--data-file",
        required=True,
        help="Path to Hopwood et al. attitudes data CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="images",
        help="Directory to save output images (default: images)",
    )
    return parser.parse_args()


def parse_logs(logs_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Parse a single logs.json file."""
    try:
        with open(logs_path, "r") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Failed to read {logs_path}: {e}")
        return pd.DataFrame(), pd.DataFrame()

    scores: List[Dict[str, Any]] = []
    samples: List[Dict[str, Any]] = []

    for _, log in logs.items():
        if log.get("status") != "success":
            continue

        model = log["eval"]["model"]
        model_short = model.split("/")[-1]

        task_registry_name = log["eval"]["task_registry_name"]
        task = task_registry_name.split("/")[-1]

        language = log["eval"]["task_args"].get("language", "en")

        try:
            score = log["results"]["scores"][0]["metrics"]["mean"]["value"]
        except (KeyError, IndexError):
            score = None

        scores.append(
            {
                "model": model_short,
                "task": task,
                "language": language,
                "score": score,
            }
        )

        try:
            for sample in log["reductions"][0]["samples"]:
                sample_id = sample.get("sample_id")
                if sample_id:
                    samples.append(
                        {
                            "model": model_short,
                            "language": language,
                            "question": sample_id,
                            "score": sample.get("value", 0),
                        }
                    )
        except (KeyError, IndexError):
            pass

    return pd.DataFrame(scores), pd.DataFrame(samples)


def aggregate_samples(samples: pd.DataFrame, questions: List[str]) -> pd.Series:
    """Aggregate sample scores with reverse scoring."""
    reverse_score_prefixes = ["spec_", "la4N_", "se4N_"]

    aggregated = pd.Series(
        index=samples.index,
        dtype=float,
    )

    for ind in aggregated.index:
        s = samples.loc[ind]
        total = 0.0
        count = 0

        for q in questions:
            if q in s.index and pd.notna(s[q]):
                sample = s[q]
                if any(q.startswith(prefix) for prefix in reverse_score_prefixes):
                    sample = 8 - sample
                total += sample
                count += 1

        if count == len(questions):
            min_possible = 1 * len(questions)
            max_possible = 7 * len(questions)
            aggregated[ind] = (
                100 * (total - min_possible) / (max_possible - min_possible)
            )

    return aggregated


def plot_assessment(
    ax: Axes,
    assessment: str,
    title: str,
    countries: pd.DataFrame,
    models: pd.DataFrame,
) -> None:
    """Plot data for a specific assessment."""
    s = pd.concat([countries[assessment], models[assessment]], axis=0)

    if "USA" not in s.index:
        logger.warning(f"USA data missing for {assessment}, skipping normalization.")
    else:
        s -= s.loc["USA"]

    western_countries = [
        "USA",
        "Argentina",
        "Brazil",
        "Canada",
        "Chile",
        "Colombia",
        "France",
        "Germany",
        "Italy",
        "Mexico",
        "Netherlands",
        "Poland",
        "Spain",
        "UK",
    ]
    western_countries = [c for c in western_countries if c in s.index]

    eastern_countries = countries.index.difference(
        western_countries + ["Russia"]
    ).tolist()
    eastern_countries = [c for c in eastern_countries if c in s.index]

    usa_part = s.loc[["USA"]] if "USA" in s.index else pd.Series(dtype=float)
    western_part = s.loc[[c for c in western_countries if c != "USA"]].sort_index()
    russia_part = s.loc[["Russia"]] if "Russia" in s.index else pd.Series(dtype=float)
    eastern_part = s.loc[eastern_countries].sort_index()
    models_part = s.loc[models.index].sort_index()

    sorted_data = pd.concat(
        [usa_part, western_part, russia_part, eastern_part, models_part]
    )[::-1]

    names = sorted_data.index.tolist()
    values = sorted_data.values
    y_pos = np.arange(len(names))

    western_indices = [i for i, c in enumerate(names) if c in western_countries]
    eastern_indices = [i for i, c in enumerate(names) if c in eastern_countries]
    russia_indices = [i for i, c in enumerate(names) if c == "Russia"]
    model_indices = [i for i, c in enumerate(names) if c in models.index]

    ax.scatter(
        values[western_indices],
        y_pos[western_indices],
        color="blue",
        marker="s",
        s=40,
    )
    ax.scatter(
        values[eastern_indices],
        y_pos[eastern_indices],
        color="red",
        marker="^",
        s=40,
    )
    ax.scatter(
        values[russia_indices],
        y_pos[russia_indices],
        color="gray",
        marker="o",
        s=40,
    )
    ax.scatter(
        values[model_indices],
        y_pos[model_indices],
        color="green",
        marker="D",
        s=40,
    )

    for i, val in enumerate(values):
        if names[i] in western_countries:
            ax.plot([0, val], [y_pos[i], y_pos[i]], "b-", alpha=0.7)
        elif names[i] in eastern_countries:
            ax.plot([0, val], [y_pos[i], y_pos[i]], "r-", alpha=0.7)
        elif names[i] == "Russia":
            ax.plot([0, val], [y_pos[i], y_pos[i]], "gray", alpha=0.7)
        else:
            ax.plot([0, val], [y_pos[i], y_pos[i]], "g-", alpha=0.7)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names)
    ax.set_title(title)
    ax.set_xlabel("Z-score")
    ax.set_xlim(-2.0, 2.0)
    ax.set_xticks(np.arange(-2, 2.4, 0.4))
    ax.grid(True)


def main() -> None:
    args = parse_args()
    logs_dir, data_file, output_dir = (
        Path(args.logs_dir),
        Path(args.data_file),
        Path(args.output_dir),
    )

    if not logs_dir.exists() or not data_file.exists():
        logger.error("Logs directory or data file not found.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(data_file, sep=";")
    except Exception as e:
        logger.error(f"Failed to read data file: {e}")
        return

    assessments = ["spec", "bfas", "la4N", "se4N"]
    for assessment in assessments:
        cols = [col for col in df.columns if assessment in col]
        if cols:
            df[assessment] = df[cols].mean(axis=1)

    countries = df.groupby("Country")[assessments].mean()
    means, stds = df[assessments].mean(), df[assessments].std()
    countries = (countries - means) / stds

    logs_paths = sorted(list(logs_dir.glob("**/logs.json")))
    logger.info(f"Found {len(logs_paths)} log files.")

    # Load allowed models
    allowed_models_path = Path(__file__).parent / "allowed_models.json"
    if allowed_models_path.exists():
        with open(allowed_models_path, "r") as f:
            allowed_models = set(json.load(f))
    else:
        logger.warning(
            f"Allowed models file not found at {allowed_models_path}. "
            "No filtering will be applied."
        )
        allowed_models = None

    questions = [
        "spec_1",
        "spec_2",
        "spec_3",
        "spec_4",
        "bfas_1",
        "bfas_2",
        "bfas_3",
        "bfas_4",
        "bfas_5",
        "bfas_6",
        "la4N_2",
        "se4N_2",
    ]

    data_df = pd.DataFrame()
    for logs_path in logs_paths:
        scores, samples = parse_logs(logs_path)
        if scores.empty:
            continue

        df_scores = scores.pivot_table(index="model", columns="task", values="score")
        df_scores.columns = df_scores.columns.str.replace("_task", "")

        # Filter allowed models
        if allowed_models is not None:
            df_scores = df_scores[df_scores.index.isin(allowed_models)]

        if df_scores.empty:
            continue

        if not samples.empty:
            df_samples = samples.pivot_table(
                index="model", columns="question", values="score"
            )
            if allowed_models is not None:
                df_samples = df_samples[df_samples.index.isin(allowed_models)]
            df_scores["aggregated"] = aggregate_samples(df_samples, questions)
        else:
            df_scores["aggregated"] = np.nan
        data_df = pd.concat([data_df, df_scores], axis=0)

    if data_df.empty:
        logger.error("No valid data extracted.")
        return

    data_df = data_df.groupby(level=0).mean()
    task_to_assessment = {
        "aggregated": "specieval",
        "speciesism": "spec",
        "sentience": "bfas",
        "attitude_meat": "la4N",
        "attitude_seafood": "se4N",
    }

    for c in [k for k in task_to_assessment.keys() if k not in data_df.columns]:
        data_df[c] = np.nan

    models_df = data_df.rename(columns=task_to_assessment).sort_values(
        "specieval", ascending=False
    )
    formatted = models_df[list(task_to_assessment.values())].reset_index()
    formatted.index = range(1, len(formatted) + 1)
    formatted.index.name = "#"
    print(formatted.to_markdown(floatfmt="0.2f"))

    models_norm = (models_df - means) / stds
    fig, axes = plt.subplots(2, 2, figsize=(20, 26))
    titles = [
        "Speciesism",
        "Belief in Animal Sentience",
        "Land Animal 4Ns",
        "Sea Animal 4Ns",
    ]

    for i, (assessment, title) in enumerate(zip(assessments, titles)):
        row, col = i // 2, i % 2
        if assessment in models_norm.columns:
            plot_assessment(axes[row, col], assessment, title, countries, models_norm)
        else:
            axes[row, col].text(
                0.5, 0.5, f"No data for {title}", ha="center", va="center"
            )

    plt.tight_layout()
    fig.savefig(output_dir / "chart.png", bbox_inches="tight", dpi=300)
    logger.info(f"Saved chart to {output_dir / 'chart.png'}")


if __name__ == "__main__":
    main()
