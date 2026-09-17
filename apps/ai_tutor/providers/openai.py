"""OpenAI Responses API provider.

Text only: no tools, no provider-side storage (``store=False``) and no provider conversation
state. Our own database holds the conversation.
"""

import json

import openai

from apps.ai_tutor.config import TutorConfig
from apps.ai_tutor.constants import ResponseKind
from apps.ai_tutor.prompts import OUTPUT_SCHEMA, SERVER_CONTEXT_HEADER, SUBMISSION_HEADER
from apps.ai_tutor.providers.base import (
    TutorInvalidResponse,
    TutorRateLimited,
    TutorTimeout,
    TutorUnavailable,
)
from apps.ai_tutor.types import TutorProviderRequest, TutorProviderResult

MAX_RETRIES = 1


def build_input(request: TutorProviderRequest) -> list[dict]:
    """Messages in trust order: server facts, conversation, learner data, current message."""
    messages = [
        {
            "role": "developer",
            "content": SERVER_CONTEXT_HEADER
            + "\n"
            + json.dumps(request.server_context, ensure_ascii=False, default=str),
        }
    ]
    for item in request.history:
        messages.append({"role": "user", "content": item.user_message or f"[{item.intent}]"})
        messages.append({"role": "assistant", "content": item.assistant_message})
    if request.learner_submission is not None:
        submission = request.learner_submission
        note = " (truncated)" if submission.truncated else ""
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{SUBMISSION_HEADER}{note}\n<<<SUBMISSION\n{submission.text}\nSUBMISSION>>>"
                ),
            }
        )
    messages.append({"role": "user", "content": request.user_message})
    return messages


def parse_output(text: str | None) -> dict:
    try:
        data = json.loads(text or "")
    except ValueError:
        raise TutorInvalidResponse() from None
    if not isinstance(data, dict) or set(data) != {"reply", "response_kind", "should_retry"}:
        raise TutorInvalidResponse()
    reply, kind, retry = data["reply"], data["response_kind"], data["should_retry"]
    if (
        not isinstance(reply, str)
        or not reply.strip()
        or kind not in ResponseKind.values
        or not isinstance(retry, bool)
    ):
        raise TutorInvalidResponse()
    return data


class OpenAITutorProvider:
    name = "openai"

    def __init__(self, config: TutorConfig, client=None) -> None:
        self.config = config
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = openai.OpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout_seconds,
                max_retries=MAX_RETRIES,
            )
        return self._client

    def generate(self, request: TutorProviderRequest) -> TutorProviderResult:
        try:
            response = self.client.responses.create(
                model=self.config.model,
                instructions=request.instructions,
                input=build_input(request),
                max_output_tokens=min(request.max_output_tokens, self.config.max_output_tokens),
                store=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "tutor_reply",
                        "strict": True,
                        "schema": OUTPUT_SCHEMA,
                    }
                },
            )
        # Map vendor errors to safe ones; never pass vendor messages on.
        except openai.APITimeoutError:
            raise TutorTimeout() from None
        except openai.RateLimitError:
            raise TutorRateLimited() from None
        except openai.OpenAIError:
            raise TutorUnavailable() from None

        if getattr(response, "status", "completed") != "completed":
            raise TutorInvalidResponse()
        data = parse_output(getattr(response, "output_text", None))
        usage = getattr(response, "usage", None)
        return TutorProviderResult(
            reply=data["reply"],
            response_kind=data["response_kind"],
            should_retry=data["should_retry"],
            provider=self.name,
            model=str(getattr(response, "model", "") or self.config.model),
            provider_response_id=str(getattr(response, "id", "") or "")[:128],
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
