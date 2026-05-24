from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spspec.core import canonicalize_sample


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize raw spec samples into canonical Lean-centered records")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payloads = json.loads(args.input.read_text(encoding="utf-8"))
    normalized = []
    for index, payload in enumerate(payloads, start=1):
        raw_text = json.dumps(payload, indent=2, sort_keys=True)
        normalized.append(canonicalize_sample(payload["task_id"], payload["model"], payload.get("sample_index", index), raw_text).__dict__)
    args.output.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(normalized)} normalized samples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
