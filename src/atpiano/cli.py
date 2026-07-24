"""Command-line entry point for atpiano."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        from atpiano import __version__

        print(__version__)
    return 0

