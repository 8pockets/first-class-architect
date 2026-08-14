from pathlib import Path

import yaml


CI_PATH = Path(".github/workflows/ci.yml")
PAGES_PATH = Path(".github/workflows/pages.yml")


def _workflow(path: Path) -> dict[str, object]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def test_ci_runs_for_pull_requests_without_write_permissions() -> None:
    workflow = _workflow(CI_PATH)
    triggers = workflow["on"]

    assert isinstance(triggers, dict)
    assert "pull_request" in triggers
    assert workflow["permissions"] == {"contents": "read"}
    text = CI_PATH.read_text(encoding="utf-8")
    assert "pages: write" not in text
    assert "id-token: write" not in text
    assert "uv sync --locked --group dev" in text
    assert "uv run --locked python -m pytest" in text
    assert "node --test tests/catalog-interactions.test.mjs" in text
    assert "--frozen" not in text


def test_pages_deploys_only_main_and_separates_permissions() -> None:
    workflow = _workflow(PAGES_PATH)
    triggers = workflow["on"]
    jobs = workflow["jobs"]

    assert isinstance(triggers, dict)
    assert triggers["push"]["branches"] == ["main"]
    assert isinstance(jobs, dict)
    assert jobs["build"]["if"] == "github.ref == 'refs/heads/main'"
    assert jobs["deploy"]["if"] == "github.ref == 'refs/heads/main'"
    assert jobs["build"]["permissions"] == {
        "contents": "read",
        "pages": "read",
    }
    assert jobs["deploy"]["permissions"] == {
        "pages": "write",
        "id-token": "write",
    }
    assert jobs["deploy"]["needs"] == "build"
    build_steps = jobs["build"]["steps"]
    assert any(step.get("run") == "uv run --locked python -m pytest" for step in build_steps)
    assert any(
        step.get("run") == "node --check principle_catalog/static/catalog.js"
        for step in build_steps
    )
    assert any(
        step.get("run") == "node --test tests/catalog-interactions.test.mjs"
        for step in build_steps
    )


def test_pages_uses_pinned_actions_and_no_auth_secrets() -> None:
    text = PAGES_PATH.read_text(encoding="utf-8")

    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in text
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in text
    assert "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d" in text
    assert "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9" in text
    assert "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128" in text
    assert "CODEX_AUTH_JSON" not in text
    assert "CODEX_AUTH_SECRET_WRITER_TOKEN" not in text
    assert "auth.json" not in text
    assert "secrets." not in text
    assert "contents: write" not in text
    assert "issues: write" not in text
    assert "uv sync --locked --group dev" in text
    assert "uv run --locked python -m principle_catalog validate" in text
    assert "--frozen" not in text


def test_ci_and_pages_reject_changes_to_existing_print_numbers() -> None:
    for path, job_name in ((CI_PATH, "validate"), (PAGES_PATH, "build")):
        workflow = _workflow(path)
        steps = workflow["jobs"][job_name]["steps"]
        checkout = next(step for step in steps if step.get("name") == "Checkout")
        assert checkout["with"]["fetch-depth"] == "0"
        previous = next(
            step for step in steps if step.get("name") == "Read previous print registry"
        )
        expected_sha = (
            "${{ github.event.pull_request.base.sha || github.event.before }}"
            if path == CI_PATH
            else "${{ github.event.before }}"
        )
        assert previous["env"]["PREVIOUS_SHA"] == expected_sha
        assert 'previous_sha="${PREVIOUS_SHA:-HEAD^}"' in previous["run"]
        text = path.read_text(encoding="utf-8")
        assert 'git show "${previous_sha}:data/principles/steel/manifest.yaml"' in text
        assert (
            "uv run --locked python -m principle_catalog verify-print-registry "
            '--previous "${RUNNER_TEMP}/previous-manifest.yaml"'
            in text
        )
