from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import (
    AmbiguousPrincipleIdentifier,
    display_facets,
    load_catalog,
    resolve_principle,
    validate_identity_history,
)
from principle_catalog.progress import public_progress_from_local
from principle_catalog.study import study_brief, sync_study_items


IDENTITIES_PATH = Path("data/principles/steel/identities.yaml")
MIGRATION_PATH = Path("data/principles/steel/migration.yaml")


def _write_yaml(path: Path, data: object) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _identity_history_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    previous_identities = tmp_path / "previous-identities.yaml"
    previous_migration = tmp_path / "previous-migration.yaml"
    current_identities = tmp_path / "current-identities.yaml"
    current_migration = tmp_path / "current-migration.yaml"
    for source, previous, current in (
        (IDENTITIES_PATH, previous_identities, current_identities),
        (MIGRATION_PATH, previous_migration, current_migration),
    ):
        contents = source.read_text(encoding="utf-8")
        previous.write_text(contents, encoding="utf-8")
        current.write_text(contents, encoding="utf-8")
    return (
        previous_identities,
        previous_migration,
        current_identities,
        current_migration,
    )


def _copied_catalog_root(tmp_path: Path) -> Path:
    root = tmp_path / "steel"
    shutil.copytree(Path("data/principles/steel"), root)
    return root


def _retire_multigeneration_target(root: Path) -> tuple[str, str, str]:
    intermediate = "S-K6-BRACED-FRAME-COLUMN-BRACE-CAPACITY-SUM"
    leaf = "S-K6-X-BRACE-TENSION-COMPRESSION-CAPACITY"
    legacy_alias = "structure.steel.braced-frame-ultimate-capacity-components"

    section_path = root / "28-x-brace-capacity.yaml"
    section = yaml.safe_load(section_path.read_text(encoding="utf-8"))
    section["principles"] = [
        item for item in section["principles"] if item["id"] != intermediate
    ]
    _write_yaml(section_path, section)

    taxonomy_path = root / "taxonomy.yaml"
    taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    del taxonomy["assignments"][intermediate]
    _write_yaml(taxonomy_path, taxonomy)

    identities_path = root / "identities.yaml"
    identities = yaml.safe_load(identities_path.read_text(encoding="utf-8"))
    identities["retired"][intermediate] = identities["active"].pop(intermediate)
    _write_yaml(identities_path, identities)

    migration_path = root / "migration.yaml"
    migration = yaml.safe_load(migration_path.read_text(encoding="utf-8"))
    migration["retired"][intermediate] = {
        "operation": "rename",
        "legacy_section": "K6-28",
        "targets": [leaf],
        "progress_policy": "preserve_active_target_only",
    }
    _write_yaml(migration_path, migration)

    manifest_path = root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["inventory"]["total"] -= 1
    manifest["inventory"]["editorial_status"]["source_gap"] -= 1
    manifest["question_audit"].update(
        {
            "taxonomy_sha256": (
                "272b5ad2476858e1305fd4530c866cb889ce195af9c5fc249a95904a9bfca545"
            ),
            "prerequisites_sha256": (
                "167ab5f91b1cb887e6d4ef6d1450741f6ffc0d51cdbe69e81aff39dba0d5776e"
            ),
            "identities_sha256": (
                "5e093e49e8c86a40ead7694630491135037f17292449216c2d9993e74e82b55d"
            ),
            "migration_sha256": (
                "1c7409526fd227a3dec58ebcd6c9ced97f20db809c6167737263bb0b11e5d2fe"
            ),
        }
    )
    _write_yaml(manifest_path, manifest)
    return intermediate, leaf, legacy_alias


