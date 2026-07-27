"""Tests for the retry-on-refusal solver."""

import pytest
from inspect_ai.model import ChatMessageAssistant, ModelName, ModelOutput
from inspect_ai.solver import TaskState
from specieval.solvers.retry import generate_until_answered


def _make_generate(scripted):
    """A fake generate() that returns the scripted completions in order."""
    calls = {"n": 0}

    async def fake_generate(state, **kwargs):
        out = scripted[min(calls["n"], len(scripted) - 1)]
        calls["n"] += 1
        state.output = ModelOutput.from_content("mockllm/model", out)
        state.messages.append(ChatMessageAssistant(content=out))
        return state

    return fake_generate, calls


def _state():
    return TaskState(
        model=ModelName("mockllm/model"),
        sample_id="x",
        epoch=1,
        input="rate this",
        messages=[],
    )


@pytest.mark.asyncio
async def test_retries_until_answered():
    """Re-prompts on unparseable output and recovers a later valid answer."""
    generate, calls = _make_generate(
        ["I won't answer.", "**7 = Strongly Agree**", "ANSWER: 5"]
    )
    state = await generate_until_answered(max_attempts=3)(_state(), generate)

    assert calls["n"] == 3
    assert state.output.completion == "ANSWER: 5"
    # One nudge was appended before each of the two re-attempts.
    assert sum(1 for m in state.messages if m.role == "user") == 2


@pytest.mark.asyncio
async def test_stops_on_first_valid_answer():
    """No extra generations or nudges once a parseable answer appears."""
    generate, calls = _make_generate(["ANSWER: 6", "unused"])
    state = await generate_until_answered(max_attempts=3)(_state(), generate)

    assert calls["n"] == 1
    assert state.output.completion == "ANSWER: 6"
    assert not any(m.role == "user" for m in state.messages)


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts():
    """A persistent refusal exhausts attempts and falls through unscored."""
    generate, calls = _make_generate(["nope"])
    state = await generate_until_answered(max_attempts=3)(_state(), generate)

    assert calls["n"] == 3
    assert "ANSWER" not in state.output.completion
