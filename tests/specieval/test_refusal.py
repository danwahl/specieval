"""Tests for the refusal-aware reducer and metrics."""

import numpy as np
from inspect_ai.scorer import NOANSWER, SampleScore, Score
from specieval.scorers.refusal import mean, mean_valid, std


def _scores(values):
    return [Score(value=v) for v in values]


def _sample_scores(values):
    return [SampleScore(score=Score(value=v)) for v in values]


def test_mean_valid_excludes_refusals():
    """Epoch mean should ignore NOANSWER rather than coerce it to 0."""
    reduce = mean_valid()
    result = reduce(_scores([6, NOANSWER, 6, NOANSWER, 6]))
    # Mean of the three valid 6s, not (6+0+6+0+6)/5 = 3.6.
    assert result.value == 6.0


def test_mean_valid_all_refused_returns_noanswer():
    """A fully-refused question reduces to NOANSWER so metrics can drop it."""
    reduce = mean_valid()
    result = reduce(_scores([NOANSWER, NOANSWER, NOANSWER]))
    assert result.value == NOANSWER


def test_mean_metric_excludes_refusals():
    """Sample-level mean should ignore NOANSWER samples."""
    metric_fn = mean()
    # (7 + 5) / 2, not (7 + 0 + 5) / 3.
    assert metric_fn(_sample_scores([7, NOANSWER, 5])) == 6.0


def test_mean_metric_all_refused_is_nan():
    metric_fn = mean()
    assert np.isnan(metric_fn(_sample_scores([NOANSWER, NOANSWER])))


def test_std_metric_excludes_refusals():
    """Std should match numpy sample std over the valid values only."""
    metric_fn = std()
    values = [7, NOANSWER, 5, 3]
    expected = float(np.std([7, 5, 3], ddof=1))
    assert metric_fn(_sample_scores(values)) == expected


def test_std_metric_too_few_values_is_zero():
    metric_fn = std()
    assert metric_fn(_sample_scores([5, NOANSWER])) == 0.0


def test_non_noanswer_string_is_refusal():
    """Any string value (not just NOANSWER) is excluded as a refusal."""
    assert mean()(_sample_scores([6, "I decline", 6])) == 6.0
    assert mean_valid()(_scores([6, "oops", 6])).value == 6.0


def test_reduction_then_metric_end_to_end():
    """A partial-refusal reduction feeds a numeric mean into the metric."""
    reduce = mean_valid()
    # Two questions: one partly refused (mean over the 3 valid = 6), one fully
    # refused (-> NOANSWER, dropped by the metric).
    q1 = reduce(_scores([6, NOANSWER, 6, 6]))
    q2 = reduce(_scores([NOANSWER, NOANSWER]))
    assert q1.value == 6.0 and q2.value == NOANSWER
    task_mean = mean()([SampleScore(score=q1), SampleScore(score=q2)])
    assert task_mean == 6.0  # only the scorable question counts


def test_metrics_named_for_analysis_keys():
    """Result dict keys must stay 'mean'/'std' for scripts/analysis.py."""
    from inspect_ai._util.registry import registry_info

    assert registry_info(mean()).name == "specieval/mean"
    assert registry_info(std()).name == "specieval/std"
