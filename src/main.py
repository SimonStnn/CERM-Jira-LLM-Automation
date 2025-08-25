from __future__ import annotations

import os

from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from config import log, settings
from const import PROMPTS_DIR, __version__
from controller import Controller

assert __version__ is not None, "Version must be set"


def main():
    log.info("Application started")

    controller = Controller()

    system_prompt = controller.get_system_prompt()

    results = controller.find_online_help_issues(projects=["PLAYG", "CERM7", "LRN"])
    for issue, onlinehelp_comment in results:
        log.info("Processing issue %s comment %s", issue.key, onlinehelp_comment.id)
        matches = controller.query_pinecone(onlinehelp_comment.body)

        user_prompt = controller.build_user_prompt(
            references=matches, issue=issue, onlinehelp_comment=onlinehelp_comment
        )

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

        # * Generate AI output

        log.info("Generating the completion...")
        completion = controller.generate_completion(messages=messages)
        completion_content = completion

        out_path = os.path.join(issues_dir, "result.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(completion_content)
        log.info("Wrote completion output to %s", out_path)

        # * Build jira content
        _, adf = controller.build_jira_comment(
            completion_content=completion_content,
            references=matches,
            issues_dir=os.path.join(PROMPTS_DIR, "issues", issue.key),
        )

        controller.post_adf(issue, adf)


if __name__ == "__main__":
    main()
