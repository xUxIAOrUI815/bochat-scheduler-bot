from __future__ import annotations

from dataclasses import dataclass
import hashlib

import httpx
from bs4 import BeautifulSoup


class WebsiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebsiteSnapshot:
    url: str
    title: str
    summary: str
    content_hash: str


async def fetch_website_snapshot(url: str, timeout_secs: float = 20.0) -> WebsiteSnapshot:
    try:
        async with httpx.AsyncClient(timeout=timeout_secs) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "bochat-scheduler-bot/0.1.0"},
                follow_redirects=True,
            )
            response.raise_for_status()
    except Exception as exc:
        raise WebsiteError(f"网站检查失败: {url}: {exc}") from exc

    return parse_website_content(url, response.text)


def parse_website_content(url: str, html: str) -> WebsiteSnapshot:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else url
    text = " ".join(soup.get_text(" ", strip=True).split())
    summary = text[:300]
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return WebsiteSnapshot(
        url=url,
        title=title or url,
        summary=summary,
        content_hash=content_hash,
    )
