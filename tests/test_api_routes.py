from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from atpiano.contracts.schemas import (
    DeleteSessionRequest,
    ScoreJobStart,
    ScoreVariantRequest,
    SessionAnnotationPatch,
)
from atpiano.corrected import CORRECTED_EVENT_SCHEMA, CorrectedSession
from atpiano.corrected_export import write_corrected_exports
from atpiano.corrected_workbench import create_corrected_workbench_server
from atpiano.live import PcmBlock
from atpiano.util import sha256_file, write_json


def _session(
    workspace: Path,
    session_id: str,
    *,
    with_note: bool = False,
) -> CorrectedSession:
    session = CorrectedSession(
        workspace / session_id,
        session_id=session_id,
        sample_rate_hz=8_000,
        source="replay",
        realtime=False,
        minimum_free_bytes=0,
    )
    session.accept_block(
        PcmBlock(
            sequence=0,
            first_sample=0,
            frame_count=100,
            sample_rate_hz=8_000,
            page_sent_ms=0.0,
            worklet_time_s=0.0125,
            pcm_s16le=b"\0\0" * 100,
        ),
        received_ns=1,
    )
    if with_note:
        session.append_events(
            [
                {
                    "schema_version": CORRECTED_EVENT_SCHEMA,
                    "session_id": session_id,
                    "event_id": "note-c4",
                    "revision": 1,
                    "lane": "commit",
                    "lifecycle": "committed",
                    "pitch": 60,
                    "controller": None,
                    "onset_sample": 10,
                    "offset_sample": 60,
                    "offset_state": "closed",
                    "velocity": 80,
                    "confidence": 0.9,
                }
            ]
        )
        session.advance_provisional(90)
        session.advance_commit(80)
    session.finalize()
    write_corrected_exports(session.directory)
    return session


def _score_runner(
    input_midi: Path,
    input_notes: Path,
    output_musicxml: Path,
    output_alignment: Path,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert input_midi.is_file()
    source = json.loads(input_notes.read_text(encoding="utf-8"))
    output_musicxml.write_text(
        """<score-partwise version="4.0">
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1"><measure number="1"><note id="test-note-1"><pitch><step>C</step>
<octave>4</octave></pitch><duration>1</duration></note></measure></part>
</score-partwise>
""",
        encoding="utf-8",
    )
    note = source["notes"][0]
    segment = {
        "musicxml_note_id": "test-note-1",
        "part": 1,
        "pitch": note["pitch"],
        "score_time_quarters": {"numerator": 0, "denominator": 1},
        "score_duration_quarters": {"numerator": 1, "denominator": 1},
        "tie": None,
    }
    write_json(
        output_alignment,
        {
            "schema_version": "atpiano.score-alignment.v2",
            "session_id": source["session_id"],
            "sample_rate_hz": source["sample_rate_hz"],
            "source": {
                "schema_version": source["schema_version"],
                "sha256": sha256_file(input_notes),
            },
            "musicxml": {"sha256": sha256_file(output_musicxml)},
            "mapping": {
                "algorithm": "monotonic-exact-pitch-lcs-v1",
                "source_order": "onset-sample,pitch,duration,source-index",
                "score_order": "attack-quarters,pitch,output-index",
            },
            "summary": {
                "source_notes": 1,
                "mapped_source_notes": 1,
                "unmatched_source_notes": 0,
                "musicxml_note_elements": 1,
                "inserted_score_note_elements": 0,
            },
            "rows": [
                {
                    "source_index": 0,
                    "event_id": note["event_id"],
                    "pitch": note["pitch"],
                    "onset_sample": note["onset_sample"],
                    "offset_sample": note["offset_sample"],
                    "status": "mapped",
                    "score_time_quarters": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "segments": [segment],
                }
            ],
            "inserted_score_segments": [],
        },
    )
    return {
        "schema_version": "test-score-runner.v1",
        "runtime_directory": str(runtime_directory),
    }


def _score_variant_runner(
    input_musicxml: Path,
    input_alignment: Path,
    output_musicxml: Path,
    output_alignment: Path,
    clef_policy: str,
    target_key_fifths: int | None,
    runtime_directory: Path,
) -> dict[str, Any]:
    assert clef_policy == "automatic"
    assert target_key_fifths == 6
    shutil.copy2(input_musicxml, output_musicxml)
    alignment = json.loads(input_alignment.read_text(encoding="utf-8"))
    alignment["musicxml"] = {"sha256": sha256_file(output_musicxml)}
    write_json(output_alignment, alignment)
    return {
        "schema_version": "test-score-variant-runner.v1",
        "runtime_directory": str(runtime_directory),
        "postprocess": {
            "schema_version": "atpiano.score-postprocessor.v1",
            "version": "deterministic-engraving-v1",
            "key_signature": {
                "source_fifths": -6,
                "source_label": "Six flats",
                "alternative_fifths": 6,
                "alternative_label": "Six sharps",
                "target_fifths": 6,
                "target_label": "Six sharps",
            },
            "clefs": {"needs_review": False},
            "needs_review": False,
        },
    }


def _serve(server: Any) -> tuple[threading.Thread, str]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread, f"http://127.0.0.1:{server.server_address[1]}"


def _get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=2) as response:
        value = json.load(response)
    assert isinstance(value, dict)
    return value


