import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_logs(logs_path):
    with open(logs_path, "r") as f:
        logs = json.load(f)

    results = []
    for _, log in logs.items():
        if log.get("status") == "success":
            model = log["eval"]["model"]
            model_short = model.split("/")[-1]

            task_registry_name = log["eval"]["task_registry_name"]
            task = task_registry_name.split("/")[-1]

            language = log["eval"]["task_args"].get("language", "en")

            try:
                score = log["results"]["scores"][0]["metrics"]["mean"]["value"]
            except (KeyError, IndexError):
                score = None

            results.append(
                {
                    "model": model_short,
                    "task": task,
                    "language": language,
                    "score": score,
                }
            )

    return pd.DataFrame(results)


def plot_assessment(ax, assessment, title, countries, models):
    # Plot the data
    s = pd.concat([countries[assessment], models[assessment]], axis=0)
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
    eastern_countries = countries.index.difference(
        western_countries + ["Russia"]
    ).tolist()

    # Create specific order with Russia between Western and Eastern
    sorted_data = pd.concat(
        [
            s.loc[["USA"]],
            s.loc[[c for c in western_countries if c != "USA"]].sort_index(),
            s.loc[["Russia"]],
            s.loc[eastern_countries].sort_index(),
            s.loc[models.index].sort_index(),
        ]
    )[::-1]

    names = sorted_data.index.tolist()
    values = sorted_data.values
    y_pos = np.arange(len(names))

    # Create indices for each group
    western_indices = [i for i, c in enumerate(names) if c in western_countries]
    eastern_indices = [i for i, c in enumerate(names) if c in eastern_countries]
    russia_indices = [i for i, c in enumerate(names) if c == "Russia"]
    model_indices = [i for i, c in enumerate(names) if c in models.index]

    # Plot markers for each group
    ax.scatter(
        values[western_indices], y_pos[western_indices], color="blue", marker="s", s=40
    )
    ax.scatter(
        values[eastern_indices], y_pos[eastern_indices], color="red", marker="^", s=40
    )
    ax.scatter(
        values[russia_indices], y_pos[russia_indices], color="gray", marker="o", s=40
    )
    ax.scatter(
        values[model_indices], y_pos[model_indices], color="green", marker="D", s=40
    )

    # Plot connecting lines
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

    ax.set_xlim(-1.6, 1.6)
    ax.set_xticks(np.arange(-1.6, 2, 0.4))
    ax.grid(True)


if __name__ == "__main__":
    # Grab the data from Hopwood et.al. (2025) here: https://osf.io/kdgtx/?view_only=bf22ece589864c73999c987d5ee0b532
    df = pd.read_csv("data/attitudes data.csv", sep=";")

    assessments = ["spec", "bfas", "la4N", "se4N"]
    for assessment in assessments:
        # Get data corresponding to the assessment
        cols = [col for col in df.columns if assessment in col]
        data = df[cols]

        # Compute assessment scores
        df[assessment] = data.mean(axis=1)

    # Get z-scores for each country
    countries = df.groupby("Country")[assessments].mean()
    means, stds = df[assessments].mean(), df[assessments].std()
    countries = (countries - means) / stds

    # Parse the SpeciEval logs
    logs_paths = [
        Path("../logs/specieval/logs.json"),
        Path("../logs/claude-4/logs.json"),
        Path("../logs/gemini-2.5-flash/logs.json"),
        Path("../logs/mistral-medium-3/logs.json"),
    ]

    data = pd.DataFrame()
    for logs_path in logs_paths:
        if logs_path.exists():  # Check if file exists to avoid errors
            df_logs = parse_logs(logs_path).pivot_table(
                index="model", columns="task", values="score"
            )
            # Strip _task from column names
            df_logs.columns = df_logs.columns.str.replace("_task", "")
            data = pd.concat([data, df_logs], axis=0)
    data.sort_index(inplace=True)

    task_to_assessment = {
        "speciesism": "spec",
        "sentience": "bfas",
        "attitude_meat": "la4N",
        "attitude_seafood": "se4N",
    }

    models = data.rename(columns=task_to_assessment)

    print(models[task_to_assessment.values()].to_markdown(floatfmt="0.2f"))

    models = (models - means) / stds

    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    titles = [
        "Speciesism",
        "Belief in Animal Sentience",
        "Land Animal 4Ns",
        "Sea Animal 4Ns",
    ]

    for i, (assessment, title) in enumerate(zip(assessments, titles)):
        row, col = i // 2, i % 2
        plot_assessment(axes[row, col], assessment, title, countries, models)

    plt.tight_layout()
    fig.savefig("../images/chart.png", bbox_inches="tight", dpi=300)
