"""Tests for the OpenRouter Decisions API provider."""

import json

import httpx
import pytest
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig

from specieval.providers.decisions import (
    LIKERT_CRITERIA,
    OpenRouterDecisionsAPI,
    decision_to_output,
)


def _body(probabilities, score=0.0):
    return {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            "likert": {
                "type": "score",
                "score": score,
                "probabilities": probabilities,
                "confidence": 0.8,
            }
        },
        "usage": {"input_tokens": 300, "output_tokens": 18, "cost": 1e-5},
    }


def test_output_is_one_indexed_answer():
    """A certain decision on level "6" becomes 7 on the 1-7 scale."""
    probs = {str(i): 0.0 for i in range(7)} | {"6": 1.0}
    output = decision_to_output(_body(probs, score=6.0), "typesafe/jev-1.13")
    assert output.completion == "ANSWER: 7.00"
    assert output.metadata["expected_score"] == 7.0
    assert output.metadata["probabilities"]["7"] == 1.0
    assert output.usage.input_tokens == 300


def test_output_is_expected_score():
    """A split decision reports the distribution's expected value."""
    probs = {str(i): 0.0 for i in range(7)} | {"1": 0.5, "3": 0.5}
    output = decision_to_output(_body(probs, score=2.0), "m")
    assert output.completion == "ANSWER: 3.00"
    assert output.metadata["expected_score"] == 3.0


@pytest.mark.asyncio
async def test_generate_request_shape(monkeypatch):
    """System message becomes instructions; the rest becomes state."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_body({"0": 1.0}))

    api = OpenRouterDecisionsAPI("typesafe/jev-1.13")
    api.transport = httpx.MockTransport(handler)

    output, _ = await api.generate(
        [ChatMessageSystem(content="Rate this."), ChatMessageUser(content="Cats.")],
        tools=[],
        tool_choice="none",
        config=GenerateConfig(),
    )

    question = requests[0]["questions"]["likert"]
    assert requests[0]["model"] == "typesafe/jev-1.13"
    assert requests[0]["state"] == "Cats."
    assert question == {
        "type": "score",
        "instructions": "Rate this.",
        "criteria": LIKERT_CRITERIA,
    }
    assert output.completion == "ANSWER: 1.00"


@pytest.mark.asyncio
async def test_generate_returns_client_errors(monkeypatch):
    """Unretryable API errors are returned with the call so they get logged."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    error = {"error": {"message": "only noul questions", "code": 400}}

    api = OpenRouterDecisionsAPI("respan/span-01")
    api.transport = httpx.MockTransport(lambda r: httpx.Response(400, json=error))

    output, call = await api.generate(
        [ChatMessageUser(content="Cats.")],
        tools=[],
        tool_choice="none",
        config=GenerateConfig(),
    )

    assert isinstance(output, RuntimeError)
    assert "only noul questions" in str(output)
    assert call.response == error
