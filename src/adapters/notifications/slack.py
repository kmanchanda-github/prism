from src.adapters.base import NotificationAdapter
from src.core.config import get_settings


class SlackAdapter(NotificationAdapter):
    name = "slack"

    def is_available(self) -> bool:
        return bool(get_settings().slack_bot_token)

    async def send(self, message: str, link: str, summary: str, config: dict) -> None:
        from slack_sdk.web.async_client import AsyncWebClient

        client = AsyncWebClient(token=get_settings().slack_bot_token)
        channel = config.get("channel", "#incidents")
        await client.chat_postMessage(
            channel=channel,
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{message}*\n>{summary}"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Analysis"},
                            "url": link,
                            "style": "primary",
                        }
                    ],
                },
            ],
        )
