from __future__ import annotations

import json
import logging
import os
import time

from jira import Issue

from config import __version__, settings
from services import Controller
from services.builder import PromptBuilder
from utils import save_to_file, setup_logging

assert __version__ is not None, "Version must be set"


setup_logging()


log = logging.getLogger(settings.log.name)


def process_issue(
    controller: Controller,
    system_prompt: str,
    lrn_issue: Issue,
):
    log.info("---===== Processing issue %s... =====---", lrn_issue.key)
    issue_start_time = time.time()
    builder = PromptBuilder(
        system_prompt=system_prompt,
        issue=lrn_issue,
    )

    # * Find linked issues

    # Get related CERM7 issue
    issue_keys: list[str] = []
    for link in lrn_issue.fields.issuelinks:
        if hasattr(link, "outwardIssue"):
            outwardIssue = link.outwardIssue
            issue_keys.append(outwardIssue.key)
        if hasattr(link, "inwardIssue"):
            inwardIssue = link.inwardIssue
            issue_keys.append(inwardIssue.key)

    linked_issues = [
        controller.jira.issue(key)
        for key in issue_keys
        if key.startswith(settings.project)
    ]

    if not linked_issues:
        log.warning(
            "No linked %s issues found for issue %s. Only found %s",
            settings.project,
            lrn_issue.key,
            issue_keys,
        )
        return

    issue = linked_issues[0]
    save_to_file(
        json.dumps(
            [
                issue.key,
                f"only processed first linked issue from [{', '.join(issue.key for issue in linked_issues)}]",
            ]
        ),
        "linked_issues.json",
        subdir=lrn_issue.key,
    )

    log.info("Filtering comments for issue %s using...", issue.key)
    comments, scores = controller.ai_filter_comments(issue)
    if not comments or len(comments) == 0:
        log.warning("No relevant comments found for issue %s", issue.key)
    log.info("Found %d relevant comments for issue %s", len(comments), issue.key)

    save_to_file(json.dumps(scores), "comment_scores.json", subdir=lrn_issue.key)

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
    pinecone_results = controller.query_pinecone(issue.fields.summary, top_k=TOP_K)
    log.info(
        "Found %d relevant documents for issue %s", len(pinecone_results), issue.key
    )

    builder.docs_references.extend(pinecone_results)

    save_to_file(
        json.dumps([doc.to_dict() for doc in pinecone_results]),
        "pinecone_results.json",
        subdir=lrn_issue.key,
    )

    # * Build prompt

    compiled_messages = builder.compile_messages()

    for i, message in enumerate(compiled_messages):
        save_to_file(
            str(message.get("content")),
            f"prompt_{i}.{message['role']}.md",
            subdir=os.path.join(lrn_issue.key, "prompt"),
        )

    # * Generate completion

    log.info("Generating the completion...")
    completion_start_time = time.time()
    completion = controller.generate_completion(messages=compiled_messages)
    log.info(
        "Obtained completion (took %.2f seconds)",
        time.time() - completion_start_time,
    )

    save_to_file(completion, "completion.md", subdir=lrn_issue.key)

    # * Find the comment to reply to

    # keywords_pat = "|".join(re.escape(k) for k in settings.keywords)
    # pattern = re.compile(rf"^h[1-6]\.\s*(?:{keywords_pat})\b", re.IGNORECASE)
    # target_comment = Controller.get_target_comment(comments, pattern)

    # if not target_comment:
    #     log.warning("No target comment found for issue %s", issue.key)

    # * Build jira content

    _, adf = controller.build_jira_comment(
        completion_content=completion,
        references=pinecone_results,
    )

    save_to_file(json.dumps(adf), "adf.json", subdir=lrn_issue.key)

    # * Post the ADF reply

    controller.post_adf(lrn_issue, adf)  # , reply_comment=target_comment)

    log.info("Posted ADF reply for issue %s", lrn_issue.key)

    log.info(
        "---===== Finished processing issue %s (took %.2f seconds) =====---",
        issue.key,
        time.time() - issue_start_time,
    )


def main():
    log.info("Application started (v%s)", __version__)

    controller = Controller()

    # Log settings
    save_to_file(settings.model_dump_json(), "settings.json")

    # * Get system prompt

    system_prompt = PromptBuilder.get_system_prompt()

    # * Query jira for issues

    save_to_file(settings.jira_query, "jira_query.jql")

    log.info("Searching with JQL: '%s'...", settings.jira_query)
    log.info("Fetching issues from Jira since '%s'", settings.pipeline_last_run_utc)
    lrn_issues = controller.query(settings.jira_query)
    log.info(
        "Processing %d issues... (%s)",
        len(lrn_issues),
        ", ".join(issue.key for issue in lrn_issues),
    )

    save_to_file(json.dumps([issue.key for issue in lrn_issues]), "jira_issues.json")

    # * Filter relevant comments from issue

    for lrn_issue in lrn_issues:
        try:
            process_issue(controller, system_prompt, lrn_issue)
        except Exception as e:
            log.error("Error processing issue %s: %s", lrn_issue.key, e)


if __name__ == "__main__":
    main()
