import os
import logging
from dotenv import load_dotenv
from slack_bolt import App

load_dotenv()

logging.basicConfig(level=logging.INFO)

# Initialize your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

from commands.github_actions import register_github_actions
register_github_actions(app)

from events.app_home_opened import register_app_home_opened
register_app_home_opened(app)

from messages.basic_messages import register_basic_messages
register_basic_messages(app)


if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