def test_identity_history_rejects_removing_an_existing_active_identity(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    removed_key = next(iter(current_data["active"]))
    del current_data["active"][removed_key]
    _write_yaml(paths[2], current_data)

    with pytest.raises(
        ValueError,
        match="existing identity keys must not be removed",
    ):
        validate_identity_history(*paths)


def test_identity_history_rejects_changing_an_existing_public_code(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    changed_key = next(iter(current_data["active"]))
    current_data["active"][changed_key]["code"] = (
        "structure.steel.changed-existing-code"
    )
    _write_yaml(paths[2], current_data)

    with pytest.raises(ValueError, match="existing identity codes must not change"):
        validate_identity_history(*paths)


def test_identity_history_rejects_removing_an_existing_identity_alias(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    previous_data = yaml.safe_load(paths[0].read_text(encoding="utf-8"))
    aliased_key = next(iter(previous_data["active"]))
    previous_data["active"][aliased_key]["aliases"] = ["legacy-card-anchor"]
    _write_yaml(paths[0], previous_data)

    with pytest.raises(ValueError, match="existing identity aliases must not be removed"):
        validate_identity_history(*paths)


def test_identity_history_rejects_reactivating_a_retired_identity(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    reactivated_key, identity = current_data["retired"].popitem()
    current_data["active"][reactivated_key] = identity
    _write_yaml(paths[2], current_data)

    with pytest.raises(ValueError, match="retired identities must remain retired"):
        validate_identity_history(*paths)


def test_identity_history_rejects_removing_an_existing_migration_alias(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    current_data["aliases"].popitem()
    _write_yaml(paths[3], current_data)

    with pytest.raises(
        ValueError,
        match="existing migration alias routes must not change or be removed",
    ):
        validate_identity_history(*paths)


def test_identity_history_rejects_retargeting_an_existing_migration_alias(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    alias = next(iter(current_data["aliases"]))
    identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    replacement = next(iter(identities["active"]))
    current_data["aliases"][alias] = [replacement]
    _write_yaml(paths[3], current_data)

    with pytest.raises(
        ValueError,
        match="existing migration alias routes must not change or be removed",
    ):
        validate_identity_history(*paths)


def test_identity_history_rejects_removing_an_existing_retirement_record(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    current_data["retired"].popitem()
    _write_yaml(paths[3], current_data)

    with pytest.raises(
        ValueError,
        match="existing retired migration records must not change or be removed",
    ):
        validate_identity_history(*paths)


def test_identity_history_rejects_changing_an_existing_retirement_record(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    split = next(
        record
        for record in current_data["retired"].values()
        if record["operation"] == "split"
    )
    split["targets"] = list(reversed(split["targets"]))
    _write_yaml(paths[3], current_data)

    with pytest.raises(
        ValueError,
        match="existing retired migration records must not change or be removed",
    ):
        validate_identity_history(*paths)


def test_identity_history_rejects_changing_a_legacy_section(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    record = next(iter(current_data["retired"].values()))
    record["legacy_section"] = "K6-99"
    _write_yaml(paths[3], current_data)

    with pytest.raises(
        ValueError,
        match="existing retired migration records must not change or be removed",
    ):
        validate_identity_history(*paths)


def test_migration_record_requires_a_legacy_section(tmp_path: Path) -> None:
    paths = _identity_history_files(tmp_path)
    current_data = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    record = next(iter(current_data["retired"].values()))
    del record["legacy_section"]
    _write_yaml(paths[3], current_data)

    with pytest.raises(ValueError, match="legacy_section"):
        validate_identity_history(*paths)


def test_identity_history_allows_additions_and_active_to_retired_transition(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    current_migration = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    active_keys = list(current_identities["active"])
    moved_key = active_keys[0]
    target_key = active_keys[1]
    current_identities["retired"][moved_key] = current_identities["active"].pop(
        moved_key
    )
    current_identities["active"]["S-K6-NEW-HISTORY-GUARD-TEST"] = {
        "code": "structure.steel.new-history-guard-test",
        "aliases": ["new-public-alias"],
    }
    current_migration["retired"][moved_key] = {
        "operation": "rename",
        "targets": [target_key],
        "progress_policy": "preserve_active_target_only",
        "legacy_section": "K6-99",
    }
    current_migration["aliases"]["new-migration-alias"] = [target_key]
    _write_yaml(paths[2], current_identities)
    _write_yaml(paths[3], current_migration)

    validate_identity_history(*paths)


def test_identity_history_allows_a_retired_target_to_gain_a_new_migration(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    current_migration = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    old_record = next(iter(current_migration["retired"].values()))
    intermediate = old_record["targets"][0]
    leaf = next(
        key for key in current_identities["active"] if key != intermediate
    )
    current_identities["retired"][intermediate] = current_identities["active"].pop(
        intermediate
    )
    current_migration["retired"][intermediate] = {
        "operation": "rename",
        "targets": [leaf],
        "progress_policy": "preserve_active_target_only",
        "legacy_section": "K6-99",
    }
    _write_yaml(paths[2], current_identities)
    _write_yaml(paths[3], current_migration)

    validate_identity_history(*paths)


def test_identity_history_rejects_an_unknown_multigeneration_target(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    current_migration = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    key = "S-K6-NEW-MISSING-TARGET"
    current_identities["retired"][key] = {
        "code": "structure.steel.new-missing-target",
        "aliases": [],
    }
    current_migration["retired"][key] = {
        "operation": "rename",
        "targets": ["S-K6-NOT-A-REAL-TARGET"],
        "progress_policy": "preserve_active_target_only",
        "legacy_section": "K6-99",
    }
    _write_yaml(paths[2], current_identities)
    _write_yaml(paths[3], current_migration)

    with pytest.raises(ValueError, match="unknown migration target"):
        validate_identity_history(*paths)


def test_identity_history_rejects_a_multigeneration_migration_cycle(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    current_migration = yaml.safe_load(paths[3].read_text(encoding="utf-8"))
    first = "S-K6-NEW-CYCLE-A"
    second = "S-K6-NEW-CYCLE-B"
    for key, suffix in ((first, "a"), (second, "b")):
        current_identities["retired"][key] = {
            "code": f"structure.steel.new-cycle-{suffix}",
            "aliases": [],
        }
    for key, target in ((first, second), (second, first)):
        current_migration["retired"][key] = {
            "operation": "rename",
            "targets": [target],
            "progress_policy": "preserve_active_target_only",
            "legacy_section": "K6-99",
        }
    _write_yaml(paths[2], current_identities)
    _write_yaml(paths[3], current_migration)

    with pytest.raises(ValueError, match="migration cycle includes"):
        validate_identity_history(*paths)


def test_catalog_and_history_resolve_multigeneration_migrations_to_active_leaves(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    previous_identities = tmp_path / "previous-identities.yaml"
    previous_migration = tmp_path / "previous-migration.yaml"
    shutil.copyfile(root / "identities.yaml", previous_identities)
    shutil.copyfile(root / "migration.yaml", previous_migration)
    intermediate, leaf, legacy_alias = _retire_multigeneration_target(root)

    validate_identity_history(
        previous_identities,
        previous_migration,
        root / "identities.yaml",
        root / "migration.yaml",
    )
    catalog = load_catalog(root / "manifest.yaml")

    assert resolve_principle(catalog, intermediate).keys == (leaf,)
    legacy_resolution = resolve_principle(catalog, legacy_alias)
    assert legacy_resolution.keys == (leaf,)
    assert legacy_resolution.is_split
    with pytest.raises(AmbiguousPrincipleIdentifier, match="split identifier"):
        legacy_resolution.require_one()


def test_catalog_rejects_an_unknown_multigeneration_target(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    migration_path = root / "migration.yaml"
    migration = yaml.safe_load(migration_path.read_text(encoding="utf-8"))
    record = next(
        record
        for record in migration["retired"].values()
        if record["operation"] == "merge"
    )
    record["targets"] = ["S-K6-NOT-A-REAL-TARGET"]
    _write_yaml(migration_path, migration)

    with pytest.raises(ValueError, match="unknown migration target"):
        load_catalog(root / "manifest.yaml")


def test_catalog_rejects_a_multigeneration_migration_cycle(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    migration_path = root / "migration.yaml"
    migration = yaml.safe_load(migration_path.read_text(encoding="utf-8"))
    merge_keys = [
        key
        for key, record in migration["retired"].items()
        if record["operation"] == "merge"
    ][:2]
    first, second = merge_keys
    migration["retired"][first]["targets"] = [second]
    migration["retired"][second]["targets"] = [first]
    _write_yaml(migration_path, migration)

    with pytest.raises(ValueError, match="migration cycle includes"):
        load_catalog(root / "manifest.yaml")


def test_identity_history_rejects_active_to_retired_without_migration_record(
    tmp_path: Path,
) -> None:
    paths = _identity_history_files(tmp_path)
    current_identities = yaml.safe_load(paths[2].read_text(encoding="utf-8"))
    moved_key, identity = current_identities["active"].popitem()
    current_identities["retired"][moved_key] = identity
    _write_yaml(paths[2], current_identities)

    with pytest.raises(
        ValueError,
        match="retired migration keys must match retired identity keys",
    ):
        validate_identity_history(*paths)


def test_verify_identity_history_cli_accepts_unchanged_registries() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "principle_catalog",
            "verify-identity-history",
            "--previous-identities",
            str(IDENTITIES_PATH),
            "--previous-migration",
            str(MIGRATION_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "valid identity history" in completed.stdout


def test_catalog_rejects_identity_registry_that_differs_from_audit_hash(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    path = root / "identities.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    key = next(iter(data["active"]))
    data["active"][key]["aliases"].append("previously-unaudited-alias")
    _write_yaml(path, data)

    with pytest.raises(
        ValueError,
        match="identities differ from the independently audited snapshot",
    ):
        load_catalog(root / "manifest.yaml")


def test_catalog_rejects_migration_registry_that_differs_from_audit_hash(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    path = root / "migration.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    identities = yaml.safe_load(
        (root / "identities.yaml").read_text(encoding="utf-8")
    )
    target = next(iter(identities["active"]))
    data["aliases"]["previously-unaudited-route"] = [target]
    _write_yaml(path, data)

    with pytest.raises(
        ValueError,
        match="migration differs from the independently audited snapshot",
    ):
        load_catalog(root / "manifest.yaml")


@pytest.mark.parametrize(
    ("projection", "filename"),
    (
        ("taxonomy", "taxonomy.yaml"),
        ("identities", "identities.yaml"),
        ("migration", "migration.yaml"),
        ("question_editions", "question-editions.yaml"),
    ),
)
def test_catalog_rejects_manifest_projection_path_substitution(
    tmp_path: Path,
    projection: str,
    filename: str,
) -> None:
    root = _copied_catalog_root(tmp_path)
    shadow = root / f"shadow-{filename}"
    shutil.copyfile(root / filename, shadow)
    manifest_path = root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["projections"][projection] = shadow.name
    _write_yaml(manifest_path, manifest)

    with pytest.raises(
        ValueError,
        match=rf"projections\.{projection} must be {filename}",
    ):
        load_catalog(manifest_path)


def test_catalog_accepts_a_new_highest_current_question_edition(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    editions_path = root / "question-editions.yaml"
    data = yaml.safe_load(editions_path.read_text(encoding="utf-8"))
    previous_current = data["editions"]["K6-R2"]
    previous_current["status"] = "archived"
    data["editions"]["K6-R3"] = {
        "status": "current",
        "content_sha256": previous_current["content_sha256"],
        "assignments": previous_current["assignments"],
    }
    data["current"] = "K6-R3"
    _write_yaml(editions_path, data)

    catalog = load_catalog(root / "manifest.yaml")

    assert catalog.question_editions.current == "K6-R3"
    assert catalog.question_editions.editions["K6-R2"].status == "archived"


def test_catalog_rejects_current_question_edition_below_highest_revision(
    tmp_path: Path,
) -> None:
    root = _copied_catalog_root(tmp_path)
    editions_path = root / "question-editions.yaml"
    data = yaml.safe_load(editions_path.read_text(encoding="utf-8"))
    current = data["editions"]["K6-R2"]
    data["editions"]["K6-R3"] = {
        "status": "archived",
        "content_sha256": current["content_sha256"],
        "assignments": current["assignments"],
    }
    _write_yaml(editions_path, data)

    with pytest.raises(
        ValueError,
        match="current question edition must have the highest revision number",
    ):
        load_catalog(root / "manifest.yaml")


def test_immutable_key_and_public_code_resolve_the_same_active_card() -> None:
    catalog = load_catalog()
    item = next(
        item
        for item in catalog.principles
        if item.editorial_status == "source_checked"
    )

    by_key = resolve_principle(catalog, item.id).require_one()
    by_code = resolve_principle(catalog, item.code).require_one()

    assert by_key is item
    assert by_code is item
    assert item.id.startswith("S-K6-")
    assert item.code.startswith("structure.steel.")


def test_every_active_card_has_one_unique_public_code() -> None:
    catalog = load_catalog()
    codes = [item.code for item in catalog.principles]

    assert len(codes) == len(set(codes)) == len(catalog.principles)
    assert set(catalog.identities.active) == {item.id for item in catalog.principles}


def test_retired_migrations_preserve_their_original_section() -> None:
    catalog = load_catalog()

    assert {
        key: record.legacy_section
        for key, record in catalog.migration.retired.items()
    } == {
        "S-K6-BOX-COLUMN-H-BEAM-RIGID-JOINT-WELD-TYPES": "K6-12",
        "S-K6-BRACE-FRAME-HYSTERESIS-BY-SLENDERNESS": "K6-38",
        "S-K6-BRACE-HORIZONTAL-LOAD-TO-AXIAL-FORCE": "K6-24",
        "S-K6-BRACED-FRAME-ULTIMATE-CAPACITY-COMPONENTS": "K6-28",
        "S-K6-COMPRESSION-ALLOWABLE-WITHOUT-BUCKLING": "K6-00",
        "S-K6-COMPRESSION-BRACE-BUCKLING-CAPACITY": "K6-00",
        "S-K6-SHOP-JOINT-FIELD-SPLICE-IDENTIFICATION": "K6-31",
        "S-K6-STEEL-HIGH-STRENGTH-SMALLER-SECTION": "K6-06",
        "S-K6-STEEL-SMALL-SECTION-DEFLECTION": "K6-06",
        "S-K6-WRAPPED-BASE-MOMENT-AND-SHEAR-DISTRIBUTION": "K6-00",
    }


def test_split_legacy_identifier_returns_all_targets_and_never_picks_one() -> None:
    catalog = load_catalog()
    retired_key, migration = next(
        (key, record)
        for key, record in catalog.migration.retired.items()
        if record.operation == "split"
    )

    resolution = resolve_principle(catalog, retired_key)

    assert resolution.keys == migration.targets
    assert tuple(item.id for item in resolution.principles) == migration.targets
    with pytest.raises(AmbiguousPrincipleIdentifier, match="split identifier"):
        resolution.require_one()
    with pytest.raises(AmbiguousPrincipleIdentifier, match="split identifier"):
        study_brief(retired_key)


def test_study_brief_accepts_key_code_and_alias_with_the_same_visible_content() -> None:
    catalog = load_catalog()
    alias, targets = next(
        (alias, targets)
        for alias, targets in catalog.migration.aliases.items()
        if len(targets) == 1
        and resolve_principle(catalog, alias).require_one().editorial_status
        == "source_checked"
    )
    item = resolve_principle(catalog, targets[0]).require_one()
    facets = display_facets(catalog, item)

    by_key = study_brief(item.id)
    by_code = study_brief(item.code)
    by_alias = study_brief(alias)

    assert by_key == by_code == by_alias
    assert f"内部キー: `{item.id}`" in by_key
    assert f"公開コード: `{item.code}`" in by_key
    assert "正解:" in by_key
    assert f"## {facets.primary.label}" in by_key
    assert f"## {facets.secondary.label}" in by_key
    if facets.tertiary.values:
        assert f"## {facets.tertiary.label}" in by_key
    assert study_brief(item.code, reveal=True) == by_key


def test_study_brief_cli_accepts_public_code() -> None:
    item = next(
        item
        for item in load_catalog().principles
        if item.editorial_status == "source_checked"
    )

    completed = subprocess.run(
        [sys.executable, "-m", "principle_catalog", "study-brief", item.code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"内部キー: `{item.id}`" in completed.stdout
    assert "正解:" in completed.stdout


def test_sync_preserves_retired_key_history_without_inheriting_split_progress(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    retired_key, migration = next(
        (key, record)
        for key, record in catalog.migration.retired.items()
        if record.operation == "split"
    )
    historical = {
        "id": retired_key,
        "title": "旧カードの履歴",
        "status": "retained_14d",
        "stage": "completed_14d",
    }
    state = {"version": 1, "items": [historical]}
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    sync_study_items(path)
    updated = json.loads(path.read_text(encoding="utf-8"))
    by_key = {item["id"]: item for item in updated["items"]}
    catalog_by_key = {item.id: item for item in catalog.principles}

    assert updated["items"][0] == historical
    for target in migration.targets:
        if catalog_by_key[target].editorial_status == "source_checked":
            assert by_key[target]["status"] == "not_started"
        else:
            assert target not in by_key


def test_public_projection_ignores_preserved_retired_key_history(
    tmp_path: Path,
) -> None:
    retired_key = next(iter(load_catalog().migration.retired))
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {"items": [{"id": retired_key, "status": "retained_14d"}]}
        ),
        encoding="utf-8",
    )

    assert public_progress_from_local(path) == {}
