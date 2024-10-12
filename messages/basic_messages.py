import re

def register_basic_messages(app):
    @app.message(re.compile("(hi|hello|hey|hoi|jo|yo|hallo)"))
    def greet(message, say):
        user = message["user"]
        response = (
            f"Hi <@{user}>! :wave:\n\n"
            "I'm the SlackOps bot! :robot_face:\n\n"
            "SlackOps can help you automate annoying tasks..\n\n"
            "If you have any questions, type \"help\" in the chat!"
        )
        say(response)

    @app.message(re.compile("(help|support)"))
    def help(message, say):
        user = message["user"]
        response = (
            f"Currently, SlackOps can do the following things:\n\n"
            "- Trigger GitHub Actions using */slackops-github-actions*\n"
        )
        say(response)