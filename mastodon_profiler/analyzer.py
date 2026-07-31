from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .client import PostMetadata

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_account_age(created_at: str) -> str:
    created = parse_datetime(created_at)
    now = datetime.now(timezone.utc)
    total_days = max((now - created).days, 0)
    years, remaining_days = divmod(total_days, 365)
    months = remaining_days // 30

    parts: list[str] = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if not parts:
        parts.append(f"{total_days} day{'s' if total_days != 1 else ''}")
    return " ".join(parts)


def _post_category(post: PostMetadata) -> str:
    if post.is_reblog:
        return "reblog"
    if post.is_reply:
        return "reply"
    return "original"


def _preview(content: str, limit: int = 80) -> str:
    text = " ".join(content.split())
    if len(text) <= limit:
        return text or "(empty)"
    return text[: limit - 3] + "..."


@dataclass
class BehaviorAnalysis:
    sample_size: int
    sample_start: str
    sample_end: str
    sample_days: int
    posts_per_week: float
    originals_per_week: float
    replies_per_week: float
    reblogs_per_week: float
    content_mix: dict[str, int] = field(default_factory=dict)
    activity_by_day: list[tuple[str, int]] = field(default_factory=list)
    activity_by_hour: list[tuple[int, int]] = field(default_factory=list)
    peak_hours: str = ""
    avg_post_length: float = 0.0
    media_usage_rate: float = 0.0
    top_hashtags: list[tuple[str, int]] = field(default_factory=list)
    top_mentions: list[tuple[str, int]] = field(default_factory=list)
    language_distribution: dict[str, int] = field(default_factory=dict)
    top_posts: list[PostMetadata] = field(default_factory=list)
    top_replies: list[PostMetadata] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        total = self.sample_size or 1
        return {
            "sample_size": self.sample_size,
            "sample_start": self.sample_start,
            "sample_end": self.sample_end,
            "sample_days": self.sample_days,
            "posts_per_week": round(self.posts_per_week, 2),
            "originals_per_week": round(self.originals_per_week, 2),
            "replies_per_week": round(self.replies_per_week, 2),
            "reblogs_per_week": round(self.reblogs_per_week, 2),
            "content_mix": self.content_mix,
            "content_mix_percent": {
                key: round(value / total * 100, 1) for key, value in self.content_mix.items()
            },
            "activity_by_day": [
                {"day": day, "count": count} for day, count in self.activity_by_day
            ],
            "activity_by_hour": [
                {"hour": hour, "count": count} for hour, count in self.activity_by_hour
            ],
            "peak_hours": self.peak_hours,
            "avg_post_length": round(self.avg_post_length, 1),
            "media_usage_rate": round(self.media_usage_rate, 3),
            "top_hashtags": [{"tag": tag, "count": count} for tag, count in self.top_hashtags],
            "top_mentions": [{"acct": acct, "count": count} for acct, count in self.top_mentions],
            "language_distribution": self.language_distribution,
            "top_posts": [
                {
                    "url": post.url,
                    "engagement_score": post.engagement_score,
                    "replies_count": post.replies_count,
                    "reblogs_count": post.reblogs_count,
                    "favourites_count": post.favourites_count,
                    "preview": _preview(post.content),
                }
                for post in self.top_posts
            ],
            "top_replies": [
                {
                    "url": post.url,
                    "engagement_score": post.engagement_score,
                    "replies_count": post.replies_count,
                    "reblogs_count": post.reblogs_count,
                    "favourites_count": post.favourites_count,
                    "preview": _preview(post.content),
                }
                for post in self.top_replies
            ],
        }


def analyze(posts: list[PostMetadata]) -> BehaviorAnalysis:
    if not posts:
        return BehaviorAnalysis(
            sample_size=0,
            sample_start="",
            sample_end="",
            sample_days=0,
            posts_per_week=0.0,
            originals_per_week=0.0,
            replies_per_week=0.0,
            reblogs_per_week=0.0,
        )

    timestamps = [parse_datetime(post.created_at) for post in posts]
    sample_start_dt = min(timestamps)
    sample_end_dt = max(timestamps)
    sample_days = max((sample_end_dt - sample_start_dt).days, 1)
    weeks = sample_days / 7

    categories = Counter(_post_category(post) for post in posts)
    day_counts = Counter(timestamp.strftime("%A") for timestamp in timestamps)
    hour_counts = Counter(timestamp.hour for timestamp in timestamps)
    language_counts = Counter(post.language or "unknown" for post in posts)

    hashtag_counts: Counter[str] = Counter()
    mention_counts: Counter[str] = Counter()
    for post in posts:
        hashtag_counts.update(post.tags)
        mention_counts.update(post.mentions)

    lengths = [len(post.content) for post in posts if post.content]
    media_posts = sum(1 for post in posts if post.media_count > 0)

    originals = categories.get("original", 0)
    replies = categories.get("reply", 0)
    reblogs = categories.get("reblog", 0)

    top_hour_pairs = hour_counts.most_common(3)
    peak_hours = _format_peak_hours(top_hour_pairs)

    ranked_posts = sorted(posts, key=lambda post: post.engagement_score, reverse=True)
    ranked_replies = sorted(
        [post for post in posts if post.is_reply],
        key=lambda post: post.engagement_score,
        reverse=True,
    )

    return BehaviorAnalysis(
        sample_size=len(posts),
        sample_start=sample_start_dt.date().isoformat(),
        sample_end=sample_end_dt.date().isoformat(),
        sample_days=sample_days,
        posts_per_week=len(posts) / weeks,
        originals_per_week=originals / weeks,
        replies_per_week=replies / weeks,
        reblogs_per_week=reblogs / weeks,
        content_mix={
            "original": originals,
            "reply": replies,
            "reblog": reblogs,
        },
        activity_by_day=[(day, day_counts.get(day, 0)) for day in WEEKDAYS],
        activity_by_hour=sorted(hour_counts.items()),
        peak_hours=peak_hours,
        avg_post_length=sum(lengths) / len(lengths) if lengths else 0.0,
        media_usage_rate=media_posts / len(posts),
        top_hashtags=hashtag_counts.most_common(10),
        top_mentions=mention_counts.most_common(10),
        language_distribution=dict(language_counts),
        top_posts=ranked_posts[:5],
        top_replies=ranked_replies[:5],
    )


def _format_peak_hours(top_hours: list[tuple[int, int]]) -> str:
    if not top_hours:
        return "unknown"
    if len(top_hours) == 1:
        hour, _ = top_hours[0]
        return f"{hour:02d}:00 UTC"

    hours = sorted(hour for hour, _ in top_hours[:3])
    if len(hours) >= 2 and hours[-1] - hours[0] <= 2:
        return f"{hours[0]:02d}:00–{hours[-1]:02d}:00 UTC"

    return ", ".join(f"{hour:02d}:00 UTC" for hour in hours)
