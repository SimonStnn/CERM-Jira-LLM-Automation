from __future__ import annotations

import json
import logging
import os
import re
import time

from jira import Issue

from config import __version__, settings
from services import Controller
from services.builder import PromptBuilder
from services.gatherer import IssueGatherer
from utils import save_to_file, setup_logging

assert __version__ is not None, "Version must be set"


setup_logging()


log = logging.getLogger(settings.log.name)


def process_issue(
    gatherer: IssueGatherer, controller: Controller, system_prompt: str, issue: Issue
):
    log.info("---===== Processing issue %s... =====---", issue.key)
    issue_start_time = time.time()
    builder = PromptBuilder(
        system_prompt=system_prompt,
        issue=issue,
    )

    log.info("Filtering comments for issue %s using...", issue.key)
    comments, scores = gatherer.ai_filter_comments(controller.triage_client, issue)
    if not comments or len(comments) == 0:
        log.warning("No relevant comments found for issue %s", issue.key)
    log.info("Found %d relevant comments for issue %s", len(comments), issue.key)

    save_to_file(json.dumps(scores), "comment_scores.json", subdir=issue.key)

    for comment in comments:
        builder.user_comments.append(
            {
                "author": comment.author.displayName,
                "content": comment.body,
            }
        )

    # * Query Pinecone for relevant documentation

    TOP_K = 10

    log.info("Querying Pinecone for relevant documents... (top_k=%d)", TOP_K)
    pinecone_results = gatherer.query_pinecone(issue.fields.summary, top_k=TOP_K)
    log.info(
        "Found %d relevant documents for issue %s", len(pinecone_results), issue.key
    )

    builder.docs_references.extend(pinecone_results)

    save_to_file(
        json.dumps([doc.to_dict() for doc in pinecone_results]),
        "pinecone_results.json",
        subdir=issue.key,
    )

    # * Build prompt

    compiled_messages = builder.compile_messages()

    for i, message in enumerate(compiled_messages):
        save_to_file(
            json.dumps(getattr(message, "content", "")),
            f"prompt_{i}.{message['role']}.md",
            subdir=os.path.join(issue.key, "prompt"),
        )

    # * Generate completion

    log.info("Generating the completion...")
    completion_start_time = time.time()
    completion = controller.generate_completion(messages=compiled_messages)
    log.info(
        "Obtained completion (took %.2f seconds)",
        time.time() - completion_start_time,
    )

    save_to_file(completion, "completion.md", subdir=issue.key)

    # * Find the comment to reply to

    keywords_pat = "|".join(re.escape(k) for k in settings.keywords)
    pattern = re.compile(rf"^h[1-6]\.\s*(?:{keywords_pat})\b", re.IGNORECASE)
    target_comment = IssueGatherer.get_target_comment(comments, pattern)

    if not target_comment:
        log.warning("No target comment found for issue %s", issue.key)

    # * Build jira content

    _, adf = gatherer.build_jira_comment(
        completion_content=completion,
        references=pinecone_results,
    )

    save_to_file(json.dumps(adf), "adf.json", subdir=issue.key)

    # * Post the ADF reply

    gatherer.post_adf(issue, adf, reply_comment=target_comment)

    log.info(
        "---===== Finished processing issue %s (took %.2f seconds) =====---",
        issue.key,
        time.time() - issue_start_time,
    )


def main():
    log.info("Application started (v%s)", __version__)

    gatherer = IssueGatherer()
    controller = Controller()

    # Log settings
    save_to_file(settings.model_dump_json(), "settings.json")

    # * Get system prompt

    system_prompt = PromptBuilder.get_system_prompt()

    # * Query jira for issues

    jira = gatherer.jira

    jira_user = jira.user(jira.current_user())

    JQL_PROJECTS = '", "'.join(settings.projects)
    JQL_KEYWORDS = " OR ".join(
        f'comment ~ "{keyword}"' for keyword in settings.keywords
    )
    JQL = (
        f"updated >= -1w"
        f' AND project in ("{JQL_PROJECTS}")'
        f" AND ({JQL_KEYWORDS})"
        f' AND NOT issue in updatedBy("{jira_user.displayName}")'
        f" ORDER BY updated DESC"
    )

    save_to_file(JQL, "jira_query.jql")

    log.info("Searching with JQL: '%s'...", JQL)
    issues = gatherer.query(JQL)
    log.info(
        "Processing %d issues... (%s)",
        len(issues),
        ", ".join(issue.key for issue in issues),
    )

    save_to_file(json.dumps([issue.key for issue in issues]), "jira_issues.json")

    # * Filter relevant comments from issue

    for issue in issues:
        try:
            process_issue(gatherer, controller, system_prompt, issue)
        except Exception as e:
            log.error("Error processing issue %s: %s", issue.key, e)


if __name__ == "__main__":
    main()
