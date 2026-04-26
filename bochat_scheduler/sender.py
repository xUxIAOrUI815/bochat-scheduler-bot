from __future__ import annotations

from dataclasses import dataclass

from bochat_sdk import BochatClient

from .config import AppConfig


@dataclass(frozen=True)
class SendResult:
    msg_id: int | None = None
    dry_run: bool = False


class BoChatSender:
    def __init__(self, config: AppConfig):
        self._client = BochatClient.builder(config.base_url).bot_token(config.bot_token).build()

    async def close(self) -> None:
        await self._client.close()

    async def send_text(self, group_id: str, text: str) -> SendResult:
        response = await self._client.messages().send_text(group_id, text)
        return SendResult(msg_id=response.msg_id)


class DryRunSender:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    async def close(self) -> None:
        return None

    async def send_text(self, group_id: str, text: str) -> SendResult:
        self.messages.append((group_id, text))
        print(f"[dry-run] group={group_id}\n{text}\n")
        return SendResult(dry_run=True)
