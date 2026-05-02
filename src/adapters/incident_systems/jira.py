import hashlib
import hmac
import uuid
from datetime import datetime

import httpx

from src.adapters.base import Analysis, IncidentSystemAdapter
from src.core.config import get_settings
from src.models.incident import Incident

_PRIORITY_MAP = {"Highest": "P0", "High": "P1", "Medium": "P2", "Low": "P3"}


class JiraAdapter(IncidentSystemAdapter):
    name = "jira"

    def validate_signature(self, payload: bytes, headers: dict) -> bool:
        secret = get_settings().jira_webhook_secret
        if not secret:
            return True  # signature check disabled if secret not configured
        sig = headers.get("x-hub-signature", "")
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)

    async def parse_webhook(self, payload: dict, headers: dict) -> Incident:
        issue = payload.get("issue", {})
        fields = issue.get("fields", {})
        priority_name = (fields.get("priority") or {}).get("name", "Medium")
        return Incident(
            id=str(uuid.uuid4()),
            source="jira",
            title=fields.get("summary", "Untitled"),
            description=fields.get("description") or "",
            severity=_PRIORITY_MAP.get(priority_name, "P2"),
            metadata={
                "jira_key": issue.get("key"),
                "jira_id": issue.get("id"),
                "issue_type": (fields.get("issuetype") or {}).get("name"),
                "project": (fields.get("project") or {}).get("key"),
                "reporter": (fields.get("reporter") or {}).get("emailAddress"),
                "labels": fields.get("labels", []),
                "components": [c["name"] for c in fields.get("components", [])],
                "custom_fields": {
                    k: v for k, v in fields.items() if k.startswith("customfield_")
                },
            },
            created_at=datetime.utcnow(),
        )

    async def get_incident(self, id: str) -> Incident:
        settings = get_settings()
        async with httpx.AsyncClient(
            base_url=settings.jira_base_url,
            auth=(settings.jira_email, settings.jira_api_token),
        ) as client:
            resp = await client.get(f"/rest/api/3/issue/{id}")
            resp.raise_for_status()
            payload = {"issue": resp.json()}
            return await self.parse_webhook(payload, {})

    async def update_incident(self, id: str, analysis: Analysis) -> None:
        settings = get_settings()
        comment = (
            f"*AI Analysis Complete*\n\n"
            f"*Root Cause:* {analysis.root_cause}\n\n"
            f"*Workaround:* {analysis.workaround}\n\n"
            f"*Confidence:* {analysis.confidence_score:.0%}"
        )
        async with httpx.AsyncClient(
            base_url=settings.jira_base_url,
            auth=(settings.jira_email, settings.jira_api_token),
        ) as client:
            await client.post(
                f"/rest/api/3/issue/{id}/comment",
                json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}},
            )
