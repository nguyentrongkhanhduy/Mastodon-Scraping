from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mastodon.errors import MastodonError

from .client import build_profile
from .formatter import format_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
        default=20,
        metavar="N",
        help="Number of recent public posts to retrieve (1-40, default: 20).",
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

    if args.posts < 1 or args.posts > 40:
        parser.error("--posts must be between 1 and 40.")

    try:
        profile = build_profile(
            acct=args.acct,
            instance=args.instance,
            post_limit=args.posts,
            exclude_replies=args.exclude_replies,
            exclude_reblogs=args.exclude_reblogs,
            access_token=args.token,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except MastodonError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        return 1

    print(format_profile(profile, args.output), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
