"""Tests for the Likert scorer."""

import pytest
from inspect_ai.scorer import NOANSWER
from specieval.scorers.likert import likert


class MockOutput:
    """Mock output object with completion attribute."""

    def __init__(self, completion: str):
        self.completion = completion


class MockTaskState:
    """Mock task state for testing the scorer."""

    def __init__(self, completion: str, levels: int = 7, reverse: bool = False):
        self.output = MockOutput(completion)
        self.metadata = {"levels": levels, "reverse": reverse}


@pytest.mark.asyncio
async def test_likert_extracts_answer():
    """Test that the scorer extracts numerical answers correctly."""
    scorer_fn = likert()
    state = MockTaskState("I think the answer is ANSWER: 5")

    score = await scorer_fn(state, None)

    assert score.value == 5
    assert score.answer == "5"


@pytest.mark.asyncio
async def test_likert_extracts_answer_with_whitespace():
    """Test extraction with varying whitespace around ANSWER."""
    scorer_fn = likert()

    # Test with extra spaces
    state = MockTaskState("ANSWER :  3")
    score = await scorer_fn(state, None)
    assert score.value == 3

    # Test with no spaces
    state = MockTaskState("ANSWER:7")
    score = await scorer_fn(state, None)
    assert score.value == 7


@pytest.mark.asyncio
async def test_likert_reverse_scoring():
    """Test that reverse scoring is applied correctly."""
    scorer_fn = likert()

    # With reverse=True and levels=7, score of 1 should become 7
    state = MockTaskState("ANSWER: 1", levels=7, reverse=True)
    score = await scorer_fn(state, None)
    assert score.value == 7
    assert score.answer == "1"  # Raw answer stored

    # Score of 7 should become 1
    state = MockTaskState("ANSWER: 7", levels=7, reverse=True)
    score = await scorer_fn(state, None)
    assert score.value == 1

    # Score of 4 (middle) should stay 4
    state = MockTaskState("ANSWER: 4", levels=7, reverse=True)
    score = await scorer_fn(state, None)
    assert score.value == 4


@pytest.mark.asyncio
async def test_likert_no_reverse_scoring():
    """Test that scores are unchanged when reverse is False."""
    scorer_fn = likert()

    state = MockTaskState("ANSWER: 3", levels=7, reverse=False)
    score = await scorer_fn(state, None)
    assert score.value == 3
    assert score.answer == "3"


@pytest.mark.asyncio
async def test_likert_no_answer_found():
    """Test handling when no answer is found in the response."""
    scorer_fn = likert()

    state = MockTaskState("I don't have a specific answer for this.")
    score = await scorer_fn(state, None)

    assert score.value == NOANSWER
    assert "No numerical answer found" in score.explanation


@pytest.mark.asyncio
async def test_likert_missing_levels_metadata():
    """Test handling when levels metadata is missing."""
    scorer_fn = likert()

    state = MockTaskState("ANSWER: 5")
    state.metadata = {}  # No levels

    score = await scorer_fn(state, None)

    assert score.value == NOANSWER
    assert "levels" in score.explanation.lower()


@pytest.mark.asyncio
async def test_likert_explanation_contains_details():
    """Test that the explanation contains useful debugging information."""
    scorer_fn = likert()

    state = MockTaskState("ANSWER: 3", levels=7, reverse=True)
    score = await scorer_fn(state, None)

    assert "Levels: 7" in score.explanation
    assert "Raw score: 3" in score.explanation
    assert "Reverse-scored: True" in score.explanation
    assert "Final score: 5" in score.explanation
