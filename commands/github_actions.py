import json
import os
import re
from typing import List, Dict, Any
from github import Github, Auth, Repository
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_bolt import App, Ack, Respond
from slack_sdk.models.views import View
from slack_sdk.models.blocks import SectionBlock, ButtonElement, MarkdownTextObject, Option, InputBlock, StaticSelectElement
from logging import Logger

load_dotenv()

auth = Auth.Token(os.environ.get("GITHUB_TOKEN"))

def list_repositories() -> List[str]:
    with Github(auth=auth) as g:
        return [repo for repo in g.get_user().get_repos()]

def search_repositories(query: str) -> List[str]:
    with Github(auth=auth) as g:
        return [repo for repo in g.get_user().get_repos() if re.search(query, repo.name, re.IGNORECASE)]

def format_repositories_for_slack(repos: List[Repository.Repository]) -> List[Dict[str, Any]]:
    blocks = []
    max_repos = 10
    for repo in repos[:max_repos]:
        blocks.append(SectionBlock(
            text=MarkdownTextObject(text=f"*{repo.name}*\n"
                         f":bust_in_silhouette: {repo.owner.name} | "
                         f":star: {repo.stargazers_count} | "
                         f":fork_and_knife: {repo.forks_count} | "
                         f":calendar: Last updated {repo.updated_at.strftime('%Y-%m-%d')} | "
                         f"<{repo.html_url}|View on GitHub>"),
            accessory=ButtonElement(
            text="Actions",
            action_id=f"open_actions_modal",
            value=json.dumps({"repository": repo.full_name})
            )
        ).to_dict())
    if len(repos) > max_repos:
        blocks.append(SectionBlock(
            text=MarkdownTextObject(text=f"Showing first {max_repos} repositories. There are more repositories not displayed. Use the `/slackops-github-actions search <term>` command to find more.")
        ).to_dict())
    return blocks

def fetch_github_actions(repository_full_name: str, logger:Logger) -> List[str]:
    with Github(auth=auth) as g:
        logger.info(f"Fetching GitHub actions for repository: {repository_full_name}")
        repo = g.get_repo(repository_full_name)
        workflows = repo.get_workflows()
        return [workflow.name for workflow in workflows]

### Register the command
def register_github_actions(app: App) -> None:
    @app.command("/slackops-github-actions")
    def github_actions(body: dict, ack: Ack, respond: Respond, client: WebClient, logger: Logger) -> None:
        logger.info("Received command: %s", body["text"])
        
        user_command = body["text"].strip().split()
        if not user_command:
            ack()
            respond(":no_entry_sign: No command provided. Use 'list' to list available repositories or 'search <query>' to search repositories.")
            return
        
        command = user_command[0]
        
        if command == "list":
            logger.info("Responding with repository list")
            ack(text=":hourglass_flowing_sand: Fetching repositories, please wait...")
            repos = list_repositories()
            blocks = format_repositories_for_slack(repos)
            respond(
                replace_original=True,
                text="Here are the repositories:",
                blocks=blocks
            )
        elif command == "search" and len(user_command) > 1:
            query = " ".join(user_command[1:])
            logger.info("Searching repositories with query: %s", query)
            ack(text=f":hourglass_flowing_sand: Searching repositories for '{query}', please wait...")
            repos = search_repositories(query)
            if repos:
                blocks = format_repositories_for_slack(repos)
                respond(
                    replace_original=True,
                    text=f"Repositories matching '{query}':",
                    blocks=blocks
                )
            else:
                respond(f"No repositories found matching '{query}'.")
        else:
            logger.info("Acknowledging unrecognized command")
            ack()
            respond(f"Command '{body['text']}' not recognized. Use 'list' to list available repositories or 'search <query>' to search repositories.")
            logger.info("Responded with unrecognized command message")

    @app.action("open_actions_modal")
    def handle_run_action(ack: Ack, body: dict, respond: Respond, client: WebClient, logger: Logger):
        logger.info("Received action to run GitHub action for repository")
        logger.info(f"Action body: {body}")
        ack()

        action_value = json.loads(body["actions"][0]["value"])
        repository_full_name = action_value["repository"]
        actions = fetch_github_actions(repository_full_name, logger)
        
        options = [Option(text=action, value=action) for action in actions]
        logger.info("Fetched %d actions for repository: %s", len(actions), repository_full_name)
        
        if not options:
            respond(f"No GitHub actions found for repository `{repository_full_name}`.")
            return

        modal_view = View(
            type="modal",
            callback_id="actions_modal",
            title={"type": "plain_text", "text": "GitHub Actions"},
            submit={"type": "plain_text", "text": "Run"},
            blocks=[
                InputBlock(
                    block_id="actions_select",
                    label={"type": "plain_text", "text": "Select an action to run"},
                    element=StaticSelectElement(
                        action_id="select_action",
                        placeholder={"type": "plain_text", "text": "Choose an action"},
                        options=options
                    )
                )
            ]
        )
        logger.info("Opening modal view for selecting GitHub action")
        client.views_open(
            trigger_id=body["trigger_id"],
            view=modal_view
        )
        logger.info("Modal view opened successfully")