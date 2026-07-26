"""Command-line entry point for atpiano."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path


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
        "--score-runtime",
        type=Path,
        default=Path("results/midi2score-runtime"),
        help="isolated MIDI2ScoreTransformer runtime directory",
    )
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
    shared_app_parser.add_argument("--port", type=int, default=8002)
    shared_app_parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the shared application in the default browser",
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
        "--score-runtime",
        type=Path,
        default=Path("results/midi2score-runtime"),
        help="isolated MIDI2ScoreTransformer runtime directory",
    )
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
    if args.command == "workbench-v2":
        from atpiano.corrected_workbench import serve_corrected_workbench

        serve_corrected_workbench(
            args.workspace,
            port=args.port,
            open_browser=not args.no_open,
            commit_device=args.commit_device,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
            replay_manifest=args.replay,
            replay_repeat=args.repeat,
            replay_silence_s=args.silence_seconds,
            replay_realtime=not args.no_wait,
            score_runtime=args.score_runtime,
        )
        return 0
    if args.command == "workbench-v3":
        from atpiano.corrected_workbench import serve_shared_application

        serve_shared_application(
            args.workspace,
            port=args.port,
            open_browser=not args.no_open,
            commit_device=args.commit_device,
            minimum_free_bytes=round(args.minimum_free_gib * 1024**3),
            replay_manifest=args.replay,
            replay_repeat=args.repeat,
            replay_silence_s=args.silence_seconds,
            replay_realtime=not args.no_wait,
            score_runtime=args.score_runtime,
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
