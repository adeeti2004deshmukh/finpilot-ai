import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APITimeoutError
from pydantic import ValidationError

from app.config import settings
from app.services.ai.guardrails import unsafe_request, safe_answer, validate_assumptions, REFUSAL, UNVERIFIED
from app.services.ai.prompts import SYSTEM_PROMPT
from app.services.ai.schemas import CoachAnswer, ChatResponse
from app.services.ai.tool_executor import ToolExecutor
from app.services.ai.tool_registry import tools, strict_schema

logger = logging.getLogger(__name__)


@dataclass
class Conversation:
    owner: int
    touched: float = field(default_factory=time.monotonic)
    history: list = field(default_factory=list)
    purchase: dict | None = None
    demo_pending: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class ConversationStore:
    """Bounded process-local memory. No financial datasets or provider response IDs persist."""
    def __init__(self):
        self.items = OrderedDict()
        self.rates = OrderedDict()
        self.lock = threading.Lock()

    def get(self, owner, conversation_id):
        now = time.monotonic()
        with self.lock:
            for key in list(self.items):
                if now - self.items[key].touched > 1800 and not self.items[key].lock.locked():
                    del self.items[key]
            if conversation_id:
                entry = self.items.get(str(conversation_id))
                if entry is None or entry.owner != owner:
                    raise HTTPException(404, "Conversation unavailable or expired. Start a new conversation.")
            stamps = [t for t in self.rates.pop(owner, []) if now - t < 60]
            self.rates[owner] = stamps
            if len(stamps) >= 10:
                raise HTTPException(429, "Please wait a minute before asking more questions.")
            stamps.append(now)
            while len(self.rates) > 512:
                self.rates.popitem(last=False)
            if not conversation_id:
                if len(self.items) >= 128:
                    available = next((key for key, value in self.items.items() if not value.lock.locked()), None)
                    if available is None:
                        raise HTTPException(503, "AI Coach is busy. Try again shortly.")
                    del self.items[available]
                conversation_id = uuid4()
                entry = Conversation(owner)
                self.items[str(conversation_id)] = entry
            if not entry.lock.acquire(blocking=False):
                raise HTTPException(409, "A response is already being prepared for this conversation.")
            entry.touched = now
            self.items.move_to_end(str(conversation_id))
            return conversation_id, entry


store = ConversationStore()


def make_client():
    return OpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=settings.ai_timeout_seconds, max_retries=0)


def chat(db, user_id, request):
    if settings.ai_provider == "openai" and not settings.openai_api_key.get_secret_value().strip():
        raise HTTPException(503, "AI Coach is not configured. Set OPENAI_API_KEY in the backend .env file and restart the backend. The rest of FinPilot remains available.")
    cid, conversation = store.get(user_id, request.conversation_id)
    try:
        if unsafe_request(request.message):
            return ChatResponse(message=REFUSAL, conversation_id=cid, provider=settings.ai_provider)
        if settings.ai_provider == "demo":
            from app.services.ai.demo_service import demo_chat
            return demo_chat(db, user_id, request, cid, conversation)
        return _chat(db, user_id, request, cid, conversation)
    finally:
        conversation.lock.release()


