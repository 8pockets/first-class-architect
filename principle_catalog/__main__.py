"""Command-line entrypoint for validation, projection, and site generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from principle_catalog.catalog import (
    load_catalog,
    load_public_progress,
    validate_public_progress,
)
from principle_catalog.progress import write_public_progress
from principle_catalog.site import build_site
from principle_catalog.study import study_brief, sync_study_items


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="principle-catalog")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate", help="validate canonical and public data")

    sync = subcommands.add_parser("sync-progress", help="refresh the public progress projection")
    sync.add_argument("--output", type=Path, default=Path("data/public_progress.yaml"))

    sync_study = subcommands.add_parser(
        "sync-study-items",
        help="append source-checked catalog IDs to private local study state",
    )
    sync_study.add_argument("--state", type=Path, default=Path(".study/state.json"))

    brief = subcommands.add_parser(
        "study-brief",
        help="show the always-visible four-field learning brief for one item",
    )
    brief.add_argument("item_id")

    build = subcommands.add_parser("build", help="build the static GitHub Pages site")
    build.add_argument("--output", type=Path, default=Path("_site"))
    build.add_argument(
        "--base-url",
        default="https://8pockets.github.io/first-class-architect/",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "validate":
        catalog = load_catalog()
        progress = load_public_progress()
        validate_public_progress(catalog, progress)
        print(
            f"valid principles={len(catalog.principles)} "
            f"source_checked={sum(item.editorial_status == 'source_checked' for item in catalog.principles)} "
            f"projected_progress={len(progress.items)}"
        )
        return 0
    if args.command == "sync-progress":
        count = write_public_progress(args.output)
        print(f"wrote {args.output} projected_progress={count}")
        return 0
    if args.command == "sync-study-items":
        added = sync_study_items(args.state)
        print(f"updated {args.state} added={len(added)}")
        return 0
    if args.command == "study-brief":
        print(study_brief(args.item_id), end="")
        return 0
    published, planned = build_site(args.output, args.base_url)
    print(f"built {args.output} published={published} planned={planned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
