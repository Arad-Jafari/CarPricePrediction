from __future__ import annotations

import re
from pathlib import Path

from app.config import REPOSITORY_ROOT

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "car_assistant.txt"
OUT_OF_SCOPE_RESPONSE = (
    "I'm designed to help with car price predictions, vehicle information, "
    "and features of this application. Please ask me something related to those topics."
)
_IN_SCOPE_TERMS = re.compile(
    r"\b(car|cars|vehicle|peugeot|206|price|prediction|estimate|valuation|"
    r"mileage|transmission|trim|body|color|colour|listing|market|model|"
    r"saved|history|application|app|account|feature)\b",
    re.IGNORECASE,
)
_LATEST_PREDICTION_TERMS = re.compile(
    r"\b(my|latest|last|recent|saved)\b.*\b(prediction|estimate|valuation)\b|"
    r"\b(prediction|estimate|valuation)\b.*\b(my|latest|last|recent|saved)\b",
    re.IGNORECASE,
)


def load_system_prompt(path: Path = SYSTEM_PROMPT_PATH) -> str:
    prompt = path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise RuntimeError(f"Assistant system prompt is empty: {path}")
    return prompt


def is_in_scope_request(content: str) -> bool:
    return bool(_IN_SCOPE_TERMS.search(content))


def requests_latest_prediction(content: str) -> bool:
    return bool(_LATEST_PREDICTION_TERMS.search(content))


def build_assistant_messages(
    history: list[dict[str, str]],
    content: str,
    max_history_messages: int,
    authorized_context: str | None = None,
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    if max_history_messages < 1:
        raise ValueError("max_history_messages must be at least 1.")
    prompt = system_prompt or load_system_prompt()
    messages = [{"role": "system", "content": prompt}]
    if authorized_context:
        messages.append({
            "role": "system",
            "content": "Authenticated application data (use only as provided):\n" + authorized_context,
        })
    messages.extend(history[-max_history_messages:])
    messages.append({"role": "user", "content": content})
    return messages


def prompt_path_relative_to_repository() -> str:
    return str(SYSTEM_PROMPT_PATH.relative_to(REPOSITORY_ROOT))
