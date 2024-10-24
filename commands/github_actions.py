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
import time

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
            text=MarkdownTextObject(text=f"*{repo.full_name}*\n"
                         f":bust_in_silhouette: {repo.owner.name}  |  "
                         f":star: {repo.stargazers_count}  |  "
                         f":fork_and_knife: {repo.forks_count}  |  "
                         f":calendar: Last updated {repo.updated_at.strftime('%Y-%m-%d')}  |  "
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

        title_text = f"{repository_full_name} actions" if len(repository_full_name) < 16 else repository_full_name[:24]
        modal_view = View(
            type="modal",
            callback_id="submit_actions_modal",
            title={"type": "plain_text", "text": title_text},
            submit={"type": "plain_text", "text": "Run"},
            private_metadata=json.dumps({"repository_full_name": repository_full_name}),
            blocks=[
                InputBlock(
                    block_id="actions_select",
                    label={"type": "plain_text", "text": "Select an action to run"},
                    element=StaticSelectElement(
                    action_id="run_action",
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
    
    @app.view("submit_actions_modal")
    def handle_run_action(ack: Ack, body: dict, client: WebClient, logger: Logger):        
        logger.info("Received action to run GitHub action")
        logger.info(f"Action body: {body}")
        user = body['user']['username']
        selected_action = body['view']['state']['values']['actions_select']['run_action']['selected_option']['value']

        private_metadata = json.loads(body['view']['private_metadata'])
        repository_full_name = private_metadata['repository_full_name']
        logger.info(f"User {user} selected action: {selected_action} for repo: {repository_full_name}")

        ack()

        client.chat_postMessage(
            channel=body['user']['id'],
            text=f"Starting action `{selected_action}` for repository `{repository_full_name}`..."
        )

        ui_url = trigger_github_action(repository_full_name, selected_action, logger)

        if ui_url:
            client.chat_postMessage(
            channel=body['user']['id'],
            text=f"Running action `{selected_action}` for repository `{repository_full_name}`... View progress here: {ui_url}."
            )
        else:
            client.chat_postMessage(
                channel=body['user']['id'],
                text=f"Action triggering failed for `{selected_action}` in repository `{repository_full_name}`. Make sure `workflow_dispatch` is in the workflow triggers. See more details here: <https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_dispatch>"
            )
        
def trigger_github_action(repository_full_name: str, workflow_name: str, logger: Logger) -> str:
    with Github(auth=auth) as g:
        logger.info(f"Triggering GitHub action '{workflow_name}' for repository: {repository_full_name}")
        repo = g.get_repo(repository_full_name)
        workflow = next((wf for wf in repo.get_workflows() if wf.name == workflow_name), None)

        if workflow:
            workflow.create_dispatch(ref=repo.default_branch)
            logger.info(f"Triggered workflow '{workflow_name}' on branch '{repo.default_branch}'")
            time.sleep(3)  # wait to allow GitHub to create the dispatch
            run = next((run for run in workflow.get_runs() if run.status != "completed"), None)
            if run:
                logger.info(f"Active workflow run url: {run.html_url} with status {run.status}")
                return run.html_url
        else:
            logger.warning(f"Workflow '{workflow_name}' not found in repository '{repository_full_name}'")
        return ""
