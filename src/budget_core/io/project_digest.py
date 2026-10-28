"""The model digest of a loaded project (D-204): its content, not the way it is written."""

from __future__ import annotations

from typing import Any

from budget_core.io.project_loader import model_to_data
from budget_core.manifest import data_digest
from budget_core.model import Project

_FOLDERS = (
    "units",
    "modes",
    "expendables",
    "orbits",
    "ground_stations",
    "targets",
    "scenarios",
    "links",
)


def project_data(project: Project) -> dict[str, Any]:
    """Every model of the project as plain data, keyed by kind and id. Comments, key order, the
    sources and statuses (D-213), file names other than the ids, and the folder the project was
    read from do not appear."""
    data: dict[str, Any] = {
        "project": model_to_data(project.meta, annotations=False),
        "spacecraft": model_to_data(project.spacecraft, annotations=False),
    }
    for folder in _FOLDERS:
        models = getattr(project, folder)
        data[folder] = {
            name: model_to_data(models[name], annotations=False) for name in sorted(models)
        }
    data["config"] = {
        name: model_to_data(model, annotations=False)
        for name in sorted(vars(project.config))
        if (model := getattr(project.config, name)) is not None
    }
    return data


def project_digest(project: Project) -> str:
    """`sha256:` and the hex digest of the canonical form of `project_data`."""
    return data_digest(project_data(project))
