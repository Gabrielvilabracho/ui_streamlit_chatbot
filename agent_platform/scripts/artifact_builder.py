"""Validate editable agent sources and build deterministic deployment-neutral artifacts."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when a platform source violates its local contract."""


def build_spec(platform_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    """Build the one supported GENERAL candidate without writing to disk."""

    root = platform_root.resolve()
    manifest_path = root / "agents" / "sofia-general" / "agent.toml"
    manifest = _toml_mapping(manifest_path)
    agent = _mapping(manifest, "agent", manifest_path)
    access = _mapping(manifest, "access", manifest_path)

    project_path = _source_path(root, _text(agent, "project_reference", manifest_path))
    evaluation_path = _source_path(root, _text(agent, "evaluation_reference", manifest_path))
    project = _mapping(_toml_mapping(project_path), "project", project_path)
    evaluation = _mapping(_toml_mapping(evaluation_path), "evaluation", evaluation_path)

    layers = _prompt_layers(root, agent, manifest_path)
    _validate_namespace(access, project, evaluation)

    source_paths = [manifest_path, project_path, evaluation_path, *[path for path, _ in layers]]
    source_hashes = {_relative(root, path): _sha256(path.read_bytes()) for path in source_paths}
    spec = {
        "schema_version": 1,
        "agent": {
            "name": _text(agent, "name", manifest_path),
            "environment": _text(agent, "environment", manifest_path),
        },
        "project": {"name": _text(project, "name", project_path)},
        "access": {
            key: _text(access, key, manifest_path)
            for key in (
                "database",
                "schema",
                "warehouse",
                "caller_role",
                "policy",
                "search_service",
            )
        },
        "evaluation": {
            key: _text(evaluation, key, evaluation_path)
            for key in ("dataset", "runs_table", "results_table", "policy")
        },
        "thresholds": _mapping(_toml_mapping(evaluation_path), "thresholds", evaluation_path),
        "prompts": {
            "layers": [
                {
                    "path": _relative(root, path),
                    "sha256": _sha256(content.encode()),
                    "content": content,
                }
                for path, content in layers
            ]
        },
    }
    spec["prompts"]["composed_sha256"] = _sha256(
        "\n\n".join(content for _, content in layers).encode()
    )
    return spec, source_hashes


def write_artifact(platform_root: Path, output_root: Path) -> Path:
    """Validate first, then write the candidate spec and its reproducibility manifest."""

    spec, source_hashes = build_spec(platform_root)
    encoded = _json(spec)
    destination = output_root / "sofia-general"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "agent-spec.json").write_text(encoded)
    build_manifest = {
        "artifact_sha256": _sha256(encoded.encode()),
        "source_sha256": source_hashes,
    }
    (destination / "build-manifest.json").write_text(_json(build_manifest))
    return destination


def _prompt_layers(
    root: Path, agent: Mapping[str, Any], manifest_path: Path
) -> list[tuple[Path, str]]:
    raw_layers = agent.get("prompt_layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValidationError(f"{manifest_path}: prompt_layers must be a non-empty list.")
    paths = [_source_path(root, value) for value in raw_layers]
    if len(paths) != len(set(paths)):
        raise ValidationError(f"{manifest_path}: prompt_layers must not contain duplicates.")
    return [(path, path.read_text().strip()) for path in paths]


def _validate_namespace(
    access: Mapping[str, Any], project: Mapping[str, Any], evaluation: Mapping[str, Any]
) -> None:
    for key in ("database", "schema", "warehouse", "owner_role"):
        if key == "owner_role":
            if _text(access, "caller_role", Path("agent manifest")) != _text(
                project, key, Path("project")
            ):
                raise ValidationError("caller role must match the project owner role.")
        elif _text(access, key, Path("agent manifest")) != _text(project, key, Path("project")):
            raise ValidationError(f"access {key} must match the project configuration.")
    database = _text(access, "database", Path("agent manifest"))
    schema = _text(access, "schema", Path("agent manifest"))
    expected_prefix = f"{database}.{schema}."
    for key in ("dataset", "runs_table", "results_table"):
        if not _text(evaluation, key, Path("evaluation")).startswith(expected_prefix):
            raise ValidationError(f"evaluation {key} must belong to {expected_prefix.rstrip('.')}.")
    if _text(access, "policy", Path("agent manifest")) != _text(
        evaluation, "policy", Path("evaluation")
    ):
        raise ValidationError("agent and evaluation policies must match.")


def _source_path(root: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("repository-relative prompt path must be a non-empty string.")
    path = (root / raw).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValidationError(
            "repository-relative prompt path escapes the platform root."
        ) from error
    if not path.is_file():
        raise ValidationError(f"repository-relative prompt path does not exist: {raw}")
    return path


def _toml_mapping(path: Path) -> Mapping[str, Any]:
    with path.open("rb") as source:
        data = tomllib.load(source)
    if not isinstance(data, Mapping):
        raise ValidationError(f"{path}: expected a TOML mapping.")
    return data


def _mapping(data: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValidationError(f"{path}: missing [{key}] table.")
    return value


def _text(data: Mapping[str, Any], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{path}: {key} must be non-empty text.")
    return value


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
