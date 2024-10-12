def register_app_home_opened(app):
    @app.event("app_home_opened")
    def update_home_tab(client, event, logger):
        try:
            client.views_publish(
            user_id=event["user"],
            view={
                "type": "home",
                "callback_id": "home_view",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                        "type": "mrkdwn",
                        "text": "*SlackOps* :robot_face:"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                        "type": "mrkdwn",
                        "text": "This bot can be used and extended to make your life easier."
                        }
                    }
                ]
            }
            )
        except Exception as e:
            logger.error(f"Error publishing home tab: {e}")
