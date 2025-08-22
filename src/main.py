from __future__ import annotations

import datetime
import os
import time
from typing import Any, Dict, List, Tuple, cast

from jira import JIRA
from openai import AzureOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pinecone import Pinecone
from requests_toolbelt import user_agent  # type: ignore

from config import log, settings

# from prompt import Prompt

__version__ = "0.0.0"

assert __version__ is not None, "Version must be set"


def main():
    log.info("Application started.")

    # * Initialize connections

    jira = JIRA(
        settings.jira.server,
        basic_auth=(settings.jira.email, settings.jira.api_token),
        options={
            "headers": {
                "User-Agent": user_agent(settings.jira.user_agent, __version__)
            },
        },
    )

    client = AzureOpenAI(
        azure_endpoint=settings.azure.endpoint,
        azure_deployment=settings.azure.deployment_name,
        api_key=settings.azure.api_key,
        api_version=settings.azure.api_version,
    )

    embedding_client = AzureOpenAI(
        api_key=settings.azure.api_key,
        api_version=settings.azure.api_version,
        azure_endpoint=settings.azure.embedding.endpoint,
    )

    pc = Pinecone(api_key=settings.pinecone.api_key)
    index_info = cast(Any, pc.describe_index(name=settings.pinecone.index_name))
    idx = pc.Index(host=cast(str, index_info.host))

    # * Fetch issue

    issue = jira.issue("PLAYG-149")

    log.info("Processing issue %s", issue.key)
    # log.info(issue.fields.summary + "\n" + (issue.fields.description or ""))

    onlinehelp_comment = None
    for comment in issue.fields.comment.comments:
        # Check if any relevant phrases are mentioned in the first two lines
        if any(
            phrase in "".join(str(comment.body).lower().split("\n", 2)[:2])
            for phrase in ["online help", "doc & test"]
        ):
            onlinehelp_comment = comment
            break
    else:
        log.warning("No online help comment found for %s.", issue.key)
        exit(1)

    # * Query Pinecone

    query_embedding = (
        embedding_client.embeddings.create(
            model=settings.azure.embedding.deployment_name,
            input=onlinehelp_comment.body,
        )
        .data[0]
        .embedding
    )

    results = cast(
        Any,
        idx.query(
            vector=query_embedding,
            top_k=10,
            namespace=settings.pinecone.namespace,
            include_metadata=True,
            # filter={"metadata_key": { "$eq": "value1" }}
        ),
    )

    references = [doc["metadata"]["source"] for doc in results.matches]

    log.info("Found %d references", len(references))

    # * Read the system prompt

    PROMPTS_DIR = os.path.abspath(os.path.join("prompt"))
    SYSTEM_PROMPT_PATH = os.path.join(PROMPTS_DIR, "system.md")
    log.info("Using system prompt: %s", SYSTEM_PROMPT_PATH)
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # * Build user prompt

    user_prompt = (
        "\n".join(
            [
                f"# Reference {i+1}\n{match['metadata']['text'].replace('\n#', '\n##')}\n"
                for i, match in enumerate(results["matches"])
            ]
        )
        + f"\n# {issue.fields.summary}\n{issue.fields.description or ''}\n"
        + f"# {onlinehelp_comment.body}"
    ).replace("\r", "")

    log.info("Using model: %s", settings.azure.deployment_name)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Write messages to PROMPTS_DIR/issues/issuekey.json
    issues_dir = os.path.join(PROMPTS_DIR, "issues", issue.key)
    os.makedirs(issues_dir, exist_ok=True)
    for message in messages:
        message_path = os.path.join(issues_dir, f"{message['role']}.md")
        with open(message_path, "w", encoding="utf-8") as f:
            f.write(str(message.get("content", "")))

    log.info("Wrote messages to %s", issues_dir)

    log.info("Generating the completion...")
    start_time = time.time()
    completion = client.chat.completions.create(
        model=settings.azure.deployment_name,
        messages=messages,
        max_completion_tokens=16384,
        stop=None,
        stream=False,
    )
    completion_content = completion.choices[0].message.content or ""
    # with open(
    #     os.path.join(PROMPTS_DIR, "issues", "PLAYG-149", "result.md"),
    #     "r",
    #     encoding="utf-8",
    # ) as f:
    #     completion_content = f.read()
    elapsed_time = time.time() - start_time
    log.info("Query took %.2f seconds", elapsed_time)

    out_path = os.path.join(issues_dir, "result.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(completion_content)
    log.info("Wrote completion output to %s", out_path)

    # * Build comment

    seen: set[str] = set()
    refs_list: List[Tuple[str, str, str]] = []
    today = datetime.date.today().isoformat()
    for m in results["matches"]:
        meta: Dict[str, Any] = m.get("metadata")
        source = str(meta.get("source"))
        if not source or source in seen:
            continue
        seen.add(source)

        # Friendly name (basename of URL when possible)
        name = source
        if source.startswith("http"):
            base = (
                os.path.basename(source.rstrip("/")).lstrip(".").replace("_", " ")
                or source
            )
            name = base.rsplit(".", 1)[0] if "." in base else base

        refs_list.append((name, source, today))
    # Build a plain-text comment compatible with Jira REST API v2
    # (ADF payloads are not supported by API v2 in many instances)
    content_text = completion_content or ""
    paragraphs = [p.strip() for p in content_text.split("\n\n") if p.strip()]

    comment_lines: List[str] = []
    for p in paragraphs:
        # preserve paragraphs separated by a blank line
        comment_lines.append(p.replace("\r", ""))
        comment_lines.append("")

    if refs_list:
        # Render references as a Jira wiki-format table.
        # First column: link in wiki syntax [name|url]
        # Second column: date accessed
        # Header row uses double pipes for header cells
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

    # Add the completion output as a plain-text comment to the Jira issue
    # jira.add_comment expects a simple string body for API v2 compatibility
    jira.add_comment(issue, comment_text)
    log.info("Added completion output (plain-text) as a comment to issue %s", issue.key)


if __name__ == "__main__":
    main()
