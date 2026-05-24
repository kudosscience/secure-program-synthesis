from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spspec.core import DEFAULT_MODELS, SAMPLES_PER_MODEL, TASKS, generate_live_samples, load_offline_sample


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate OpenAI spec samples or offline fixtures")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline fixtures")
    parser.add_argument("--live", action="store_true", help="Use live OpenAI calls")
    parser.add_argument("--samples-per-model", type=int, default=SAMPLES_PER_MODEL)
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    live = bool(args.live) and not args.offline

    if live:
        samples = generate_live_samples(models=tuple(args.models), samples_per_model=args.samples_per_model)
        payloads = [sample.__dict__ for sample in samples]
    else:
        payloads = []
        for task_id in TASKS:
            for model in args.models:
                for sample_index in range(1, args.samples_per_model + 1):
                    payloads.append(load_offline_sample(task_id, model, sample_index))

    raw_path = output_dir / "spec_samples.json"
    raw_path.write_text(json.dumps(payloads, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(payloads)} samples to {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
