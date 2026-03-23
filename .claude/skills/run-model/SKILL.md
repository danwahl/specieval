---
name: run-model
description: Run eval on a model, update allowed_models.json, regenerate analysis, and suggest a commit
disable-model-invocation: true
argument-hint: [openrouter-model-id]
---

# Run Model Evaluation

Run the full evaluation pipeline for a model and update all artifacts.

The argument should be an OpenRouter model ID (e.g., `minimax/minimax-m2.7`). The user may also provide a short log directory name (e.g., `minimax-m2.7`); if not, derive one from the model ID by taking the last path segment.

## Steps

### 1. Run the evaluation

```bash
uv run inspect eval-set specieval/speciesism specieval/sentience specieval/attitude_meat specieval/attitude_seafood --model openrouter/$ARGUMENTS --log-dir logs/<log-dir-name>
```

This will take a while. Wait for it to complete and verify it succeeded (check for errors in the output).

### 2. Add model to allowed_models.json

Add the model's short name (the value that appears in the `model` field of log results, typically the last segment of the OpenRouter model ID) to `scripts/allowed_models.json`, keeping the list in alphabetical order.

If the model name already exists in the list, skip this step.

### 3. Generate updated analysis

Run the analysis script and capture the table output:

```bash
uv run scripts/analysis.py --data-file "scripts/data/attitudes data.csv"
```

This regenerates the chart image and prints the results table.

### 4. Update README.md

Replace the results table in README.md (the markdown table between the "Each assessment was run 10 times..." paragraph and the "Roughly reproducing Figure 3..." paragraph) with the fresh output from the analysis script.

### 5. Suggest a commit

Show the user a suggested commit command in the style of existing commits. The format is:

```
Add <Model Display Name>
```

For example: `Add Grok 4.20-beta`

Use the model's common display name rather than the raw model ID. Stage the following files:
- `scripts/allowed_models.json` (if modified)
- `images/chart.png`
- `README.md`

Do NOT commit automatically — just suggest the command and let the user decide.
