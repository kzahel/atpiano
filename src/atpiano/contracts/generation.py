"""Generate OpenAPI and TypeScript wire contracts from Pydantic."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from atpiano.contracts.schemas import contract_models
from atpiano.util import write_json

OPENAPI_RELATIVE_PATH = Path("contracts/openapi/atpiano-api-v1.json")
TYPESCRIPT_RELATIVE_PATH = Path("app/src/generated/schema.ts")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _reference(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _response(name: str, *, status: str = "200") -> dict[str, Any]:
    return {
        status: {
            "description": name,
            "content": {
                "application/json": {
                    "schema": _reference(name),
                }
            },
        },
        "default": {
            "description": "Structured API error",
            "content": {
                "application/json": {
                    "schema": _reference("ErrorResponse"),
                }
            },
        },
    }


def _request(name: str) -> dict[str, Any]:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": _reference(name),
            }
        },
    }


def _path_parameter(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
    }


def _query_parameter(
    name: str,
    *,
    required: bool = False,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "in": "query",
        "required": required,
        "schema": schema or {"type": "string"},
    }


def build_openapi_document() -> dict[str, Any]:
    _, combined = models_json_schema(
        [(model, "validation") for model in contract_models()],
        ref_template="#/components/schemas/{model}",
    )
    schemas = combined["$defs"]
    workspace_id = _path_parameter("workspace_id")
    group_id = _path_parameter("group_id")
    session_id = _path_parameter("session_id")
    job_id = _path_parameter("job_id")
    artifact_id = _path_parameter("artifact_id")
    cursor = _query_parameter("cursor")
    limit = _query_parameter(
        "limit",
        schema={"type": "integer", "minimum": 1, "maximum": 4096, "default": 100},
    )
    paths = {
        "/api/v1/auth/login": {
            "post": {
                "operationId": "login",
                "requestBody": _request("LoginRequest"),
                "responses": _response("AuthSession"),
            }
        },
        "/api/v1/auth/logout": {
            "post": {
                "operationId": "logout",
                "responses": _response("LogoutResult"),
            }
        },
        "/api/v1/auth/session": {
            "get": {
                "operationId": "getAuthSession",
                "responses": _response("AuthSession"),
            }
        },
        "/api/v1/capabilities": {
            "get": {
                "operationId": "getCapabilities",
                "responses": _response("RuntimeCapabilities"),
            }
        },
        "/api/v1/workspaces": {
            "get": {
                "operationId": "listWorkspaces",
                "parameters": [cursor, limit],
                "responses": _response("WorkspacePage"),
            }
        },
        "/api/v1/groups": {
            "get": {
                "operationId": "listGroups",
                "responses": _response("GroupPage"),
            }
        },
        "/api/v1/groups/{group_id}/profiles": {
            "post": {
                "operationId": "createProfile",
                "parameters": [group_id],
                "requestBody": _request("ProfileCreate"),
                "responses": _response("Profile", status="201"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/profiles": {
            "get": {
                "operationId": "listProfiles",
                "parameters": [workspace_id, cursor, limit],
                "responses": _response("ProfilePage"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions": {
            "get": {
                "operationId": "listSessions",
                "parameters": [workspace_id, cursor, limit],
                "responses": _response("SessionPage"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/recording-imports": {
            "post": {
                "operationId": "importRecording",
                "parameters": [
                    workspace_id,
                    {
                        "name": "X-Atpiano-Filename",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 255},
                    },
                    {
                        "name": "X-Atpiano-Request-Id",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 128},
                    },
                    {
                        "name": "X-Atpiano-Performer-Profile",
                        "in": "header",
                        "required": False,
                        "schema": {"type": "string", "maxLength": 128},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "audio/wav": {
                            "schema": {
                                "type": "string",
                                "format": "binary",
                            }
                        },
                        "audio/mpeg": {
                            "schema": {
                                "type": "string",
                                "format": "binary",
                            }
                        },
                        "application/octet-stream": {
                            "schema": {
                                "type": "string",
                                "format": "binary",
                            }
                        },
                    },
                },
                "responses": _response("Capture", status="202"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}": {
            "get": {
                "operationId": "getSession",
                "parameters": [workspace_id, session_id],
                "responses": _response("Session"),
            },
            "patch": {
                "operationId": "updateSessionAnnotation",
                "parameters": [workspace_id, session_id],
                "requestBody": _request("SessionAnnotationPatch"),
                "responses": _response("SessionAnnotation"),
            },
            "delete": {
                "operationId": "deleteSession",
                "parameters": [workspace_id, session_id],
                "requestBody": _request("DeleteSessionRequest"),
                "responses": _response("DeleteSessionResult"),
            },
        },
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/performer"
        ): {
            "patch": {
                "operationId": "updateSessionPerformer",
                "parameters": [workspace_id, session_id],
                "requestBody": _request("SessionPerformerPatch"),
                "responses": _response(
                    "SessionPerformerAttribution"
                ),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/horizon": {
            "get": {
                "operationId": "getHorizon",
                "parameters": [workspace_id, session_id],
                "responses": _response("Horizon"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/events": {
            "get": {
                "operationId": "listEvents",
                "parameters": [
                    workspace_id,
                    session_id,
                    _query_parameter(
                        "start_sample",
                        required=True,
                        schema={"type": "integer", "minimum": 0},
                    ),
                    _query_parameter(
                        "end_sample",
                        required=True,
                        schema={"type": "integer", "minimum": 0},
                    ),
                    cursor,
                    limit,
                ],
                "responses": _response("EventPage"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/artifacts": {
            "get": {
                "operationId": "listArtifacts",
                "parameters": [workspace_id, session_id, cursor, limit],
                "responses": _response("ArtifactPage"),
            }
        },
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/artifacts/{artifact_id}/access"
        ): {
            "get": {
                "operationId": "getArtifactAccess",
                "parameters": [workspace_id, session_id, artifact_id],
                "responses": _response("ArtifactAccess"),
            }
        },
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/score-jobs": {
            "post": {
                "operationId": "startScoreJob",
                "parameters": [workspace_id, session_id],
                "requestBody": _request("ScoreJobStart"),
                "responses": _response("Job", status="202"),
            }
        },
        (
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}"
            "/score-variants"
        ): {
            "get": {
                "operationId": "listScoreVariants",
                "parameters": [workspace_id, session_id],
                "responses": _response("ScoreVariantPage"),
            },
            "post": {
                "operationId": "createScoreVariant",
                "parameters": [workspace_id, session_id],
                "requestBody": _request("ScoreVariantRequest"),
                "responses": _response("ScoreVariant", status="201"),
            },
        },
        "/api/v1/jobs/{job_id}": {
            "get": {
                "operationId": "getJob",
                "parameters": [job_id],
                "responses": _response("Job"),
            }
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "atpiano API contract",
            "version": "1.0.0",
            "description": (
                "Platform-neutral atpiano operations. Musical time is always "
                "expressed in source-audio samples."
            ),
        },
        "paths": paths,
        "components": {"schemas": schemas},
    }


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _generate_typescript(
    *,
    root: Path,
    openapi_path: Path,
    output_path: Path,
) -> None:
    executable = root / "app" / "node_modules" / ".bin" / "openapi-typescript"
    if not executable.is_file():
        raise RuntimeError(
            "TypeScript dependencies are missing; run `npm ci --prefix app`"
        )
    subprocess.run(
        [str(executable), str(openapi_path), "-o", str(output_path)],
        cwd=root,
        check=True,
    )


def generate_contracts(
    *,
    check: bool = False,
    root: Path | None = None,
) -> tuple[Path, Path]:
    root = (root or _repository_root()).resolve()
    openapi_path = root / OPENAPI_RELATIVE_PATH
    typescript_path = root / TYPESCRIPT_RELATIVE_PATH
    document = build_openapi_document()

    with tempfile.TemporaryDirectory(prefix="atpiano-contracts-") as temporary:
        temporary_root = Path(temporary)
        expected_openapi = temporary_root / "openapi.json"
        expected_openapi.write_bytes(_json_bytes(document))
        expected_typescript = temporary_root / "schema.ts"
        _generate_typescript(
            root=root,
            openapi_path=expected_openapi,
            output_path=expected_typescript,
        )

        if check:
            drifted = [
                path
                for path, expected in (
                    (openapi_path, expected_openapi),
                    (typescript_path, expected_typescript),
                )
                if not path.is_file() or path.read_bytes() != expected.read_bytes()
            ]
            if drifted:
                names = ", ".join(str(path.relative_to(root)) for path in drifted)
                raise RuntimeError(f"generated API contracts have drifted: {names}")
        else:
            write_json(openapi_path, document)
            typescript_path.parent.mkdir(parents=True, exist_ok=True)
            typescript_path.write_bytes(expected_typescript.read_bytes())
    return openapi_path, typescript_path
