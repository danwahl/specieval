"""Tests for the chain-of-thought prompt solver."""

import pytest
from inspect_ai.model import ChatMessageUser, ModelName
from inspect_ai.solver import TaskState

from specieval.solvers import cot_template

TEMPLATE = "{prompt}\n\nReason, then ANSWER: 1-{levels}."


def _state(model):
    return TaskState(
        model=ModelName(model),
        sample_id="x",
        epoch=1,
        input="Cats are nice.",
        messages=[ChatMessageUser(content="Cats are nice.")],
        metadata={"levels": 7},
    )


async def _noop(state, **kwargs):
    return state


@pytest.mark.asyncio
async def test_applies_template_for_chat_models():
    state = await cot_template(TEMPLATE)(_state("openrouter/openai/gpt-4.1"), _noop)
    assert state.user_prompt.text == "Cats are nice.\n\nReason, then ANSWER: 1-7."


@pytest.mark.asyncio
async def test_skips_template_for_decision_models():
    model = "openrouter-decisions/typesafe/jev-1.13"
    state = await cot_template(TEMPLATE)(_state(model), _noop)
    assert state.user_prompt.text == "Cats are nice."