def _request_json(
    url: str,
    *,
    value: dict[str, Any],
    origin: str,
    method: str,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(value).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Origin": origin,
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        result = json.load(response)
        assert isinstance(result, dict)
        return response.status, result


def test_api_routes_read_explicit_history_without_retargeting_current(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    _session(tmp_path, older_id, with_note=True)
    _session(tmp_path, newer_id)
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,
        score_runtime=tmp_path / "runtime",
        score_runner=_score_runner,
        score_variant_runner=_score_variant_runner,
    )
    thread, base_url = _serve(server)
    api = f"{base_url}/api/v1"
    try:
        capabilities = _get(f"{api}/capabilities")
        catalog = _get(f"{api}/workspaces/local/sessions?limit=1")
        older = _get(
            f"{api}/workspaces/local/sessions/{older_id}"
        )
        events = _get(
            f"{api}/workspaces/local/sessions/{older_id}/events"
            "?start_sample=0&end_sample=100"
        )
        legacy_current = _get(f"{base_url}/api/session")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert capabilities["supported_schema_versions"] == [
        "atpiano.contract.v1"
    ]
    assert capabilities["capture_sources"] == ["microphone"]
    assert catalog["items"][0]["session_id"] == newer_id
    assert catalog["next_cursor"] == newer_id
    assert older["session_id"] == older_id
    assert events["session_id"] == older_id
    assert events["items"][0]["event_id"] == "note-c4"
    assert legacy_current["session_id"] == newer_id


def test_api_score_job_and_artifacts_remain_targeted_to_history(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    _session(tmp_path, older_id, with_note=True)
    _session(tmp_path, newer_id)
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,
        score_runtime=tmp_path / "runtime",
        score_runner=_score_runner,
        score_variant_runner=_score_variant_runner,
    )
    thread, base_url = _serve(server)
    api = f"{base_url}/api/v1"
    try:
        request = ScoreJobStart(
            workspace_id="local",
            session_id=older_id,
            transcription_run_id=f"legacy-v2:{older_id}",
            commit_sample=80,
            request_id="request-score-1",
        )
        status, job = _request_json(
            f"{api}/workspaces/local/sessions/{older_id}/score-jobs",
            value=request.model_dump(mode="json"),
            origin=base_url,
            method="POST",
        )
        assert status == 202
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            job = _get(f"{api}/jobs/{job['job_id']}")
            if job["status"] != "running":
                break
            time.sleep(0.01)
        artifacts = _get(
            f"{api}/workspaces/local/sessions/{older_id}/artifacts"
        )
        musicxml = next(
            item
            for item in artifacts["items"]
            if item["filename"] == "score.musicxml"
        )
        alignment = next(
            item
            for item in artifacts["items"]
            if item["kind"] == "score-alignment"
        )
        access = _get(
            f"{api}/workspaces/local/sessions/{older_id}"
            f"/artifacts/{musicxml['artifact_id']}/access"
        )
        with urllib.request.urlopen(
            f"{base_url}{access['url']}",
            timeout=2,
        ) as response:
            body = response.read()
        alignment_access = _get(
            f"{api}/workspaces/local/sessions/{older_id}"
            f"/artifacts/{alignment['artifact_id']}/access"
        )
        with urllib.request.urlopen(
            f"{base_url}{alignment_access['url']}",
            timeout=2,
        ) as response:
            alignment_body = json.load(response)
        variants = _get(
            f"{api}/workspaces/local/sessions/{older_id}/score-variants"
        )
        automatic = next(
            item for item in variants["items"] if item["role"] == "automatic"
        )
        variant_request = ScoreVariantRequest(
            workspace_id="local",
            session_id=older_id,
            baseline_musicxml_artifact_id=(
                automatic["baseline_musicxml_artifact_id"]
            ),
            baseline_alignment_artifact_id=(
                automatic["baseline_alignment_artifact_id"]
            ),
            target_key_fifths=6,
            request_id="request-variant-1",
        )
        variant_status, enharmonic = _request_json(
            f"{api}/workspaces/local/sessions/{older_id}/score-variants",
            value=variant_request.model_dump(mode="json"),
            origin=base_url,
            method="POST",
        )
        selected_variants = _get(
            f"{api}/workspaces/local/sessions/{older_id}/score-variants"
        )
        legacy_current = _get(f"{base_url}/api/session")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert job["status"] == "complete"
    assert job["session_id"] == older_id
    assert access["session_id"] == older_id
    assert musicxml["source_horizon_sample"] == 80
    assert alignment["source_horizon_sample"] == 80
    assert b"score-partwise" in body
    assert alignment_body["summary"]["mapped_source_notes"] == 1
    assert variant_status == 201
    assert enharmonic["role"] == "enharmonic"
    assert enharmonic["target_key_fifths"] == 6
    assert next(
        item for item in selected_variants["items"] if item["selected"]
    )["score_variant_id"] == enharmonic["score_variant_id"]
    assert legacy_current["session_id"] == newer_id


def test_api_delete_is_recoverable_and_structured(
    tmp_path: Path,
) -> None:
    older_id = "20260726T100000-aaaaaaaaaaaa"
    newer_id = "20260726T100001-bbbbbbbbbbbb"
    _session(tmp_path, older_id)
    _session(tmp_path, newer_id)
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,
    )
    thread, base_url = _serve(server)
    api = f"{base_url}/api/v1"
    try:
        request = DeleteSessionRequest(
            workspace_id="local",
            session_id=older_id,
            request_id="request-delete-1",
            confirmation="recoverable-delete",
        )
        status, result = _request_json(
            f"{api}/workspaces/local/sessions/{older_id}",
            value=request.model_dump(mode="json"),
            origin=base_url,
            method="DELETE",
        )
        assert status == 200
        try:
            _get(f"{api}/workspaces/local/sessions/{older_id}")
        except urllib.error.HTTPError as error:
            assert error.code == 404
            failure = json.load(error)
        else:
            raise AssertionError("deleted session remained readable")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result["recoverable"] is True
    assert failure["error"]["code"] == "not-found"
    assert (tmp_path / newer_id / "session.json").is_file()
    assert len(list((tmp_path / ".trash").iterdir())) == 1


