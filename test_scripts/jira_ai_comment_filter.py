"""Use AI to pick which comments are relevant to solving the issue.

This script narrows the candidate set returned by `pull_jira_comments.search_relevant_comments`
by asking Azure OpenAI to classify which comments are actually relevant. It prints
the selected comment IDs and a short rationale score per comment.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Annotated, Any, cast

from jira import Comment, Issue
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# Allow running this script directly: ensure the workspace root is on sys.path so
# `from src.config import settings` works whether the package is imported or the
# script is executed as `python test_scripts/pinecone_connection.py`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ROOT_SRC = os.path.join(ROOT, "src")
if ROOT_SRC not in sys.path:
    sys.path.insert(0, ROOT_SRC)


from pull_jira_comments import search_relevant_comments

from src.config import settings
from src.services import Controller

log = logging.getLogger(settings.log.name)


# Reusable score type for JSON Schema (emits minimum/maximum)
Score = Annotated[float, Field(ge=0, le=1)]


class RelevantSelectionModel(BaseModel):
    """Pydantic-validated structure for the AI response JSON."""

    # Emit additionalProperties: false at the top-level
    model_config = ConfigDict(extra="forbid")

    scores: dict[str, Score] = Field(default_factory=dict)

    @classmethod
    @field_validator("scores", mode="after")
    def _validate_scores(cls, v: dict[str, Any]) -> dict[str, float]:
        filtered: dict[str, float] = {}
        for k, val in v.items():
            try:
                f = float(val)
            except Exception:
                continue
            if 0.0 <= f <= 1.0:
                filtered[str(k)] = f
        return filtered


def _compact(text: str, limit: int = 1200) -> str:
    """Trim text to a safe token budget while keeping structure."""
    text = (text or "").replace("\r", "").strip()
    if len(text) <= limit:
        return text
    # Keep first N chars and last short tail to preserve clues
    head = text[: limit - 200]
    tail = text[-180:]
    return f"{head}\n…\n{tail}"


def _build_messages(issue: Issue, comments: list[Comment]) -> list[dict[str, Any]]:
    """Build a JSON-friendly messages array for Chat Completions."""
    summary = cast(str, getattr(issue.fields, "summary", ""))
    description = cast(str, getattr(issue.fields, "description", "") or "")
    created = cast(str, getattr(issue.fields, "created", ""))

    system = (
        "You are a senior triage engineer. The Jira issue has already been resolved. "
        "Identify which of the provided comments were relevant to diagnosing or fixing the issue."
        "\nGuidelines:"
        "\n- Relevant: technical findings, steps taken, logs, config, root-cause clues, links to authoritative docs, direct fix instructions, code changes."
        "\n- Not relevant: chit-chat, thanks, scheduling, duplicated text, off-topic, meta commentary."
        "\n- Prefer comments that contain concrete steps, error messages, or references that directly contributed to the resolution."
        "\nReturn a single JSON object only with keys: scores (object mapping id->0..1 (float))."
    )

    user_payload: dict[str, Any] = {
        "issue": {
            "key": issue.key,
            "summary": _compact(summary, 500),
            "description": _compact(description, 1500),
            "created": created,
        },
        "comments": [
            {
                "id": str(c.id),
                "author": cast(str, getattr(c.author, "displayName", "")),
                "created": cast(str, getattr(c, "created", "")),
                "body": _compact(str(c.body), 1500),
            }
            for c in comments
        ],
        "output_schema": {
            "scores": {"<comment_id>": 0.1},
        },
    }

    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                "You must answer with a single JSON object only, no extra text.\n"
                + json.dumps(user_payload, ensure_ascii=False)
            ),
        },
    ]


def _extract_json(s: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from model output."""
    s = s.strip()
    # If it's already valid JSON
    try:
        return cast(dict[str, Any], json.loads(s))
    except Exception:
        pass
    # Try to pull the first {...} block
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return cast(dict[str, Any], json.loads(m.group(0)))
        except Exception:
            return None
    return None


def ai_filter_relevant_comments(
    issue: Issue, controller: Controller
) -> tuple[list[Comment], dict[str, float]]:
    """Use Azure OpenAI to select relevant comments.

    Returns (selected_comments, scores_by_id).
    """

    messages = _build_messages(issue, issue.fields.comment.comments)

    completion = controller.triage_client.chat.completions.create(
        model=settings.azure.triage.deployment_name,
        messages=messages,  # type: ignore[arg-type]
        max_completion_tokens=500,
        temperature=0.1,
    )
    content = completion.choices[0].message.content or ""
    raw = _extract_json(content) or {"scores": {}}
    try:
        parsed = RelevantSelectionModel.model_validate(raw)
    except ValidationError as exc:
        log.warning("AI response validation failed: %s", exc)
        parsed = RelevantSelectionModel()  # fall back to empty selection

    id_set = {str(i) for i in parsed.scores.keys() if parsed.scores[i] >= 0.5}

    selected = [c for c in issue.fields.comment.comments if str(c.id) in id_set]
    return selected, parsed.scores


def process_issue(issue: Issue, controller: Controller):
    log.info(
        "Processing %s with %d candidate comments: %s",
        issue.key,
        len(issue.fields.comment.comments),
        ", ".join(str(c.id) for c in issue.fields.comment.comments),
    )

    selected, scores = ai_filter_relevant_comments(issue, controller)
    if not selected:
        log.info("No relevant comments selected by AI for %s", issue.key)
        return
    base_ids = {str(c.id) for c in issue.fields.comment.comments}
    selected_ids = {str(c.id) for c in selected}
    if not selected_ids.issubset(base_ids):
        log.warning(
            "Selected comments include IDs not in the candidate set for %s", issue.key
        )

    # Pretty-print a short report
    log.info(
        "AI selected %d of %d comments for %s:",
        len(selected),
        len(issue.fields.comment.comments),
        issue.key,
    )
    log.info(
        ", ".join(f"{c.id} (score={scores.get(str(c.id), 0):.2f})" for c in selected)
    )


def main():
    controller = Controller()
    matching_comments = search_relevant_comments()
    log.info(
        f"Found {sum(len(comments) for comments in matching_comments.values())} comments in {len(matching_comments.keys())} issues\n({', '.join(issue.key for issue in matching_comments.keys())})"
    )

    for issue in matching_comments.keys():
        process_issue(issue, controller)


if __name__ == "__main__":
    main()
