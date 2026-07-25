import json
import requests
from django.conf import settings


class LarkService:

    @staticmethod
    def send_message(webhook: str, title: str, lines: list) -> bool:

        if not webhook:
            return False

        content_md = "\n".join([f"- {line}" for line in lines if line])

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content_md
                        }
                    }
                ]
            }
        }

        try:
            response = requests.post(
                webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False