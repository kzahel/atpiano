"""Isolated MIDI2ScoreTransformer inference entry point.

This file is executed by the ignored Python 3.11 score runtime. Keep imports
from atpiano out of this module so the external environment only needs the
upstream model stack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input-midi", type=Path, required=True)
    parser.add_argument("--output-musicxml", type=Path, required=True)
    args = parser.parse_args()

    module_root = args.repository.resolve() / "midi2scoretransformer"
    if not module_root.is_dir():
        raise FileNotFoundError(f"MIDI2ScoreTransformer module directory is missing: {module_root}")
    for path in (args.checkpoint, args.input_midi):
        if not path.resolve().is_file():
            raise FileNotFoundError(path)
    sys.path.insert(0, str(module_root))

    import torch
    from config import MyModelConfig
    from models.roformer import Roformer
    from utils import quantize_path

    started = time.perf_counter()
    torch.serialization.add_safe_globals([MyModelConfig])
    model = Roformer.load_from_checkpoint(
        str(args.checkpoint.resolve()),
        map_location="cpu",
        weights_only=False,
    )
    model.to("cpu")
    model.eval()
    score = quantize_path(
        str(args.input_midi.resolve()),
        model,
        overlap=64,
        chunk=512,
        kv_cache=True,
        verbose=False,
    )
    output_path = args.output_musicxml.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(output_path))
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("MIDI2ScoreTransformer produced empty MusicXML")
    print(
        json.dumps(
            {
                "schema_version": "atpiano.midi2score-adapter.v1",
                "device": "cpu",
                "elapsed_s": time.perf_counter() - started,
                "musicxml_bytes": output_path.stat().st_size,
                "musicxml_sha256": _sha256(output_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
