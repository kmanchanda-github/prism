from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.models.incident import Incident


@dataclass
class DataChunk:
    source: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Analysis:
    root_cause: str
    workaround: str
    recommended_actions: list[dict]
    confidence_score: float
    sub_reports: list[dict]
    token_usage: dict


class DataSourceAdapter(ABC):
    """Fetches raw data for a given incident from one external source."""

    name: str = ""

    @abstractmethod
    async def fetch(self, incident: Incident, context: dict) -> list[DataChunk]:
        """Return chunks of relevant data for this incident."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the adapter is configured and reachable."""


class IncidentSystemAdapter(ABC):
    """Reads from and writes to an incident management system."""

    name: str = ""

    @abstractmethod
    async def get_incident(self, id: str) -> Incident: ...

    @abstractmethod
    async def parse_webhook(self, payload: dict, headers: dict) -> Incident:
        """Map a raw webhook payload to an Incident."""

    @abstractmethod
    def validate_signature(self, payload: bytes, headers: dict) -> bool:
        """Verify HMAC or other signature before processing webhook."""

    async def update_incident(self, id: str, analysis: Analysis) -> None:
        """Optionally write analysis back to the incident system."""

    async def create_incident(self, incident: Incident) -> str:
        """Optionally create a ticket and return its ID."""
        raise NotImplementedError


class NotificationAdapter(ABC):
    """Sends analysis-ready notifications with a link to the UI."""

    name: str = ""

    @abstractmethod
    async def send(
        self,
        message: str,
        link: str,
        summary: str,
        config: dict,
    ) -> None: ...

    @abstractmethod
    def is_available(self) -> bool: ...
