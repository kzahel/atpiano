"""Command-line entry point for atpiano."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


def _add_storage_arguments(parser: argparse.ArgumentParser) -> None:
    recording_policy = parser.add_mutually_exclusive_group()
    recording_policy.add_argument(
        "--compact-recordings",
        dest="compact_recordings",
        action="store_true",
        help=(
            "retain verified 128 kbps MP3 and retire new-session WAV "
            "source after settlement (default; compatibility alias)"
        ),
    )
    recording_policy.add_argument(
        "--retain-wav",
        dest="compact_recordings",
        action="store_false",
        help=(
            "retain new-session WAV source alongside MP3 for debugging "
            "or future retranscription"
        ),
    )
    parser.set_defaults(compact_recordings=True)
    parser.add_argument(
        "--debug-retention",
        action="store_true",
        help="retain bounded local model diagnostics (default: off)",
    )
    parser.add_argument(
        "--debug-byte-cap-mib",
        type=float,
        default=64.0,
        help="workspace debug byte cap when enabled (default: 64 MiB)",
    )
    parser.add_argument(
        "--debug-max-age-hours",
        type=float,
        default=72.0,
        help="unpinned debug maximum age when enabled (default: 72 hours)",
    )


def _add_model_lifecycle_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--model-idle-timeout-seconds",
        type=float,
        default=10 * 60,
        help=(
            "unload warmed capture models this long after settlement; "
            "0 keeps them loaded (default: 600)"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atpiano",
        description="Acoustic-piano transcription research harness",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show the atpiano version",
    )
    subparsers = parser.add_subparsers(dest="command")
    fixture_parser = subparsers.add_parser(
        "fixture",
        help="generate the deterministic MIDI-derived audio fixture",
    )
    fixture_parser.add_argument("output_directory", type=Path)
    fixture_parser.add_argument(
        "--force",
        action="store_true",
        help="replace fixture files in the target directory",
    )
    musical_fixture_parser = subparsers.add_parser(
        "musical-fixture",
        help="generate the aligned deterministic musical-loop fixture",
    )
    musical_fixture_parser.add_argument("output_directory", type=Path)
    musical_fixture_parser.add_argument(
        "--force",
        action="store_true",
        help="replace fixture files in the target directory",
    )
    offline_parser = subparsers.add_parser(
        "offline",
        help="run the untouched Basic Pitch offline reference",
    )
    offline_parser.add_argument("input_manifest", type=Path)
    offline_parser.add_argument("run_directory", type=Path)
    replay_parser = subparsers.add_parser(
        "replay",
        help="replay audio at wall-clock cadence through Basic Pitch windows",
    )
    replay_parser.add_argument("input_manifest", type=Path)
    replay_parser.add_argument("run_directory", type=Path)
    replay_parser.add_argument(
        "--block-samples",
        type=int,
        default=1024,
        help="source delivery block size (default: 1024)",
    )
    replay_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="exercise replay without wall-clock waits; latency is not reported",
    )
    corrected_replay_parser = subparsers.add_parser(
        "replay-v2",
        help="feed a WAV manifest through the bounded corrected-session engine",
    )
    corrected_replay_parser.add_argument("input_manifest", type=Path)
    corrected_replay_parser.add_argument("session_directory", type=Path)
    corrected_replay_parser.add_argument("--repeat", type=int, default=1)
    corrected_replay_parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.0,
        help="declared silence inserted between repetitions (default: 0)",
    )
    corrected_replay_parser.add_argument(
        "--block-samples",
        type=int,
        default=4096,
        help="source delivery block size (default: 4096)",
    )
    corrected_replay_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="exercise replay without wall-clock waits",
    )
    corrected_replay_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="stop before free space falls below this reserve (default: 2)",
    )
    corrected_replay_parser.add_argument(
        "--preview",
        action="store_true",
        help="run the bounded Basic Pitch provisional lane",
    )
    corrected_replay_parser.add_argument(
        "--commit",
        action="store_true",
        help="run the trailing Transkun corrected-note lane",
    )
    corrected_replay_parser.add_argument(
        "--commit-device",
        default="cpu",
        help="Transkun execution device (default: cpu)",
    )
    backend_profile_parser = subparsers.add_parser(
        "profile-backend",
        help="measure an isolated Transkun worker for correction-mode selection",
    )
    backend_profile_parser.add_argument("input_manifest", type=Path)
    backend_profile_parser.add_argument("output_directory", type=Path)
    backend_profile_parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="continuous-clock fixture repetitions (default: 2)",
    )
    backend_profile_parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.0,
        help="declared silence between repetitions (default: 0)",
    )
    backend_profile_parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=16.0,
        help="unmeasured model warm-up source duration (default: 16)",
    )
    backend_profile_parser.add_argument(
        "--commit-device",
        default="cpu",
        help="Transkun execution device (default: cpu)",
    )
    backend_profile_parser.add_argument(
        "--commit-threads",
        type=int,
        default=2,
        help="maximum Transkun CPU threads (default: 2)",
    )
    backend_profile_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="stop before free space falls below this reserve (default: 2)",
    )
    storage_validation_parser = subparsers.add_parser(
        "validate-storage",
        help="run accelerated Phase 4 compact-storage validation",
    )
    storage_validation_parser.add_argument(
        "input_manifest",
        type=Path,
    )
    storage_validation_parser.add_argument(
        "workspace",
        type=Path,
    )
    storage_validation_parser.add_argument(
        "--minimum-hours",
        type=float,
        default=1.0,
        help="minimum continuous source-clock duration (default: 1)",
    )
    storage_validation_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="protected free-space reserve (default: 2 GiB)",
    )
    storage_validation_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=900.0,
        help="wall-clock validation timeout (default: 900)",
    )
    review_parser = subparsers.add_parser(
        "review",
        help="serve a local browser reviewer for a completed run",
    )
    review_parser.add_argument("run_directory", type=Path)
    review_parser.add_argument("--bind", default="127.0.0.1")
    review_parser.add_argument("--port", type=int, default=8000)
    review_parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the reviewer in the default browser",
    )
    workbench_parser = subparsers.add_parser(
        "workbench",
        help="record, transcribe, and review from one local browser page",
    )
    workbench_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("results/workbench"),
        help="generated artifact directory (default: results/workbench)",
    )
    workbench_parser.add_argument("--port", type=int, default=8000)
    workbench_parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the workbench in the default browser",
    )
    corrected_workbench_parser = subparsers.add_parser(
        "workbench-v2",
        help="run the bounded corrected-note capture and replay application",
    )
    corrected_workbench_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("results/workbench-v2"),
        help="segmented session directory (default: results/workbench-v2)",
    )
    corrected_workbench_parser.add_argument("--port", type=int, default=8001)
    corrected_workbench_parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the corrected workbench in the default browser",
    )
    corrected_workbench_parser.add_argument(
        "--replay",
        type=Path,
        help="start by replaying this deterministic input manifest",
    )
    corrected_workbench_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="number of continuous-clock replay repetitions (default: 1)",
    )
    corrected_workbench_parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.0,
        help="declared silence inserted between replay repetitions (default: 0)",
    )
    corrected_workbench_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="run configured replay without wall-clock waits",
    )
    corrected_workbench_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="stop before free space falls below this reserve (default: 2)",
    )
    corrected_workbench_parser.add_argument(
        "--commit-device",
        default="cpu",
        help="Transkun execution device (default: cpu)",
    )
    corrected_workbench_parser.add_argument(
        "--commit-threads",
        type=int,
        default=2,
        help="maximum Transkun CPU threads (default: 2)",
    )
    corrected_workbench_parser.add_argument(
        "--correction-mode",
        choices=("auto", "live", "delayed", "after-stop", "unavailable"),
        default="auto",
        help="when the corrected lane may run (default: auto)",
    )
    corrected_workbench_parser.add_argument(
        "--backend-profile",
        type=Path,
        default=Path("results/backend-profile/backend-profile.json"),
        help="measured backend profile used by automatic correction mode",
    )
    corrected_workbench_parser.add_argument(
        "--score-runtime",
        type=Path,
        default=Path("results/midi2score-runtime"),
        help="isolated MIDI2ScoreTransformer runtime directory",
    )
    _add_storage_arguments(corrected_workbench_parser)
    _add_model_lifecycle_arguments(corrected_workbench_parser)
    shared_app_parser = subparsers.add_parser(
        "workbench-v3",
        help="run the shared React performance workspace",
    )
    shared_app_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("results/workbench-v3"),
        help="segmented session directory (default: results/workbench-v3)",
    )
    shared_app_parser.add_argument(
        "--bind",
        default="127.0.0.1",
        help="address for the shared application server (default: 127.0.0.1)",
    )
    shared_app_parser.add_argument("--port", type=int, default=8002)
    shared_app_parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the shared application in the default browser",
    )
    shared_app_parser.add_argument(
        "--public-origin",
        help=(
            "exact HTTPS origin trusted for a temporary public tunnel "
            "(example: https://atpiano.example.com)"
        ),
    )
    shared_app_parser.add_argument(
        "--replay",
        type=Path,
        help="start by replaying this deterministic input manifest",
    )
    shared_app_parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="number of continuous-clock replay repetitions (default: 1)",
    )
    shared_app_parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.0,
        help="declared silence inserted between replay repetitions (default: 0)",
    )
    shared_app_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="run configured replay without wall-clock waits",
    )
    shared_app_parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=2.0,
        help="stop before free space falls below this reserve (default: 2)",
    )
    shared_app_parser.add_argument(
        "--commit-device",
        default="cpu",
        help="Transkun execution device (default: cpu)",
    )
    shared_app_parser.add_argument(
        "--commit-threads",
        type=int,
        default=2,
        help="maximum Transkun CPU threads (default: 2)",
    )
    shared_app_parser.add_argument(
        "--correction-mode",
        choices=("auto", "live", "delayed", "after-stop", "unavailable"),
        default="auto",
        help="when the corrected lane may run (default: auto)",
    )
    shared_app_parser.add_argument(
        "--backend-profile",
        type=Path,
        default=Path("results/backend-profile/backend-profile.json"),
        help="measured backend profile used by automatic correction mode",
    )
    shared_app_parser.add_argument(
        "--score-runtime",
        type=Path,
        default=Path("results/midi2score-runtime"),
        help="isolated MIDI2ScoreTransformer runtime directory",
    )
    _add_storage_arguments(shared_app_parser)
    _add_model_lifecycle_arguments(shared_app_parser)
    score_setup_parser = subparsers.add_parser(
        "setup-midi2score",
        help="install the internal MIDI2ScoreTransformer runtime",
    )
    score_setup_parser.add_argument(
        "--runtime",
        type=Path,
        default=Path("results/midi2score-runtime"),
        help="isolated runtime directory (default: results/midi2score-runtime)",
    )
    subparsers.add_parser(
        "devices",
        help="list audio devices available for microphone capture",
    )
    record_parser = subparsers.add_parser(
        "record",
        help="record a fixed-duration sample-clocked microphone input",
    )
    record_parser.add_argument("output_directory", type=Path)
    record_parser.add_argument("--seconds", type=float, default=20.0)
    record_parser.add_argument("--sample-rate", type=int, default=22_050)
    record_parser.add_argument("--block-samples", type=int, default=1024)
    record_parser.add_argument("--device")
    record_parser.add_argument(
        "--force",
        action="store_true",
        help="replace capture files in the target directory",
    )
    study_parser = subparsers.add_parser(
        "decoder-study",
        help="compare decoder policies over retained Basic Pitch output",
    )
    study_parser.add_argument("output_directory", type=Path)
    study_parser.add_argument(
        "cases",
        metavar="LABEL=RUN_DIRECTORY",
        nargs="+",
        help="labeled completed run with raw/basic_pitch.npz and input.wav",
    )
    migration_parser = subparsers.add_parser(
        "migration-regression",
        help="run and report the frozen product-migration regression lanes",
    )
    migration_parser.add_argument(
        "--output",
        type=Path,
        help="report path (default: timestamped path under results/)",
    )
    contracts_parser = subparsers.add_parser(
        "generate-contracts",
        help="generate the product OpenAPI document and TypeScript wire types",
    )
    contracts_parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when generated contracts have drifted",
    )
    users_parser = subparsers.add_parser(
        "users",
        help="manage basic local family accounts",
    )
    users_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("results/workbench-v3"),
        help="workspace owning the identity catalog",
    )
    user_commands = users_parser.add_subparsers(
        dest="users_command",
        required=True,
    )
    create_user_parser = user_commands.add_parser(
        "create",
        help="create a password account and local-workspace membership",
    )
    create_user_parser.add_argument("username")
    create_user_parser.add_argument("--display-name")
    create_user_parser.add_argument(
        "--role",
        choices=("owner", "editor", "viewer"),
        default="owner",
    )
    set_password_parser = user_commands.add_parser(
        "set-password",
        help="replace a password and revoke existing browser sessions",
    )
    set_password_parser.add_argument("username")
    disable_user_parser = user_commands.add_parser(
        "disable",
        help="disable an account and revoke existing browser sessions",
    )
    disable_user_parser.add_argument("username")
    enable_user_parser = user_commands.add_parser(
        "enable",
        help="enable an existing account",
    )
    enable_user_parser.add_argument("username")
    user_commands.add_parser(
        "list",
        help="list local-workspace accounts without password data",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from atpiano import __version__

        print(__version__)
        return 0
    if args.command == "fixture":
        from atpiano.fixture import generate_fixture

        manifest = generate_fixture(args.output_directory, force=args.force)
        print(args.output_directory / "input.json")
        print(f"audio sha256: {manifest['audio']['sha256']}")
        print(f"midi sha256:  {manifest['reference']['sha256']}")
        return 0
    if args.command == "musical-fixture":
        from atpiano.musical_fixture import generate_musical_fixture

        manifest = generate_musical_fixture(
            args.output_directory,
            force=args.force,
        )
        print(args.output_directory / "input.json")
        print(f"audio sha256: {manifest['audio']['sha256']}")
        print(f"midi sha256:  {manifest['reference']['sha256']}")
        return 0
    if args.command == "offline":
        from atpiano.offline import run_offline

        run_offline(
            args.input_manifest,
            args.run_directory,
            command=["atpiano", *sys.argv[1:]],
        )
        print(args.run_directory / "report.md")
        print(
            "onset F1 @ 50 ms: "
            f"{format_score(read_score(args.run_directory, 'onset', '50_ms', 'f1'))}"
        )
        return 0
    if args.command == "review":
        from atpiano.reviewer import serve_review

        serve_review(
            args.run_directory,
            bind=args.bind,
            port=args.port,
            open_browser=not args.no_open,
        )
        return 0
    if args.command == "workbench":
        from atpiano.workbench import serve_workbench

        serve_workbench(
            args.workspace,
            port=args.port,
            open_browser=not args.no_open,
        )
        return 0
    if args.command == "profile-backend":
        from atpiano.backend_profile import profile_backend

        profile = profile_backend(
            args.input_manifest,
            args.output_directory,
            device=args.commit_device,
            thread_limit=args.commit_threads,
            repeat=args.repeat,
            silence_s=args.silence_seconds,
            warmup_s=args.warmup_seconds,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
        )
        print(args.output_directory / "backend-profile.json")
        print(f"recommendation: {profile.recommendation.value}")
        print(f"service ratio: {profile.timing.service_ratio:.3f}")
        return 0
    if args.command == "validate-storage":
        from atpiano.storage_validation import (
            run_storage_validation,
        )

        evidence_path, evidence = run_storage_validation(
            args.input_manifest,
            args.workspace,
            minimum_hours=args.minimum_hours,
            minimum_free_bytes=round(
                args.minimum_free_gib * 1024**3
            ),
            timeout_s=args.timeout_seconds,
        )
        print(evidence_path)
        print(
            "source hours: "
            f"{evidence['source']['duration_s'] / 3600:.3f}"
        )
        print(
            "recording bytes/hour: "
            f"{evidence['measured_recording_bytes_per_hour']:.0f}"
        )
        return 0
    if args.command == "workbench-v2":
        from atpiano.corrected_workbench import serve_corrected_workbench

        serve_corrected_workbench(
            args.workspace,
            port=args.port,
            open_browser=not args.no_open,
            commit_device=args.commit_device,
            commit_threads=args.commit_threads,
            correction_mode=args.correction_mode,
            backend_profile_path=args.backend_profile,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
            model_idle_timeout_s=args.model_idle_timeout_seconds,
            replay_manifest=args.replay,
            replay_repeat=args.repeat,
            replay_silence_s=args.silence_seconds,
            replay_realtime=not args.no_wait,
            score_runtime=args.score_runtime,
            compact_recordings=args.compact_recordings,
            debug_retention=args.debug_retention,
            debug_byte_cap=round(
                args.debug_byte_cap_mib * 1024**2
            ),
            debug_max_age_s=(
                args.debug_max_age_hours * 60 * 60
            ),
        )
        return 0
    if args.command == "workbench-v3":
        from atpiano.corrected_workbench import serve_shared_application

        serve_shared_application(
            args.workspace,
            bind=args.bind,
            port=args.port,
            open_browser=not args.no_open,
            commit_device=args.commit_device,
            commit_threads=args.commit_threads,
            correction_mode=args.correction_mode,
            backend_profile_path=args.backend_profile,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
            model_idle_timeout_s=args.model_idle_timeout_seconds,
            replay_manifest=args.replay,
            replay_repeat=args.repeat,
            replay_silence_s=args.silence_seconds,
            replay_realtime=not args.no_wait,
            score_runtime=args.score_runtime,
            public_origin=args.public_origin,
            compact_recordings=args.compact_recordings,
            debug_retention=args.debug_retention,
            debug_byte_cap=round(
                args.debug_byte_cap_mib * 1024**2
            ),
            debug_max_age_s=(
                args.debug_max_age_hours * 60 * 60
            ),
        )
        return 0
    if args.command == "setup-midi2score":
        from atpiano.score_snapshot import setup_score_runtime

        manifest = setup_score_runtime(args.runtime)
        print(args.runtime / "runtime.json")
        print(f"repository: {manifest['repository']['commit']}")
        print(f"checkpoint: {manifest['checkpoint']['sha256']}")
        return 0
    if args.command == "devices":
        from atpiano.capture import list_input_devices

        print(list_input_devices())
        return 0
    if args.command == "record":
        from atpiano.capture import record_microphone

        device: int | str | None = args.device
        if isinstance(device, str) and device.isdecimal():
            device = int(device)
        manifest = record_microphone(
            args.output_directory,
            duration_s=args.seconds,
            sample_rate_hz=args.sample_rate,
            block_samples=args.block_samples,
            device=device,
            force=args.force,
        )
        print(args.output_directory / "input.json")
        print(f"audio sha256: {manifest['audio']['sha256']}")
        return 0
    if args.command == "replay":
        from atpiano.replay import run_replay

        run_replay(
            args.input_manifest,
            args.run_directory,
            realtime=not args.no_wait,
            block_samples=args.block_samples,
            command=["atpiano", *sys.argv[1:]],
        )
        print(args.run_directory / "report.md")
        print(
            "onset F1 @ 50 ms: "
            f"{format_score(read_score(args.run_directory, 'onset', '50_ms', 'f1'))}"
        )
        return 0
    if args.command == "replay-v2":
        from atpiano.corrected import run_corrected_replay

        preview_model = None
        if args.preview:
            from atpiano.live import BasicPitchLiveModel

            preview_model = BasicPitchLiveModel()
        commit_model = None
        if args.commit:
            from atpiano.corrected_commit import TranskunCommitModel

            commit_model = TranskunCommitModel(device=args.commit_device)
        manifest = run_corrected_replay(
            args.input_manifest,
            args.session_directory,
            repeat=args.repeat,
            silence_s=args.silence_seconds,
            realtime=not args.no_wait,
            block_samples=args.block_samples,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
            preview_model=preview_model,
            commit_model=commit_model,
        )
        print(args.session_directory / "session.json")
        print(f"source frames: {manifest['source_frame_count']}")
        return 0
    if args.command == "decoder-study":
        from atpiano.decoder_study import run_decoder_study

        cases = []
        for case in args.cases:
            label, separator, run_directory = case.partition("=")
            if not separator or not label or not run_directory:
                parser.error("decoder-study cases must use LABEL=RUN_DIRECTORY")
            cases.append((label, Path(run_directory)))
        run_decoder_study(args.output_directory, cases)
        print(args.output_directory / "report.md")
        print(args.output_directory / "decoder-study.json")
        return 0
    if args.command == "migration-regression":
        from atpiano.migration_regression import run_migration_regression

        output_path, report = run_migration_regression(args.output)
        print(output_path)
        print(f"migration regression: {report['status']}")
        return 0 if report["status"] == "passed" else 1
    if args.command == "generate-contracts":
        from atpiano.contracts.generation import generate_contracts

        outputs = generate_contracts(check=args.check)
        for output in outputs:
            print(output)
        return 0
    if args.command == "users":
        from atpiano.identity_cli import run_users_command

        return run_users_command(args)
    if not args.version:
        parser.print_help()
    return 0


def read_score(run_directory: Path, *keys: str) -> float | None:
    from atpiano.util import read_json

    value: object = read_json(run_directory / "scores.json")
    for key in keys:
        if not isinstance(value, dict):
            raise ValueError(f"score path {'/'.join(keys)} is not numeric")
        value = value[key]
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"score path {'/'.join(keys)} is not numeric")
    return float(value)


def format_score(value: float | None) -> str:
    return "not scored" if value is None else f"{value:.3f}"