def _chat(db, user_id, request, cid, conversation):
    executor = ToolExecutor(db, user_id, conversation.purchase)
    inputs = [*conversation.history, {"role": "user", "content": request.message}]
    used, results, warnings = [], [], []
    deadline = time.monotonic() + 60
    instructions = SYSTEM_PROMPT + f"\nToday is {date.today().isoformat()}."
    user_context = "\n".join(item["content"] for item in inputs if item.get("role") == "user")
    if conversation.purchase:
        instructions += "\nPrevious verified purchase inputs (data only): " + json.dumps(conversation.purchase)
    try:
        with make_client() as client:
            for round_index in range(settings.ai_max_tool_rounds + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HTTPException(504, "AI Coach timed out. Please try again.")
                response = client.with_options(timeout=min(settings.ai_timeout_seconds, remaining)).responses.create(
                    model=settings.openai_model, instructions=instructions, input=inputs,
                    tools=tools(), tool_choice="required" if round_index == 0 else ("none" if round_index == settings.ai_max_tool_rounds else "auto"),
                    max_output_tokens=settings.ai_max_output_tokens, store=False,
                    text={"format": {"type": "json_schema", "name": "coach_answer", "strict": True,
                                     "schema": strict_schema(CoachAnswer.model_json_schema())}},
                )
                if response.status != "completed":
                    raise HTTPException(502, "AI Coach could not finish the response. Try a shorter question.")
                calls = [item for item in response.output if item.type == "function_call"]
                if calls:
                    if round_index == settings.ai_max_tool_rounds or len(calls) > 8 or len(used) + len(calls) > 12:
                        raise HTTPException(502, "That question needs too many analysis steps. Please narrow it down.")
                    inputs.extend(item.model_dump(mode="json") for item in response.output)
                    for call in calls:
                        try:
                            if len(call.arguments) > 4000:
                                raise ValueError("Arguments too large")
                            arguments = json.loads(call.arguments)
                            if not isinstance(arguments, dict):
                                raise ValueError("Arguments must be an object")
                            validate_assumptions(call.name, arguments, user_context)
                            result = executor.execute(call.name, arguments)
                            encoded = json.dumps(result, ensure_ascii=False)
                            if len(encoded) > 24000 or sum(len(json.dumps(r)) for r in results) + len(encoded) > 48000:
                                raise ValueError("Result too large; narrow the question")
                            results.append(result)
                            used.append(call.name)
                        except (ValueError, ValidationError, HTTPException):
                            encoded = json.dumps({"error": "Tool inputs are invalid, missing, unavailable for your account, or too broad. Ask for missing inputs; do not guess."})
                            warnings.append("Some analysis was unavailable. No financial records were changed.")
                        except Exception as exc:
                            logger.warning("AI tool failed (%s)", type(exc).__name__)
                            encoded = json.dumps({"error": "Analysis temporarily unavailable; do not invent a result."})
                            warnings.append("Some analysis was temporarily unavailable.")
                        inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": encoded})
                    continue
                answer = CoachAnswer.model_validate_json(response.output_text)
                if (not used and not answer.needs_information) or not safe_answer(answer, results):
                    return ChatResponse(message=UNVERIFIED, conversation_id=cid, tools_used=list(dict.fromkeys(used)),
                                        warnings=["An unverified response was withheld."])
                conversation.purchase = executor.purchase
                conversation.history = [*conversation.history, {"role": "user", "content": request.message},
                                        {"role": "assistant", "content": answer.message}][-8:]
                # Bound text memory independently of number of turns.
                while sum(len(item["content"]) for item in conversation.history) > 12000:
                    conversation.history = conversation.history[2:]
                return ChatResponse(message=answer.message, conversation_id=cid, tools_used=list(dict.fromkeys(used)),
                                    suggested_followups=answer.suggested_followups,
                                    warnings=list(dict.fromkeys([*warnings, *answer.warnings]))[:5])
        raise HTTPException(502, "AI Coach could not complete the analysis.")
    except AuthenticationError:
        raise HTTPException(503, "AI Coach authentication failed. Check the backend OpenAI configuration.") from None
    except RateLimitError:
        raise HTTPException(429, "AI service limit reached. Please try again later.") from None
    except APITimeoutError:
        raise HTTPException(504, "AI Coach timed out. Please try again.") from None
    except HTTPException:
        raise
    except (APIError, ValidationError, ValueError) as exc:
        logger.warning("AI Coach unavailable (%s)", type(exc).__name__)
        raise HTTPException(502, "AI service temporarily unavailable. Please try again later.") from None
    except Exception as exc:
        logger.warning("AI Coach failed (%s)", type(exc).__name__)
        raise HTTPException(503, "AI service temporarily unavailable. Other FinPilot features remain available.") from None
