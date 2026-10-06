"""Command-line entrypoint for validation, projection, and site generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from principle_catalog.catalog import (
    load_catalog,
    load_public_progress,
    validate_coverage_tier_history,
    validate_identity_history,
    validate_print_registry_history,
    validate_public_progress,
    validate_question_edition_history,
)
from principle_catalog.progress import write_public_progress
from principle_catalog.research import load_research_queries
from principle_catalog.research_questions import (
    RESEARCH_COVERAGE_TIERS_PATH,
    RESEARCH_QUESTIONS_PATH,
    load_research_coverage,
    load_research_questions,
    validate_research_coverage_history,
    validate_research_question_history,
)
from principle_catalog.site import build_site
from principle_catalog.exam_coverage import load_exam_coverage
from principle_catalog.study import (
    new_study_candidates_from_path,
    study_brief,
    sync_study_items,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="principle-catalog")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate", help="validate canonical and public data")

    verify_print_registry = subcommands.add_parser(
        "verify-print-registry",
        help="verify that existing permanent print numbers were not changed",
    )
    verify_print_registry.add_argument("--previous", type=Path, required=True)

    verify_question_editions = subcommands.add_parser(
        "verify-question-editions",
        help="verify that previously issued question editions were not changed",
    )
    verify_question_editions.add_argument("--previous", type=Path, required=True)
    verify_question_editions.add_argument(
        "--current",
        type=Path,
        default=Path("data/principles/steel/question-editions.yaml"),
    )

    verify_identity_history = subcommands.add_parser(
        "verify-identity-history",
        help="verify that existing identity and migration routes were preserved",
    )
    verify_identity_history.add_argument(
        "--previous-identities", type=Path, required=True
    )
    verify_identity_history.add_argument(
        "--previous-migration", type=Path, required=True
    )
    verify_identity_history.add_argument(
        "--current-identities",
        type=Path,
        default=Path("data/principles/steel/identities.yaml"),
    )
    verify_identity_history.add_argument(
        "--current-migration",
        type=Path,
        default=Path("data/principles/steel/migration.yaml"),
    )

    verify_coverage_tiers = subcommands.add_parser(
        "verify-coverage-tiers",
        help="verify that previously issued coverage schemes were not changed",
    )
    verify_coverage_tiers.add_argument("--previous", type=Path, required=True)
    verify_coverage_tiers.add_argument(
        "--current",
        type=Path,
        default=Path("data/principles/steel/coverage-tiers.yaml"),
    )

    verify_research_questions = subcommands.add_parser(
        "verify-research-questions",
        help="verify that released provisional questions were preserved",
    )
    verify_research_questions.add_argument("--previous", type=Path, required=True)
    verify_research_questions.add_argument(
        "--current",
        type=Path,
        default=RESEARCH_QUESTIONS_PATH,
    )

    verify_research_coverage = subcommands.add_parser(
        "verify-research-coverage",
        help="verify that released candidate coverage and its questions were preserved",
    )
    verify_research_coverage.add_argument("--previous", type=Path, required=True)
    verify_research_coverage.add_argument(
        "--previous-questions",
        type=Path,
        required=True,
    )
    verify_research_coverage.add_argument(
        "--current",
        type=Path,
        default=RESEARCH_COVERAGE_TIERS_PATH,
    )

    sync = subcommands.add_parser("sync-progress", help="refresh the public progress projection")
    sync.add_argument("--output", type=Path, default=Path("data/public_progress.yaml"))

    sync_study = subcommands.add_parser(
        "sync-study-items",
        help="append source-checked catalog IDs to private local study state",
    )
    sync_study.add_argument("--state", type=Path, default=Path(".study/state.json"))

    new_candidates = subcommands.add_parser(
        "new-study-candidates",
        help=(
            "list eligible new items only; the existing urgent/review queue "
            "remains authoritative"
        ),
    )
    new_candidates.add_argument(
        "--state", type=Path, default=Path(".study/state.json")
    )
    new_candidates.add_argument("--ceiling", type=int, choices=(1, 2, 3))

    brief = subcommands.add_parser(
        "study-brief",
        help="show a source-checked binary question and its visible explanation",
    )
    brief.add_argument("item_id", help="immutable key, public code, or legacy alias")
    brief.add_argument(
        "--reveal",
        action="store_true",
        help="deprecated compatibility flag; full content is always visible",
    )

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
        exam_audit = load_exam_coverage(catalog)
        research_queries = load_research_queries(catalog)
        research_questions = load_research_questions(catalog)
        research_coverage = load_research_coverage(catalog, research_questions)
        progress = load_public_progress()
        validate_public_progress(catalog, progress)
        research_tier_counts = {
            tier: sum(
                research_coverage.items[key].current.tier == tier
                for key in research_coverage.active_keys
            )
            for tier in (1, 2, 3)
        }
        research_tier_summary = ",".join(
            f"{tier}:{research_tier_counts[tier]}" for tier in (1, 2, 3)
        )
        print(
            f"valid principles={len(catalog.principles)} "
            f"source_checked={sum(item.editorial_status == 'source_checked' for item in catalog.principles)} "
            f"research_queries={len(research_queries.items)} "
            f"research_questions={len(research_questions.active_keys)} "
            f"research_tiers={research_tier_summary} "
            f"projected_progress={len(progress.items)} "
            f"exam_objectives={exam_audit.verified}/{exam_audit.objectives}"
        )
        return 0
    if args.command == "sync-progress":
        count = write_public_progress(args.output)
        print(f"wrote {args.output} projected_progress={count}")
        return 0
    if args.command == "verify-print-registry":
        validate_print_registry_history(args.previous)
        print(f"valid permanent print registry previous={args.previous}")
        return 0
    if args.command == "verify-question-editions":
        validate_question_edition_history(args.previous, args.current)
        print(f"valid question editions previous={args.previous}")
        return 0
    if args.command == "verify-identity-history":
        validate_identity_history(
            args.previous_identities,
            args.previous_migration,
            args.current_identities,
            args.current_migration,
        )
        print(
            "valid identity history "
            f"previous_identities={args.previous_identities} "
            f"previous_migration={args.previous_migration}"
        )
        return 0
    if args.command == "verify-coverage-tiers":
        validate_coverage_tier_history(args.previous, args.current)
        print(f"valid coverage tiers previous={args.previous}")
        return 0
    if args.command == "verify-research-questions":
        catalog = load_catalog()
        validate_research_question_history(catalog, args.previous, args.current)
        print(f"valid research questions previous={args.previous}")
        return 0
    if args.command == "verify-research-coverage":
        catalog = load_catalog()
        validate_research_question_history(
            catalog,
            args.previous_questions,
            RESEARCH_QUESTIONS_PATH,
        )
        questions = load_research_questions(catalog)
        validate_research_coverage_history(
            catalog,
            questions,
            args.previous,
            args.current,
        )
        print(
            "valid research coverage "
            f"previous={args.previous} "
            f"previous_questions={args.previous_questions}"
        )
        return 0
    if args.command == "sync-study-items":
        added = sync_study_items(args.state)
        print(f"updated {args.state} added={len(added)}")
        return 0
    if args.command == "new-study-candidates":
        candidates = new_study_candidates_from_path(
            args.state,
            ceiling=args.ceiling,
        )
        print(
            "eligible new items only; urgent/review queue remains authoritative "
            f"count={len(candidates)}"
        )
        for item in candidates:
            print(item.id)
        return 0
    if args.command == "study-brief":
        print(study_brief(args.item_id, reveal=args.reveal), end="")
        return 0
    published, planned = build_site(args.output, args.base_url)
    print(f"built {args.output} published={published} planned={planned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
