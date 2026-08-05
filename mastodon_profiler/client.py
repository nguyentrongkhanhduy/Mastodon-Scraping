from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from mastodon import Mastodon
from mastodon.errors import MastodonNotFoundError

API_PAGE_SIZE = 40
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_SEARCH_INSTANCE = "mastodon.social"


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
    mentions: list[str]
    is_reply: bool
    is_reblog: bool

    @property
    def engagement_score(self) -> int:
        return self.replies_count + self.reblogs_count + self.favourites_count

    @classmethod
    def from_status(cls, status: dict[str, Any]) -> PostMetadata:
        reblog = status.get("reblog")
        if reblog:
            inner = cls._from_status_content(reblog)
            return cls(
                id=inner.id,
                url=inner.url,
                created_at=_stringify(status.get("created_at", "")),
                content=inner.content,
                visibility=inner.visibility,
                language=inner.language,
                sensitive=inner.sensitive,
                spoiler_text=inner.spoiler_text,
                replies_count=inner.replies_count,
                reblogs_count=inner.reblogs_count,
                favourites_count=inner.favourites_count,
                media_count=inner.media_count,
                tags=inner.tags,
                mentions=inner.mentions,
                is_reply=False,
                is_reblog=True,
            )
        return cls._from_status_content(status)

    @classmethod
    def _from_status_content(cls, status: dict[str, Any]) -> PostMetadata:
        content = _strip_html(status.get("content", ""))
        tags = [tag.get("name", "") for tag in status.get("tags", []) if tag.get("name")]
        mentions = [
            mention.get("acct") or mention.get("username", "")
            for mention in status.get("mentions", [])
            if mention.get("acct") or mention.get("username")
        ]

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
            mentions=mentions,
            is_reply=status.get("in_reply_to_id") is not None,
            is_reblog=False,
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
            "posts": [_post_to_dict(post) for post in self.posts],
        }


def _post_to_dict(post: PostMetadata) -> dict[str, Any]:
    return {
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
        "mentions": post.mentions,
        "is_reply": post.is_reply,
        "is_reblog": post.is_reblog,
        "engagement_score": post.engagement_score,
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


def parse_search_input(
    query: str,
    instance: str | None = None,
    search_instance: str | None = None,
) -> tuple[str, str | None, str]:
    """Return (username query, optional instance domain filter, API base URL)."""
    query = query.strip().lstrip("@")
    if "@" in query:
        username, domain = query.rsplit("@", 1)
        return username, domain.lower(), _normalize_instance_url(domain)

    if instance:
        domain = _hostname_from_instance(instance).lower()
        return query, domain, _normalize_instance_url(instance)

    hub = search_instance or DEFAULT_SEARCH_INSTANCE
    return query, None, _normalize_instance_url(hub)


def _account_on_instance(account: dict[str, Any], instance_domain: str) -> bool:
    """Return True when an account belongs to the specified instance."""
    account_acct = account.get("acct", "")
    domain = instance_domain.lower().removeprefix("www.")
    if "@" not in account_acct:
        return True
    account_domain = account_acct.rsplit("@", 1)[1].lower().removeprefix("www.")
    return account_domain == domain


def format_account_handle(account: dict[str, Any], fallback_instance: str = "") -> str:
    """Return a full user@instance handle for display."""
    username, instance = split_account_handle(account, fallback_instance)
    if instance:
        return f"{username}@{instance}"
    return username


def split_account_handle(
    account: dict[str, Any],
    fallback_instance: str = "",
) -> tuple[str, str]:
    """Return (username, instance domain) for an account."""
    acct = account.get("acct", "") or account.get("username", "")
    if "@" in acct:
        username, instance = acct.rsplit("@", 1)
        return username, instance
    if fallback_instance:
        return acct, fallback_instance
    return acct, ""


def search_accounts(
    query: str,
    instance: str | None = None,
    access_token: str | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
    search_instance: str | None = None,
) -> tuple[str, str | None, str, list[dict[str, Any]]]:
    """Search for accounts. Returns (query, scoped instance, search hub, results)."""
    username, instance_domain, base_url = parse_search_input(
        query,
        instance=instance,
        search_instance=search_instance,
    )
    hub_instance = _hostname_from_instance(base_url)
    client = create_mastodon_client(base_url, access_token=access_token)

    if instance_domain:
        results = client.account_search(username, limit=limit, resolve=False)
        results = [account for account in results if _account_on_instance(account, instance_domain)]
    else:
        results = list(client.account_search(username, limit=limit, resolve=True))

    return username, instance_domain, hub_instance, results


def resolve_account(
    client: Mastodon,
    acct: str,
    hub_instance: str,
    search_limit: int = 5,
    search_fallback: bool = True,
) -> dict[str, Any]:
    """Look up an account by exact handle, optionally falling back to account_search."""
    try:
        return client.account_lookup(acct)
    except MastodonNotFoundError:
        if not search_fallback:
            raise ValueError(f"No account found for '{acct}'.")

    query = acct.split("@", 1)[0]
    results = client.account_search(query, limit=search_limit, resolve=True)
    if not results:
        raise ValueError(f"No account found matching '{acct}'.")

    exact_matches = [
        account
        for account in results
        if format_account_handle(account, hub_instance).lower() == acct.lower()
        or account.get("username", "").lower() == query.lower()
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(results) == 1:
        return results[0]

    lines = [f"Multiple matches for '{query}':"]
    for index, account in enumerate(results, start=1):
        handle = format_account_handle(account, hub_instance)
        display_name = account.get("display_name", "") or "(no display name)"
        lines.append(f"  {index}. {handle} — {display_name}")
    lines.append("Pass the full handle, e.g. user@instance.social")
    raise ValueError("\n".join(lines))


def fetch_account_statuses(
    client: Mastodon,
    account_id: str,
    limit: int,
    exclude_replies: bool = False,
    exclude_reblogs: bool = False,
) -> list[PostMetadata]:
    """Fetch recent statuses, paginating when limit exceeds the API page size."""
    limit = max(limit, 1)
    posts: list[PostMetadata] = []
    max_id: str | None = None

    while len(posts) < limit:
        batch_limit = min(API_PAGE_SIZE, limit - len(posts))
        kwargs: dict[str, Any] = {
            "limit": batch_limit,
            "exclude_replies": exclude_replies,
            "exclude_reblogs": exclude_reblogs,
        }
        if max_id is not None:
            kwargs["max_id"] = max_id

        statuses = client.account_statuses(account_id, **kwargs)
        if not statuses:
            break

        posts.extend(PostMetadata.from_status(status) for status in statuses)
        max_id = str(statuses[-1]["id"])

        if len(statuses) < batch_limit:
            break

    return posts[:limit]


def build_profile(
    acct: str,
    instance: str | None = None,
    post_limit: int = 20,
    exclude_replies: bool = False,
    exclude_reblogs: bool = False,
    access_token: str | None = None,
    search_fallback: bool = True,
) -> UserProfile:
    acct, base_url = parse_acct(acct, instance)
    hub_instance = _hostname_from_instance(base_url)
    client = create_mastodon_client(base_url, access_token=access_token)

    account = resolve_account(
        client,
        acct,
        hub_instance=hub_instance,
        search_fallback=search_fallback,
    )
    posts = fetch_account_statuses(
        client,
        account["id"],
        limit=post_limit,
        exclude_replies=exclude_replies,
        exclude_reblogs=exclude_reblogs,
    )

    biography = _strip_html(account.get("note", ""))

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
