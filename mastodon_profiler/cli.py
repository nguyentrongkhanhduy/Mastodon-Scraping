from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mastodon.errors import MastodonError

from .analyzer import analyze
from .client import build_profile
from .formatter import format_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_POSTS = 200
DEFAULT_POSTS = 20
DEFAULT_ANALYSIS_POSTS = 100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mastodon-profiler",
        description="Retrieve publicly available Mastodon user profile data and recent posts.",
    )
    parser.add_argument(
        "acct",
        help="Mastodon account in user@instance form (leading @ optional).",
    )
    parser.add_argument(
        "--instance",
        help="Instance URL or domain when acct is provided as username only.",
    )
    parser.add_argument(
        "--posts",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Number of recent public posts to retrieve "
            f"(1-{MAX_POSTS}, default: {DEFAULT_ANALYSIS_POSTS} with --analyze, "
            f"otherwise {DEFAULT_POSTS})."
        ),
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Compute and display behavioral analysis metrics.",
    )
    parser.add_argument(
        "--exclude-replies",
        action="store_true",
        help="Exclude reply posts from the recent post list.",
    )
    parser.add_argument(
        "--exclude-reblogs",
        action="store_true",
        help="Exclude reblogs/boosts from the recent post list.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("MASTODON_ACCESS_TOKEN"),
        help="Optional access token (or set MASTODON_ACCESS_TOKEN in .env).",
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    parser = build_parser()
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    post_limit = args.posts
    if post_limit is None:
        post_limit = DEFAULT_ANALYSIS_POSTS if args.analyze else DEFAULT_POSTS

    if post_limit < 1 or post_limit > MAX_POSTS:
        parser.error(f"--posts must be between 1 and {MAX_POSTS}.")

    try:
        profile = build_profile(
            acct=args.acct,
            instance=args.instance,
            post_limit=post_limit,
            exclude_replies=args.exclude_replies,
            exclude_reblogs=args.exclude_reblogs,
            access_token=args.token,
        )
        analysis = analyze(profile.posts) if args.analyze else None
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except MastodonError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 1

    print(format_profile(profile, args.output, analysis=analysis), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
