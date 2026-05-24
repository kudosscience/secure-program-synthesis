# Secure Program Synthesis Hackathon Scaffold

This repository contains a self-contained implementation of the Track 2 plan:
cross-model spec comparison using two OpenAI models, Lean 4-centered canonicalization,
and executable counterexample search.

## What it does

- Generates three candidate Lean-oriented specs for each of three tasks.
- Supports live OpenAI calls or offline demo fixtures.
- Canonicalizes outputs into a structured spec record.
- Compares model outputs and finds concrete counterexamples.
- Renders a static HTML report and a simple PDF summary.

## Quick start

Run the offline end-to-end pipeline and generate all artifacts:

```bash
python -m spspec.pipeline --offline --output-dir artifacts/demo
```

Run the tests:

```bash
python -m unittest discover -s tests
```

Generate only model samples:

```bash
python scripts/generate_specs.py --offline --output-dir artifacts/samples
```

Normalize a raw sample file:

```bash
python scripts/normalize_to_lean.py --input artifacts/samples/spec_samples.json --output artifacts/samples/normalized.json
```

## Live OpenAI mode

Set `OPENAI_API_KEY` and run:

```bash
python -m spspec.pipeline --live --output-dir artifacts/live
```

The live mode uses the Chat Completions API directly via `urllib`, so no OpenAI SDK dependency is required.

## Outputs

- `spec_samples.json`: raw samples.
- `normalized_samples.json`: canonical spec records.
- `results.json`: comparison and counterexample summary.
- `report.html`: static HTML report.
- `report.pdf`: compact PDF summary.
