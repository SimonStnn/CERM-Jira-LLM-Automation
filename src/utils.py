from __future__ import annotations

import datetime
import json
import os
from typing import Any

from config import log


def build_jira_comment(
    *,
    completion_content: str | None,
    results: Any,
    issues_dir: str,
) -> tuple[str, dict[str, Any]]:
    """Build a plain-text Jira comment and an ADF payload for the same content.

    Returns (comment_text, adf_dict). The function will write audit files to
    ``issues_dir`` and will attempt to post the ADF to Jira when
    ``settings.jira.post_adf`` is True. Posting failures are logged but do not
    raise.
    """
    seen: set[str] = set()
    refs_list: list[tuple[str, str, str]] = []
    today = datetime.date.today().isoformat()
    for m in results["matches"]:
        meta: dict[str, Any] = m.get("metadata")
        source = meta.get("source")
        if not source or (source := str(source)) in seen:
            continue
        seen.add(source)
        name = str(
            meta.get(
                "title",
                (
                    os.path.basename(source.rstrip("/")).lstrip(".").replace("_", " ")
                    or source
                ).rsplit(".", 1)[0],
            )
        )

        refs_list.append((name, source, today))

    # Build a plain-text comment compatible with Jira REST API v2
    content_text = completion_content or ""
    paragraphs = [p.strip() for p in content_text.split("\n\n") if p.strip()]

    comment_lines: list[str] = []
    for p in paragraphs:
        # preserve paragraphs separated by a blank line
        comment_lines.append(p.replace("\r", ""))
        comment_lines.append("")

    if refs_list:
        comment_lines.append("||References||Date accessed||")
        for name, source, date_accessed in refs_list:
            link = f"[{name}|{source}]"
            comment_lines.append(f"|{link}|{date_accessed}|")
        comment_lines.append("")

    comment_text = "\n".join(comment_lines).strip()

    # Write a plain-text copy for auditing
    out_path = os.path.join(issues_dir, "comment.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(comment_text)
    log.info("Wrote plain-text comment to %s", out_path)

    # Build a Jira ADF comment where the references table lives inside an expand node.
    adf: dict[str, Any] = {"type": "doc", "version": 1, "content": []}

    if refs_list:
        # Construct table rows: header + one row per reference
        headers = ["Reference", "Date accessed"]
        header_row: dict[str, Any] = {
            "type": "tableRow",
            "content": [
                {
                    "type": "tableHeader",
                    "attrs": {},
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": header}],
                        }
                    ],
                }
                for header in headers
            ],
        }

        rows: list[dict[str, Any]] = [header_row]
        for name, source, date_accessed in refs_list:
            rows.append(
                {
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "attrs": {},
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": name,
                                            "marks": [
                                                {
                                                    "type": "link",
                                                    "attrs": {"href": source},
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "tableCell",
                            "attrs": {},
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {"type": "text", "text": date_accessed}
                                    ],
                                }
                            ],
                        },
                    ],
                }
            )

        # Build paragraph nodes from the completion output so the ADF shows
        # the generated completion first. Keep it simple: split on double-new
        adf_paragraphs: list[dict[str, Any]] = [
            {"type": "paragraph", "content": [{"type": "text", "text": p.strip()}]}
            for p in (completion_content or "").split("\n\n")
            if p.strip()
        ]

        table_node: dict[str, Any] = {
            "type": "table",
            "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": rows,
        }

        if adf_paragraphs:
            adf["content"].extend(adf_paragraphs)

        expand_node: dict[str, Any] = {
            "type": "expand",
            "attrs": {"title": "References"},
            "content": [table_node],
        }

        adf["content"].append(expand_node)

    # Save the ADF payload for auditing
    adf_out = os.path.join(issues_dir, "comment.adf.json")
    with open(adf_out, "w", encoding="utf-8") as f:
        json.dump(adf, f, ensure_ascii=False, indent=2)
    log.info("Wrote ADF comment payload to %s", adf_out)

    return comment_text, adf
