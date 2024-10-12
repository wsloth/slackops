import os
from typing import List, Dict, Any
from github import Github
from github import Auth
from dotenv import load_dotenv
from slack_sdk import WebClient
from logging import Logger
from slack_bolt import App, Ack, Respond
from slack_sdk.models.blocks import SectionBlock, ButtonElement, MarkdownTextObject
import re

load_dotenv()

auth = Auth.Token(os.environ.get("GITHUB_TOKEN"))

def list_repositories() -> List[str]:
    g = Github(auth=auth)
    repos = [repo.name for repo in g.get_user().get_repos()]
    g.close()
    return repos

def search_repositories(query: str) -> List[str]:
    g = Github(auth=auth)
    repos = [repo.name for repo in g.get_user().get_repos() if re.search(query, repo.name, re.IGNORECASE)]
    g.close()
    return repos

def format_repositories_for_slack(repos: List[str]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    max_repos = 10
    for repo in repos[:max_repos]:
        blocks.append(SectionBlock(
            text=MarkdownTextObject(text=f"- {repo}"),
            accessory=ButtonElement(
                text="Run",
                action_id=f"run_{repo}"
            )
        ).to_dict())
    if len(repos) > max_repos:
        blocks.append(SectionBlock(
            text=MarkdownTextObject(text=f"Showing first {max_repos} repositories. There are more repositories not displayed. Use the 'search <term' command to find more.")
        ).to_dict())
    return blocks

def register_github_actions(app: App) -> None:
    @app.command("/slackops-github-actions")
    def github_actions(body: dict, ack: Ack, respond: Respond, client: WebClient, logger: Logger) -> None:
        logger.info("Received command: %s", body["text"])
        
        user_command = body["text"].strip().split()
        if not user_command:
            ack()
            respond("No command provided. Use 'list' to list available repositories or 'search <query>' to search repositories.")
            return
        
        command = user_command[0]
        
        if command == "list":
            logger.info("Responding with repository list")
            ack(text="Fetching repositories, please wait...")
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
            ack(text=f"Searching repositories for '{query}', please wait...")
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
