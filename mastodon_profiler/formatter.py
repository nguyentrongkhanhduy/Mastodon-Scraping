from __future__ import annotations

import json
from typing import Any

from .client import UserProfile


def format_profile(profile: UserProfile, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
    return _format_text(profile)


def _format_text(profile: UserProfile) -> str:
    lines: list[str] = [
        "Mastodon User Profile",
        "=" * 40,
        f"Username:      @{profile.username}",
        f"Display name:  {profile.display_name or '(none)'}",
        f"Acct:          @{profile.acct}",
        f"Instance:      {profile.instance}",
        f"Profile URL:   {profile.profile_url}",
        f"Created:       {profile.created_at}",
        f"Followers:     {profile.followers_count:,}",
        f"Following:     {profile.following_count:,}",
        f"Total posts:   {profile.statuses_count:,}",
        "",
        "Biography:",
        profile.biography or "(empty)",
        "",
        f"Recent public posts ({len(profile.posts)}):",
        "-" * 40,
    ]

    if not profile.posts:
        lines.append("(no posts retrieved)")
        return "\n".join(lines)

    for index, post in enumerate(profile.posts, start=1):
        lines.extend(_format_post(index, post))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_post(index: int, post: Any) -> list[str]:
    flags = []
    if post.is_reblog:
        flags.append("reblog")
    if post.is_reply:
        flags.append("reply")
    if post.sensitive:
        flags.append("sensitive")

    flag_text = f" [{', '.join(flags)}]" if flags else ""
    lines = [
        f"{index}. {post.created_at}{flag_text}",
        f"   URL: {post.url}",
        f"   Visibility: {post.visibility} | Language: {post.language or 'unknown'}",
        (
            "   Engagement: "
            f"{post.replies_count} replies, "
            f"{post.reblogs_count} reblogs, "
            f"{post.favourites_count} favourites"
        ),
    ]

    if post.media_count:
        lines.append(f"   Media attachments: {post.media_count}")
    if post.tags:
        lines.append(f"   Tags: {', '.join(f'#{tag}' for tag in post.tags)}")
    if post.spoiler_text:
        lines.append(f"   Content warning: {post.spoiler_text}")

    content = post.content.replace("\n", "\n   ")
    lines.append(f"   Content: {content or '(empty)'}")

    return lines
