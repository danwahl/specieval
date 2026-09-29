"""Inspect model provider for the OpenRouter Decisions API.

Decision models such as TypeSafe's Jev do not generate text: they take a state
plus typed questions and return a probability distribution over the answers.
They are served from a separate endpoint (`/api/alpha/decisions`), so Inspect's
chat-completions `openrouter` provider cannot call them.

This provider poses each Likert item as a single `score` question. The system
message becomes the question's instructions, the remaining conversation becomes
the state, and the response scale becomes the ordered criteria.

The answer is the distribution's expected value, which is the quantity a chat
model's epoch mean estimates by sampling. It is recorded as `expected_score` in
the output metadata (which the Likert scorer prefers when present) and rendered
as "ANSWER: N" alongside the full distribution.

Usage:
    inspect eval specieval/speciesism --model openrouter-decisions/typesafe/jev-1.13
"""

import os
from typing import Any

import httpx
from inspect_ai.model import (
    ChatMessage,
    ChatMessageSystem,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
    ModelUsage,
    modelapi,
)
from inspect_ai.model._model_call import ModelCall
from inspect_ai.tool import ToolChoice, ToolInfo

DECISIONS_API = "openrouter-decisions"
DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"

# Ordered labels for the 7-point scale used by every SpeciEval task.
LIKERT_CRITERIA = [
    "Strongly Disagree",
    "Disagree",
    "Somewhat Disagree",
    "Neither agree nor disagree",
    "Somewhat Agree",
    "Agree",
    "Strongly Agree",
]


@modelapi(name=DECISIONS_API)
class OpenRouterDecisionsAPI(ModelAPI):
    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),
        **model_args: Any,
    ) -> None:
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            api_key_vars=["OPENROUTER_API_KEY"],
            config=config,
        )
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable not set.")
        self.timeout = config.timeout or 60
        # Overridable for tests.
        self.transport: httpx.AsyncBaseTransport | None = None

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> tuple[ModelOutput | Exception, ModelCall]:
        instructions = "\n\n".join(
            m.text for m in input if isinstance(m, ChatMessageSystem)
        )
        # A plain string is the one state format every decision provider accepts.
        state = "\n\n".join(
            m.text for m in input if not isinstance(m, ChatMessageSystem)
        )
        request = {
            "model": self.model_name,
            "state": state,
            "questions": {
                "likert": {
                    "type": "score",
                    "instructions": instructions,
                    "criteria": LIKERT_CRITERIA,
                }
            },
        }

        # A client per request, since eval-set retries run on a fresh event loop.
        async with httpx.AsyncClient(
            timeout=self.timeout, transport=self.transport
        ) as client:
            response = await client.post(
                self.base_url or DECISIONS_URL,
                json=request,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        body = response.json()
        call = ModelCall.create(request=request, response=body)

        # Raise retryable errors; return the rest so the call is logged.
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as ex:
            if self.should_retry(ex):
                raise
            return RuntimeError(f"{ex}\n{body.get('error', body)}"), call

        return decision_to_output(body, self.model_name), call

    def should_retry(self, ex: Exception) -> bool:
        if isinstance(ex, httpx.HTTPStatusError):
            return ex.response.status_code == 429 or ex.response.status_code >= 500
        return isinstance(ex, httpx.TransportError)

    def connection_key(self) -> str:
        return DECISIONS_API


def decision_to_output(body: dict[str, Any], model: str) -> ModelOutput:
    """Convert a `score` decision response to a 1-indexed Likert answer."""
    answer = body["answers"]["likert"]
    # Levels are keyed "0".."6"; shift to the 1..7 scale the scorer expects.
    expected = answer["score"] + 1
    probabilities = {str(int(k) + 1): p for k, p in answer["probabilities"].items()}

    output = ModelOutput.from_content(
        model=body.get("model", model), content=f"ANSWER: {expected:.2f}"
    )
    output.metadata = {
        "probabilities": probabilities,
        "expected_score": expected,
        "confidence": answer.get("confidence"),
        "cost": body.get("usage", {}).get("cost"),
    }
    usage = body.get("usage", {})
    output.usage = ModelUsage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    )
    return output
