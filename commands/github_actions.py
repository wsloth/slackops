def register_github_actions(app):
    @app.command("/slackops-github-actions")
    def github_actions(ack, respond, command):
        ack()
        respond(f"Running GitHub Actions for {command['text']}")