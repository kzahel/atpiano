"""Generate OpenAPI and TypeScript wire contracts from Pydantic."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from atpiano.contracts.schemas import contract_models
from atpiano.corrected_export import (
    MIDI_TEMPO_US_PER_BEAT,
    MIDI_TICKS_PER_BEAT,
    midi_tick_at_sample,
)
from atpiano.score_alignment import score_input_notes_document
from atpiano.util import resolve_command, write_json

OPENAPI_RELATIVE_PATH = Path("contracts/openapi/atpiano-api-v1.json")
TYPESCRIPT_RELATIVE_PATH = Path("app/src/generated/schema.ts")
MIDI_TICK_FIXTURE_RELATIVE_PATH = Path(
    "contracts/fixtures/v1/midi-tick-parity.json"
)
MIDI_TICK_FIXTURE_SCHEMA = "atpiano.midi-tick-parity.v1"
MIDI_TICK_OPERATION_IDENTITY = (
    "mido-second2tick-float-python-half-even-v1"
)


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


def build_midi_tick_parity_document() -> dict[str, Any]:
    """Generate canonical producer timing and ordering expectations."""

    sample_rate_hz = 48_000
    samples = [
        ("zero", 0),
        ("below-first-half", 24),
        ("first-half", 25),
        ("above-first-half", 26),
        ("retained-ties-to-even-down", 3_063_125),
        ("retained-float-above-half", 1_556_525),
        ("retained-collision-neighbor", 1_556_530),
        ("near-session-limit", sample_rate_hz * 15 * 60 - 1),
    ]
    durations = [
        ("one-tick", 5_000, 5_050),
        ("same-tick", 1_556_525, 1_556_530),
        ("retained-long", 1_556_525, 1_596_339),
    ]
    notes = [
        {
            "event_id": "retained-later-low",
            "pitch": 65,
            "onset_sample": 1_556_530,
            "offset_sample": 1_559_535,
            "velocity": 64,
        },
        {
            "event_id": "retained-half-high",
            "pitch": 77,
            "onset_sample": 1_556_525,
            "offset_sample": 1_596_339,
            "velocity": 64,
        },
        {
            "event_id": "duration-long",
            "pitch": 60,
            "onset_sample": 5_000,
            "offset_sample": 5_100,
            "velocity": 64,
        },
        {
            "event_id": "duration-short",
            "pitch": 60,
            "onset_sample": 5_000,
            "offset_sample": 5_050,
            "velocity": 64,
        },
        {
            "event_id": "later-source-sample",
            "pitch": 60,
            "onset_sample": 5_002,
            "offset_sample": 5_052,
            "velocity": 64,
        },
        {
            "event_id": "identity-b",
            "pitch": 61,
            "onset_sample": 6_000,
            "offset_sample": 6_050,
            "velocity": 64,
        },
        {
            "event_id": "identity-a",
            "pitch": 61,
            "onset_sample": 6_000,
            "offset_sample": 6_050,
            "velocity": 64,
        },
    ]
    ordered = score_input_notes_document(
        session_id="midi-tick-parity",
        sample_rate_hz=sample_rate_hz,
        notes=notes,
    )
    return {
        "schema_version": MIDI_TICK_FIXTURE_SCHEMA,
        "operation_identity": MIDI_TICK_OPERATION_IDENTITY,
        "parameters": {
            "sample_rate_hz": sample_rate_hz,
            "ticks_per_beat": MIDI_TICKS_PER_BEAT,
            "tempo_us_per_beat": MIDI_TEMPO_US_PER_BEAT,
        },
        "tick_cases": [
            {
                "label": label,
                "source_sample": source_sample,
                "expected_tick": midi_tick_at_sample(
                    source_sample,
                    sample_rate_hz=sample_rate_hz,
                ),
            }
            for label, source_sample in samples
        ],
        "duration_cases": [
            {
                "label": label,
                "onset_sample": onset_sample,
                "offset_sample": offset_sample,
                "expected_onset_tick": midi_tick_at_sample(
                    onset_sample,
                    sample_rate_hz=sample_rate_hz,
                ),
                "expected_offset_tick": midi_tick_at_sample(
                    offset_sample,
                    sample_rate_hz=sample_rate_hz,
                ),
                "expected_duration_ticks": (
                    midi_tick_at_sample(
                        offset_sample,
                        sample_rate_hz=sample_rate_hz,
                    )
                    - midi_tick_at_sample(
                        onset_sample,
                        sample_rate_hz=sample_rate_hz,
                    )
                ),
            }
            for label, onset_sample, offset_sample in durations
        ],
        "ordering": {
            "notes": notes,
            "expected_event_ids": [
                note["event_id"] for note in ordered["notes"]
            ],
        },
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
    executable = (
        root
        / "app"
        / "node_modules"
        / "openapi-typescript"
        / "bin"
        / "cli.js"
    )
    if not executable.is_file():
        raise RuntimeError(
            "TypeScript dependencies are missing; run `npm ci --prefix app`"
        )
    subprocess.run(
        resolve_command(
            [
                "node",
                str(executable),
                str(openapi_path),
                "-o",
                str(output_path),
            ]
        ),
        cwd=root,
        check=True,
    )


def generate_contracts(
    *,
    check: bool = False,
    root: Path | None = None,
) -> tuple[Path, Path, Path]:
    root = (root or _repository_root()).resolve()
    openapi_path = root / OPENAPI_RELATIVE_PATH
    typescript_path = root / TYPESCRIPT_RELATIVE_PATH
    midi_tick_fixture_path = root / MIDI_TICK_FIXTURE_RELATIVE_PATH
    document = build_openapi_document()
    midi_tick_fixture = build_midi_tick_parity_document()

    with tempfile.TemporaryDirectory(prefix="atpiano-contracts-") as temporary:
        temporary_root = Path(temporary)
        expected_openapi = temporary_root / "openapi.json"
        expected_openapi.write_bytes(_json_bytes(document))
        expected_typescript = temporary_root / "schema.ts"
        expected_midi_tick_fixture = temporary_root / "midi-tick-parity.json"
        expected_midi_tick_fixture.write_bytes(
            _json_bytes(midi_tick_fixture)
        )
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
                    (
                        midi_tick_fixture_path,
                        expected_midi_tick_fixture,
                    ),
                )
                if not path.is_file() or path.read_bytes() != expected.read_bytes()
            ]
            if drifted:
                names = ", ".join(
                    path.relative_to(root).as_posix() for path in drifted
                )
                raise RuntimeError(
                    f"generated contracts have drifted: {names}"
                )
        else:
            write_json(openapi_path, document)
            typescript_path.parent.mkdir(parents=True, exist_ok=True)
            typescript_path.write_bytes(expected_typescript.read_bytes())
            midi_tick_fixture_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            midi_tick_fixture_path.write_bytes(
                expected_midi_tick_fixture.read_bytes()
            )
    return openapi_path, typescript_path, midi_tick_fixture_path
