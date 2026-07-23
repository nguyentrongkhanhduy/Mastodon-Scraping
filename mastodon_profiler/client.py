from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from mastodon import Mastodon


@dataclass
class PostMetadata:
    id: str
    url: str
    created_at: str
    content: str
    visibility: str
    language: str | None
    sensitive: bool
    spoiler_text: str
    replies_count: int
    reblogs_count: int
    favourites_count: int
    media_count: int
    tags: list[str]
    is_reply: bool
    is_reblog: bool

    @classmethod
    def from_status(cls, status: dict[str, Any]) -> PostMetadata:
        reblog = status.get("reblog")
        if reblog:
            return cls.from_status(reblog)._as_reblog()

        content = _strip_html(status.get("content", ""))
        tags = [tag.get("name", "") for tag in status.get("tags", []) if tag.get("name")]

        return cls(
            id=str(status.get("id", "")),
            url=status.get("url") or status.get("uri", ""),
            created_at=_stringify(status.get("created_at", "")),
            content=content,
            visibility=status.get("visibility", "unknown"),
            language=status.get("language"),
            sensitive=bool(status.get("sensitive")),
            spoiler_text=status.get("spoiler_text", ""),
            replies_count=int(status.get("replies_count", 0)),
            reblogs_count=int(status.get("reblogs_count", 0)),
            favourites_count=int(status.get("favourites_count", 0)),
            media_count=len(status.get("media_attachments") or []),
            tags=tags,
            is_reply=status.get("in_reply_to_id") is not None,
            is_reblog=False,
        )

    def _as_reblog(self) -> PostMetadata:
        return PostMetadata(
            id=self.id,
            url=self.url,
            created_at=self.created_at,
            content=self.content,
            visibility=self.visibility,
            language=self.language,
            sensitive=self.sensitive,
            spoiler_text=self.spoiler_text,
            replies_count=self.replies_count,
            reblogs_count=self.reblogs_count,
            favourites_count=self.favourites_count,
            media_count=self.media_count,
            tags=self.tags,
            is_reply=self.is_reply,
            is_reblog=True,
        )


@dataclass
class UserProfile:
    username: str
    display_name: str
    acct: str
    instance: str
    profile_url: str
    created_at: str
    biography: str
    followers_count: int
    following_count: int
    statuses_count: int
    posts: list[PostMetadata] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "acct": self.acct,
            "instance": self.instance,
            "profile_url": self.profile_url,
            "created_at": self.created_at,
            "biography": self.biography,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "statuses_count": self.statuses_count,
            "posts": [
                {
                    "id": post.id,
                    "url": post.url,
                    "created_at": post.created_at,
                    "content": post.content,
                    "visibility": post.visibility,
                    "language": post.language,
                    "sensitive": post.sensitive,
                    "spoiler_text": post.spoiler_text,
                    "replies_count": post.replies_count,
                    "reblogs_count": post.reblogs_count,
                    "favourites_count": post.favourites_count,
                    "media_count": post.media_count,
                    "tags": post.tags,
                    "is_reply": post.is_reply,
                    "is_reblog": post.is_reblog,
                }
                for post in self.posts
            ],
        }


def parse_acct(acct: str, instance: str | None = None) -> tuple[str, str]:
    """Return (acct, base_url) from user input."""
    acct = acct.strip().lstrip("@")
    if "@" in acct:
        username, domain = acct.rsplit("@", 1)
        acct = f"{username}@{domain}"
        base_url = _normalize_instance_url(domain)
        return acct, base_url

    if not instance:
        raise ValueError(
            "Provide a full acct (user@instance) or pass --instance with the username."
        )

    username = acct
    acct = f"{username}@{_hostname_from_instance(instance)}"
    base_url = _normalize_instance_url(instance)
    return acct, base_url


def _hostname_from_instance(instance: str) -> str:
    parsed = urlparse(_normalize_instance_url(instance))
    return parsed.netloc


def _normalize_instance_url(instance: str) -> str:
    instance = instance.strip().rstrip("/")
    if not instance.startswith(("http://", "https://")):
        instance = f"https://{instance}"
    return instance


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _stringify(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def create_mastodon_client(base_url: str, access_token: str | None = None) -> Mastodon:
    """Create a Mastodon.py client for public or authenticated API access."""
    kwargs: dict[str, Any] = {
        "api_base_url": base_url,
        "user_agent": "mastodon-profiler/1.0",
    }
    if access_token:
        kwargs["access_token"] = access_token
    return Mastodon(**kwargs)


def build_profile(
    acct: str,
    instance: str | None = None,
    post_limit: int = 20,
    exclude_replies: bool = False,
    exclude_reblogs: bool = False,
    access_token: str | None = None,
) -> UserProfile:
    acct, base_url = parse_acct(acct, instance)
    client = create_mastodon_client(base_url, access_token=access_token)

    account = client.account_lookup(acct)
    statuses = client.account_statuses(
        account["id"],
        limit=min(max(post_limit, 1), 40),
        exclude_replies=exclude_replies,
        exclude_reblogs=exclude_reblogs,
    )

    biography = _strip_html(account.get("note", ""))
    posts = [PostMetadata.from_status(status) for status in statuses]

    return UserProfile(
        username=account.get("username", ""),
        display_name=account.get("display_name", ""),
        acct=account.get("acct", acct),
        instance=_hostname_from_instance(base_url),
        profile_url=account.get("url", ""),
        created_at=_stringify(account.get("created_at", "")),
        biography=biography,
        followers_count=int(account.get("followers_count", 0)),
        following_count=int(account.get("following_count", 0)),
        statuses_count=int(account.get("statuses_count", 0)),
        posts=posts,
    )