def test_api_updates_application_owned_session_name(
    tmp_path: Path,
) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    _session(tmp_path, session_id)
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,
    )
    thread, base_url = _serve(server)
    api = f"{base_url}/api/v1"
    try:
        request = SessionAnnotationPatch(
            workspace_id="local",
            session_id=session_id,
            display_name="  Evening invention  ",
            request_id="request-rename-1",
        )
        status, result = _request_json(
            f"{api}/workspaces/local/sessions/{session_id}",
            value=request.model_dump(mode="json"),
            origin=base_url,
            method="PATCH",
        )
        renamed = _get(
            f"{api}/workspaces/local/sessions/{session_id}"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 200
    assert result["display_name"] == "Evening invention"
    assert renamed["display_name"] == "Evening invention"
    assert (tmp_path / session_id / "session.json").is_file()


def test_api_delete_rejects_active_session(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    session_id = "20260726T100000-aaaaaaaaaaaa"
    _session(tmp_path, session_id)
    server = create_corrected_workbench_server(
        tmp_path,
        port=0,
        minimum_free_bytes=0,
        commit_model_factory=lambda: None,
    )
    monkeypatch.setattr(
        server.application.capture,
        "active_session_id",
        lambda: session_id,
    )
    thread, base_url = _serve(server)
    try:
        request = DeleteSessionRequest(
            workspace_id="local",
            session_id=session_id,
            request_id="request-delete-active",
            confirmation="recoverable-delete",
        )
        try:
            _request_json(
                f"{base_url}/api/v1/workspaces/local"
                f"/sessions/{session_id}",
                value=request.model_dump(mode="json"),
                origin=base_url,
                method="DELETE",
            )
        except urllib.error.HTTPError as error:
            assert error.code == 409
            failure = json.load(error)
        else:
            raise AssertionError("active session deletion succeeded")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert failure["error"]["code"] == "session-active"
    assert (tmp_path / session_id / "session.json").is_file()
