from __future__ import annotations

import json
from typing import Any

from .analyzer import BehaviorAnalysis, format_account_age
from .client import PostMetadata, UserProfile


def format_profile(
    profile: UserProfile,
    output_format: str,
    analysis: BehaviorAnalysis | None = None,
) -> str:
    if output_format == "json":
        payload = profile.to_dict()
        if analysis is not None:
            payload["analysis"] = analysis.to_dict()
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return _format_text(profile, analysis)


def _format_text(profile: UserProfile, analysis: BehaviorAnalysis | None) -> str:
    lines: list[str] = [
        f"Mastodon Behavioral Profile — @{profile.username}",
        "=" * 60,
        "",
        "ACCOUNT SUMMARY",
        "-" * 60,
        f"  Display name:  {profile.display_name or '(none)'}",
        f"  Acct:          @{profile.acct}",
        f"  Instance:      {profile.instance}",
        f"  Profile URL:   {profile.profile_url}",
        f"  Account age:   {format_account_age(profile.created_at)}",
        f"  Created:       {profile.created_at}",
        (
            "  Followers:     "
            f"{profile.followers_count:,} | Following: {profile.following_count:,} "
            f"| Total posts: {profile.statuses_count:,}"
        ),
        "",
        "  Biography:",
        f"  {profile.biography or '(empty)'}",
    ]

    if analysis is not None:
        lines.extend(_format_analysis(analysis))
    else:
        lines.extend(_format_recent_posts(profile.posts))

    return "\n".join(lines).rstrip() + "\n"


def _format_analysis(analysis: BehaviorAnalysis) -> list[str]:
    lines = [
        "",
        "ANALYSIS SAMPLE",
        "-" * 60,
        f"  Based on last {analysis.sample_size} public posts",
        f"  Date range: {analysis.sample_start} to {analysis.sample_end} ({analysis.sample_days} days)",
        "",
        "POSTING FREQUENCY",
        "-" * 60,
        f"  Overall:    {analysis.posts_per_week:.2f} posts/week",
        (
            "  Originals:  "
            f"{analysis.originals_per_week:.2f}/week | "
            f"Replies: {analysis.replies_per_week:.2f}/week | "
            f"Reblogs: {analysis.reblogs_per_week:.2f}/week"
        ),
        "",
        "CONTENT MIX",
        "-" * 60,
    ]
    lines.extend(_format_content_mix(analysis))
    lines.extend(
        [
            "",
            "ACTIVITY BY DAY (UTC)",
            "-" * 60,
        ]
    )
    lines.extend(_format_bar_chart(analysis.activity_by_day, label_width=9))
    lines.extend(
        [
            "",
            "ACTIVITY BY HOUR (UTC)",
            "-" * 60,
            f"  Peak hours: {analysis.peak_hours}",
        ]
    )
    lines.extend(_format_bar_chart([(f"{hour:02d}:00", count) for hour, count in analysis.activity_by_hour], label_width=5))
    lines.extend(
        [
            "",
            "CONTENT STATS",
            "-" * 60,
            f"  Average post length: {analysis.avg_post_length:.1f} characters",
            f"  Media usage rate:  {analysis.media_usage_rate * 100:.1f}%",
            "",
            "TOP HASHTAGS",
            "-" * 60,
        ]
    )
    lines.extend(_format_ranked_list(analysis.top_hashtags, prefix="#"))
    lines.extend(
        [
            "",
            "TOP MENTIONS",
            "-" * 60,
        ]
    )
    lines.extend(_format_ranked_list(analysis.top_mentions, prefix="@"))
    lines.extend(
        [
            "",
            "LANGUAGE DISTRIBUTION",
            "-" * 60,
        ]
    )
    lines.extend(_format_language_distribution(analysis))
    lines.extend(
        [
            "",
            "TOP POSTS BY ENGAGEMENT",
            "-" * 60,
        ]
    )
    lines.extend(_format_top_content(analysis.top_posts))
    lines.extend(
        [
            "",
            "TOP REPLIES BY ENGAGEMENT",
            "-" * 60,
        ]
    )
    lines.extend(_format_top_content(analysis.top_replies))
    return lines


def _format_content_mix(analysis: BehaviorAnalysis) -> list[str]:
    if analysis.sample_size == 0:
        return ["  (no posts analyzed)"]

    lines: list[str] = []
    labels = {
        "original": "Original",
        "reply": "Reply",
        "reblog": "Reblog",
    }
    for key in ("original", "reply", "reblog"):
        count = analysis.content_mix.get(key, 0)
        percent = count / analysis.sample_size * 100
        bar = _bar(count, analysis.sample_size, width=18)
        lines.append(f"  {labels[key]:<9} {percent:5.1f}% ({count:>3})  {bar}")
    return lines


def _format_bar_chart(items: list[tuple[Any, int]], label_width: int) -> list[str]:
    if not items:
        return ["  (no data)"]

    max_count = max(count for _, count in items) or 1
    lines: list[str] = []
    for label, count in items:
        if count == 0 and max_count > 0:
            continue
        bar = _bar(count, max_count, width=24)
        lines.append(f"  {str(label):<{label_width}} {count:>3}  {bar}")
    return lines or ["  (no activity recorded)"]


def _bar(value: int, maximum: int, width: int) -> str:
    if maximum <= 0:
        return ""
    filled = max(1, round(value / maximum * width)) if value > 0 else 0
    return "█" * filled


def _format_ranked_list(items: list[tuple[str, int]], prefix: str) -> list[str]:
    if not items:
        return ["  (none)"]
    return [f"  {prefix}{name:<24} {count}" for name, count in items]


def _format_language_distribution(analysis: BehaviorAnalysis) -> list[str]:
    if not analysis.language_distribution:
        return ["  (none)"]

    total = sum(analysis.language_distribution.values()) or 1
    lines: list[str] = []
    for language, count in sorted(
        analysis.language_distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        percent = count / total * 100
        lines.append(f"  {language:<10} {percent:5.1f}% ({count})")
    return lines


def _format_top_content(posts: list[PostMetadata]) -> list[str]:
    if not posts:
        return ["  (none)"]

    lines: list[str] = []
    for index, post in enumerate(posts, start=1):
        preview = " ".join(post.content.split())
        if len(preview) > 90:
            preview = preview[:87] + "..."
        lines.append(
            f"  {index}. [{post.engagement_score} pts] "
            f"{post.replies_count} replies, {post.reblogs_count} boosts, {post.favourites_count} favs"
        )
        lines.append(f"     {preview or '(empty)'}")
        lines.append(f"     {post.url}")
    return lines


def _format_recent_posts(posts: list[PostMetadata]) -> list[str]:
    lines = [
        "",
        f"RECENT PUBLIC POSTS ({len(posts)})",
        "-" * 60,
    ]
    if not posts:
        lines.append("(no posts retrieved)")
        return lines

    for index, post in enumerate(posts, start=1):
        lines.extend(_format_post(index, post))
        lines.append("")
    return lines


def _format_post(index: int, post: PostMetadata) -> list[str]:
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
    if post.mentions:
        lines.append(f"   Mentions: {', '.join(f'@{mention}' for mention in post.mentions)}")
    if post.spoiler_text:
        lines.append(f"   Content warning: {post.spoiler_text}")

    content = post.content.replace("\n", "\n   ")
    lines.append(f"   Content: {content or '(empty)'}")

    return lines
