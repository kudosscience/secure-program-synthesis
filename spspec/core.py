from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from string import Template
from typing import Any, Callable


MODEL_A = "gpt-4o"
MODEL_B = "gpt-" + "3.5" + "-turbo"
DEFAULT_MODELS = (MODEL_A, MODEL_B)
SAMPLES_PER_MODEL = 3


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    title: str
    description: str
    question: str
    semantic_axis: str
    allowed_modes: tuple[str, str]
    witness_description: str


@dataclass
class SpecSample:
    task_id: str
    task_title: str
    model: str
    sample_index: int
    raw_text: str
    lean: str
    assumptions: list[str]
    preconditions: list[str]
    postconditions: list[str]
    invariants: list[str]
    examples: list[str]
    notes: list[str]
    semantic_mode: str


@dataclass
class Counterexample:
    task_id: str
    description: str
    witness: dict[str, Any]
    left_accepts: bool
    right_accepts: bool
    explanation: str


@dataclass
class Disagreement:
    task_id: str
    left_model: str
    left_index: int
    right_model: str
    right_index: int
    left_mode: str
    right_mode: str
    diff_summary: dict[str, Any]
    score: int
    counterexample: Counterexample | None


TASKS: dict[str, TaskDefinition] = {
    "sortedness": TaskDefinition(
        task_id="sortedness",
        title="Sortedness Property",
        description="Validate whether a candidate sorting specification is stable and permutation preserving.",
        question="What must a sorting specification guarantee about order, equality, and duplicates?",
        semantic_axis="stable_vs_unstable",
        allowed_modes=("stable", "unstable"),
        witness_description="A labeled duplicate pair that distinguishes stable order from mere value sorting.",
    ),
    "rate_limiter": TaskDefinition(
        task_id="rate_limiter",
        title="Token-Bucket Rate Limiter",
        description="Validate whether refill is applied before or after a request at the same timestamp boundary.",
        question="How should a token bucket behave when refill and consume happen at the same instant?",
        semantic_axis="refill_first_vs_consume_first",
        allowed_modes=("refill_first", "consume_first"),
        witness_description="A boundary-timestamp request that is accepted only if refill happens first.",
    ),
    "token_expiry": TaskDefinition(
        task_id="token_expiry",
        title="Token Expiry Semantics",
        description="Validate whether a token is valid exactly at the expiry timestamp.",
        question="Should token expiry be inclusive or exclusive at the boundary?",
        semantic_axis="inclusive_vs_exclusive",
        allowed_modes=("inclusive", "exclusive"),
        witness_description="A timestamp exactly equal to expiry that one spec accepts and the other rejects.",
    ),
}


FIXTURE_MODES: dict[str, dict[str, list[str]]] = {
    "sortedness": {
        MODEL_A: ["stable", "stable", "unstable"],
        MODEL_B: ["unstable", "stable", "unstable"],
    },
    "rate_limiter": {
        MODEL_A: ["refill_first", "refill_first", "consume_first"],
        MODEL_B: ["consume_first", "refill_first", "consume_first"],
    },
    "token_expiry": {
        MODEL_A: ["inclusive", "inclusive", "exclusive"],
        MODEL_B: ["exclusive", "inclusive", "exclusive"],
    },
}


def get_task(task_id: str) -> TaskDefinition:
    try:
        return TASKS[task_id]
    except KeyError as exc:
        raise KeyError(f"Unknown task: {task_id}") from exc


def build_prompt(task: TaskDefinition, sample_index: int) -> tuple[str, str]:
    system_prompt = (
        "You write Lean 4-centered specification candidates for a validation benchmark. "
        "Return JSON only, with keys lean, assumptions, preconditions, postconditions, invariants, examples, notes. "
        "Keep each field short and concrete. Do not add prose outside the JSON object."
    )
    user_prompt = textwrap.dedent(
        f"""
        Task: {task.title}
        Description: {task.description}
        Question: {task.question}

        Produce one candidate specification in JSON only.
        Required fields:
        - semantic_mode: one of {task.allowed_modes[0]} or {task.allowed_modes[1]}
        - lean: Lean 4 style spec fragment or theorem statement
        - assumptions: list of assumptions
        - preconditions: list of preconditions
        - postconditions: list of postconditions
        - invariants: list of invariants
        - examples: list of small examples
        - notes: list of short notes

        Make the candidate explicitly choose one semantic interpretation.
        Sample index: {sample_index}
        """
    ).strip()
    return system_prompt, user_prompt


def build_fixture(task_id: str, model: str, sample_index: int, mode: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task_id == "sortedness":
        if mode == "stable":
            lean = "def SortedSpec : Prop := \n  forall xs ys, SortedOutput xs ys -> Nondecreasing ys ∧ Permutation xs ys ∧ StableEqualOrder xs ys"
            postconditions = ["output is nondecreasing", "output is a permutation", "equal elements keep their input order"]
            examples = ["[(1,'a'), (1,'b')] -> [(1,'a'), (1,'b')]", "duplicates preserve order"]
            notes = ["stable sorting interpretation"]
        else:
            lean = "def SortedSpec : Prop := \n  forall xs ys, SortedOutput xs ys -> Nondecreasing ys ∧ Permutation xs ys"
            postconditions = ["output is nondecreasing", "output is a permutation"]
            examples = ["[(1,'a'), (1,'b')] -> [(1,'b'), (1,'a')]", "stability not required"]
            notes = ["unstable sorting interpretation"]
        assumptions = ["elements are comparable", "values may repeat"]
        preconditions = ["input is a finite list"]
        invariants = ["multiset preserved"]
    elif task_id == "rate_limiter":
        if mode == "refill_first":
            lean = "def RateLimitSpec : Prop := \n  refillBeforeConsume = true"
            postconditions = ["refill is applied before the request decision", "boundary-time requests can become admissible after refill"]
            examples = ["capacity 1, rate 1/s, t=1.0 -> accepted after refill"]
            notes = ["refill-before-consume interpretation"]
        else:
            lean = "def RateLimitSpec : Prop := \n  refillBeforeConsume = false"
            postconditions = ["consume is evaluated before refill at the same instant", "boundary-time requests can still be rejected"]
            examples = ["capacity 1, rate 1/s, t=1.0 -> rejected before refill"]
            notes = ["consume-before-refill interpretation"]
        assumptions = ["token bucket has finite capacity", "timestamps are monotonic"]
        preconditions = ["requests carry timestamps"]
        invariants = ["token count never exceeds capacity"]
    elif task_id == "token_expiry":
        if mode == "inclusive":
            lean = "def ExpirySpec : Prop := \n  isValid now expiry := now <= expiry"
            postconditions = ["a token is valid at the exact expiry instant", "boundary is inclusive"]
            examples = ["now = expiry -> accepted"]
            notes = ["inclusive expiry interpretation"]
        else:
            lean = "def ExpirySpec : Prop := \n  isValid now expiry := now < expiry"
            postconditions = ["a token is invalid at the exact expiry instant", "boundary is exclusive"]
            examples = ["now = expiry -> rejected"]
            notes = ["exclusive expiry interpretation"]
        assumptions = ["clock values are comparable", "revocation is out of scope"]
        preconditions = ["token has issue and expiry timestamps"]
        invariants = ["expiry does not move backwards"]
    else:
        raise KeyError(task_id)

    return {
        "task_id": task_id,
        "task_title": task.title,
        "model": model,
        "sample_index": sample_index,
        "semantic_mode": mode,
        "lean": lean,
        "assumptions": assumptions,
        "preconditions": preconditions,
        "postconditions": postconditions,
        "invariants": invariants,
        "examples": examples,
        "notes": notes,
    }


def load_offline_sample(task_id: str, model: str, sample_index: int) -> dict[str, Any]:
    mode = FIXTURE_MODES[task_id][model][sample_index - 1]
    return build_fixture(task_id, model, sample_index, mode)


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value).strip()]


def infer_semantic_mode(task_id: str, payload: dict[str, Any]) -> str:
    blob = " ".join(
        normalize_list(payload.get("lean"))
        + normalize_list(payload.get("assumptions"))
        + normalize_list(payload.get("preconditions"))
        + normalize_list(payload.get("postconditions"))
        + normalize_list(payload.get("invariants"))
        + normalize_list(payload.get("examples"))
        + normalize_list(payload.get("notes"))
    ).lower()

    if task_id == "sortedness":
        if "unstable" in blob or "stability not required" in blob or "stable sorting interpretation" in blob:
            return "unstable"
        if "stable" in blob or "relative order" in blob or "keep their input order" in blob:
            return "stable"
        return "unstable"
    if task_id == "rate_limiter":
        if "consume-before" in blob or "rejected before refill" in blob or "consume-before-refill" in blob:
            return "consume_first"
        if "refill-before" in blob or "refill is applied before" in blob or "accepted after refill" in blob:
            return "refill_first"
        return "consume_first"
    if task_id == "token_expiry":
        if "exclusive" in blob or "invalid at the exact expiry" in blob or "< expiry" in blob:
            return "exclusive"
        if "inclusive" in blob or "<= expiry" in blob or "valid at the exact expiry" in blob:
            return "inclusive"
        return "exclusive"
    raise KeyError(task_id)


def canonicalize_sample(task_id: str, model: str, sample_index: int, raw_text: str) -> SpecSample:
    payload = extract_json_object(raw_text)
    semantic_mode = str(payload.get("semantic_mode", "")).strip()
    if not semantic_mode:
        semantic_mode = infer_semantic_mode(task_id, payload)
    return SpecSample(
        task_id=task_id,
        task_title=str(payload.get("task_title", get_task(task_id).title)),
        model=model,
        sample_index=sample_index,
        raw_text=raw_text.strip(),
        lean=str(payload.get("lean", "")).strip(),
        assumptions=normalize_list(payload.get("assumptions")),
        preconditions=normalize_list(payload.get("preconditions")),
        postconditions=normalize_list(payload.get("postconditions")),
        invariants=normalize_list(payload.get("invariants")),
        examples=normalize_list(payload.get("examples")),
        notes=normalize_list(payload.get("notes")),
        semantic_mode=semantic_mode,
    )


def sample_to_dict(sample: SpecSample) -> dict[str, Any]:
    return asdict(sample)


def compare_field_lists(left: list[str], right: list[str]) -> dict[str, list[str]]:
    left_set = {item.strip() for item in left}
    right_set = {item.strip() for item in right}
    return {
        "left_only": sorted(left_set - right_set),
        "right_only": sorted(right_set - left_set),
    }


def compare_samples(left: SpecSample, right: SpecSample) -> dict[str, Any]:
    diff_summary = {
        "assumptions": compare_field_lists(left.assumptions, right.assumptions),
        "preconditions": compare_field_lists(left.preconditions, right.preconditions),
        "postconditions": compare_field_lists(left.postconditions, right.postconditions),
        "invariants": compare_field_lists(left.invariants, right.invariants),
        "examples": compare_field_lists(left.examples, right.examples),
        "notes": compare_field_lists(left.notes, right.notes),
        "semantic_mode": {
            "left": left.semantic_mode,
            "right": right.semantic_mode,
            "different": left.semantic_mode != right.semantic_mode,
        },
    }

    score = 0
    for field_name in ("assumptions", "preconditions", "postconditions", "invariants", "examples", "notes"):
        if diff_summary[field_name]["left_only"] or diff_summary[field_name]["right_only"]:
            score += 1
    if left.semantic_mode != right.semantic_mode:
        score += 4

    counterexample = search_counterexample(left, right)
    if counterexample is not None:
        score += 6

    return {
        "left": left,
        "right": right,
        "diff_summary": diff_summary,
        "score": score,
        "counterexample": counterexample,
    }


def search_counterexample(left: SpecSample, right: SpecSample) -> Counterexample | None:
    task_id = left.task_id
    if task_id != right.task_id:
        raise ValueError("Cannot compare samples from different tasks")

    if task_id == "sortedness":
        witness = {
            "input": [(1, "a"), (1, "b")],
            "candidate_output": [(1, "b"), (1, "a")],
        }
        left_accepts = accepts_sortedness(left.semantic_mode, witness)
        right_accepts = accepts_sortedness(right.semantic_mode, witness)
        if left_accepts != right_accepts:
            return Counterexample(
                task_id=task_id,
                description="A reordered duplicate pair distinguishes stable sorting from value-only sorting.",
                witness=witness,
                left_accepts=left_accepts,
                right_accepts=right_accepts,
                explanation="The unstable interpretation accepts the witness because the output is nondecreasing, while the stable interpretation rejects it because equal elements are reordered.",
            )

    if task_id == "rate_limiter":
        witness = {
            "capacity": 1,
            "refill_rate_per_second": 1,
            "events": [
                {"time": 0.0, "request": 1},
                {"time": 1.0, "request": 1},
            ],
            "boundary_decision": "accept_second_request",
        }
        left_accepts = accepts_rate_limiter(left.semantic_mode, witness)
        right_accepts = accepts_rate_limiter(right.semantic_mode, witness)
        if left_accepts != right_accepts:
            return Counterexample(
                task_id=task_id,
                description="A boundary-timestamp request distinguishes refill-before-consume from consume-before-refill.",
                witness=witness,
                left_accepts=left_accepts,
                right_accepts=right_accepts,
                explanation="The refill-first interpretation credits the refill before evaluating the second request, while the consume-first interpretation rejects it before refill is applied.",
            )

    if task_id == "token_expiry":
        witness = {
            "issue_time": 100,
            "expiry_time": 200,
            "now": 200,
        }
        left_accepts = accepts_token_expiry(left.semantic_mode, witness)
        right_accepts = accepts_token_expiry(right.semantic_mode, witness)
        if left_accepts != right_accepts:
            return Counterexample(
                task_id=task_id,
                description="A token checked exactly at expiry distinguishes inclusive from exclusive validity.",
                witness=witness,
                left_accepts=left_accepts,
                right_accepts=right_accepts,
                explanation="The inclusive interpretation accepts a token at the exact expiry instant, while the exclusive interpretation rejects it.",
            )

    return None


def accepts_sortedness(mode: str, witness: dict[str, Any]) -> bool:
    input_pairs = witness["input"]
    output_pairs = witness["candidate_output"]
    values = [value for value, _tag in output_pairs]
    nondecreasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    same_multiset = sorted(input_pairs) == sorted(output_pairs)
    if mode == "stable":
        if not (nondecreasing and same_multiset):
            return False
        input_order = [tag for value, tag in input_pairs if value == 1]
        output_order = [tag for value, tag in output_pairs if value == 1]
        return input_order == output_order
    return nondecreasing and same_multiset


def accepts_rate_limiter(mode: str, witness: dict[str, Any]) -> bool:
    if mode == "refill_first":
        return witness["boundary_decision"] == "accept_second_request"
    return witness["boundary_decision"] == "reject_second_request"


def accepts_token_expiry(mode: str, witness: dict[str, Any]) -> bool:
    now = witness["now"]
    expiry = witness["expiry_time"]
    if mode == "inclusive":
        return now <= expiry
    return now < expiry


def build_offline_samples(models: tuple[str, ...] = DEFAULT_MODELS, samples_per_model: int = SAMPLES_PER_MODEL) -> list[SpecSample]:
    samples: list[SpecSample] = []
    for task_id in TASKS:
        for model in models:
            for sample_index in range(1, samples_per_model + 1):
                payload = load_offline_sample(task_id, model, sample_index)
                raw_text = json.dumps(payload, indent=2, sort_keys=True)
                samples.append(canonicalize_sample(task_id, model, sample_index, raw_text))
    return samples


def call_openai_chat_completion(model: str, system_prompt: str, user_prompt: str, max_tokens: int = 450, temperature: float = 0.1) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.read().decode('utf-8', errors='replace')}") from exc

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI response did not contain choices")
    return choices[0]["message"]["content"]


def generate_live_samples(models: tuple[str, ...] = DEFAULT_MODELS, samples_per_model: int = SAMPLES_PER_MODEL) -> list[SpecSample]:
    samples: list[SpecSample] = []
    for task_id, task in TASKS.items():
        for model in models:
            for sample_index in range(1, samples_per_model + 1):
                system_prompt, user_prompt = build_prompt(task, sample_index)
                raw_text = call_openai_chat_completion(model, system_prompt, user_prompt)
                samples.append(canonicalize_sample(task_id, model, sample_index, raw_text))
    return samples


def select_task_disagreements(samples: list[SpecSample]) -> dict[str, Any]:
    by_task: dict[str, list[SpecSample]] = {task_id: [] for task_id in TASKS}
    for sample in samples:
        by_task[sample.task_id].append(sample)

    task_reports: list[dict[str, Any]] = []
    for task_id, task_samples in by_task.items():
        ordered_models = list(dict.fromkeys(sample.model for sample in task_samples))
        if len(ordered_models) < 2:
            raise ValueError(f"Need at least two models for task {task_id}")
        model_a = [sample for sample in task_samples if sample.model == ordered_models[0]]
        model_b = [sample for sample in task_samples if sample.model == ordered_models[1]]
        pair_reports: list[Disagreement] = []
        for left in model_a:
            for right in model_b:
                comparison = compare_samples(left, right)
                pair_reports.append(
                    Disagreement(
                        task_id=task_id,
                        left_model=left.model,
                        left_index=left.sample_index,
                        right_model=right.model,
                        right_index=right.sample_index,
                        left_mode=left.semantic_mode,
                        right_mode=right.semantic_mode,
                        diff_summary=comparison["diff_summary"],
                        score=comparison["score"],
                        counterexample=comparison["counterexample"],
                    )
                )

        pair_reports.sort(key=lambda item: item.score, reverse=True)
        best = pair_reports[0]
        task_reports.append(
            {
                "task_id": task_id,
                "task_title": get_task(task_id).title,
                "task_description": get_task(task_id).description,
                "samples": [sample_to_dict(sample) for sample in task_samples],
                "pair_reports": [disagreement_to_dict(report) for report in pair_reports],
                "best_pair": disagreement_to_dict(best),
            }
        )

    return {
        "tasks": task_reports,
        "sample_count": len(samples),
        "model_names": list(DEFAULT_MODELS),
    }


def disagreement_to_dict(disagreement: Disagreement) -> dict[str, Any]:
    return {
        "task_id": disagreement.task_id,
        "left_model": disagreement.left_model,
        "left_index": disagreement.left_index,
        "right_model": disagreement.right_model,
        "right_index": disagreement.right_index,
        "left_mode": disagreement.left_mode,
        "right_mode": disagreement.right_mode,
        "diff_summary": disagreement.diff_summary,
        "score": disagreement.score,
        "counterexample": None if disagreement.counterexample is None else asdict(disagreement.counterexample),
    }


def escape_html_lines(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def render_html_report(report: dict[str, Any], template_path: Path) -> str:
    template = Template(template_path.read_text(encoding="utf-8"))
    sections: list[str] = []
    summary_rows: list[str] = []
    for task in report["tasks"]:
        best = task["best_pair"]
        summary_rows.append(
            f"<tr><td>{html.escape(task['task_title'])}</td><td>{html.escape(str(best['left_model']))} vs {html.escape(str(best['right_model']))}</td><td>{best['score']}</td><td>{html.escape(str(best['left_mode']))} vs {html.escape(str(best['right_mode']))}</td></tr>"
        )

        sample_cards = []
        for sample in task["samples"]:
            sample_cards.append(
                f"""
                <div class=\"card\">
                  <h4>{html.escape(sample['model'])} sample {sample['sample_index']}</h4>
                  <p><strong>Semantic mode:</strong> {html.escape(sample['semantic_mode'])}</p>
                  <p><strong>Lean:</strong><br><code>{escape_html_lines(sample['lean'])}</code></p>
                  <p><strong>Assumptions:</strong> {html.escape(', '.join(sample['assumptions']))}</p>
                  <p><strong>Preconditions:</strong> {html.escape(', '.join(sample['preconditions']))}</p>
                  <p><strong>Postconditions:</strong> {html.escape(', '.join(sample['postconditions']))}</p>
                  <p><strong>Invariants:</strong> {html.escape(', '.join(sample['invariants']))}</p>
                  <p><strong>Examples:</strong> {html.escape(', '.join(sample['examples']))}</p>
                  <p><strong>Notes:</strong> {html.escape(', '.join(sample['notes']))}</p>
                </div>
                """
            )

        pair_rows = []
        for pair in task["pair_reports"][:6]:
            ce = pair["counterexample"]
            ce_text = "No counterexample" if ce is None else html.escape(ce["description"])
            pair_rows.append(
                f"<tr><td>{html.escape(pair['left_model'])} {pair['left_index']}</td><td>{html.escape(pair['right_model'])} {pair['right_index']}</td><td>{pair['score']}</td><td>{html.escape(pair['left_mode'])}</td><td>{html.escape(pair['right_mode'])}</td><td>{ce_text}</td></tr>"
            )

        counterexample = best["counterexample"]
        if counterexample is None:
            counterexample_html = "<p>No counterexample found.</p>"
        else:
            counterexample_html = f"""
            <pre>{html.escape(json.dumps(counterexample['witness'], indent=2))}</pre>
            <p><strong>Explanation:</strong> {html.escape(counterexample['explanation'])}</p>
            <p><strong>Accepted by left:</strong> {str(counterexample['left_accepts']).lower()} | <strong>Accepted by right:</strong> {str(counterexample['right_accepts']).lower()}</p>
            """

        sections.append(
            f"""
            <section class=\"task-section\">
              <h2>{html.escape(task['task_title'])}</h2>
              <p>{html.escape(task['task_description'])}</p>
              <div class=\"grid\">{''.join(sample_cards)}</div>
              <h3>Pairwise disagreement summary</h3>
              <table>
                <thead><tr><th>Left</th><th>Right</th><th>Score</th><th>Left mode</th><th>Right mode</th><th>Counterexample</th></tr></thead>
                <tbody>{''.join(pair_rows)}</tbody>
              </table>
              <h3>Best counterexample</h3>
              {counterexample_html}
            </section>
            """
        )

    html_output = template.safe_substitute(
        title="Cross-Model Spec Comparison",
        generated_at=report.get("generated_at", "unknown"),
        sample_count=report.get("sample_count", 0),
        summary_rows="".join(summary_rows),
        sections="".join(sections),
    )
    return html_output


def build_pdf_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "Cross-Model Spec Comparison",
        f"Generated: {report.get('generated_at', 'unknown')}",
        f"Samples: {report.get('sample_count', 0)}",
        "",
    ]
    for task in report["tasks"]:
        best = task["best_pair"]
        lines.extend(
            [
                f"Task: {task['task_title']}",
                f"Best pair: {best['left_model']} {best['left_index']} vs {best['right_model']} {best['right_index']}",
                f"Modes: {best['left_mode']} vs {best['right_mode']}",
                f"Score: {best['score']}",
            ]
        )
        ce = best["counterexample"]
        if ce is None:
            lines.append("Counterexample: none")
        else:
            lines.append(f"Counterexample: {ce['description']}")
            lines.append(json.dumps(ce['witness']))
        lines.append("")
    return lines


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_pdf(lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    margin_left = 72
    margin_top = 72
    line_height = 14
    lines_per_page = 44
    wrapped_lines: list[str] = []
    for line in lines:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(line, width=90) or [""])

    pages = [wrapped_lines[i : i + lines_per_page] for i in range(0, len(wrapped_lines), lines_per_page)] or [[""]]

    objects: list[str] = []
    objects.append("<< /Type /Catalog /Pages 3 0 R >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_object_numbers = list(range(4, 4 + len(pages)))
    content_object_numbers = list(range(4 + len(pages), 4 + len(pages) + len(pages)))
    kids = " ".join(f"{page_number} 0 R" for page_number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")

    for page_number, content_number in zip(page_object_numbers, content_object_numbers):
        objects.append(
            f"<< /Type /Page /Parent 3 0 R /MediaBox [0 0 {page_width} {page_height}] /Resources << /Font << /F1 2 0 R >> >> /Contents {content_number} 0 R >>"
        )

    for page_lines in pages:
        content_lines = ["BT", "/F1 12 Tf", f"{margin_left} {page_height - margin_top} Td"]
        first_line = True
        for line in page_lines:
            if first_line:
                content_lines.append(f"({escape_pdf_text(line)}) Tj")
                first_line = False
            else:
                content_lines.append(f"0 -{line_height} Td ({escape_pdf_text(line)}) Tj")
        content_lines.append("ET")
        content_stream = "\n".join(content_lines).encode("utf-8")
        objects.append(f"<< /Length {len(content_stream)} >>\nstream\n{content_stream.decode('utf-8')}\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    xref_positions = [0]
    for index, obj in enumerate(objects, start=1):
        xref_positions.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n{obj}\nendobj\n".encode("utf-8"))
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    pdf.extend(b"0000000000 65535 f \n")
    for position in xref_positions[1:]:
        pdf.extend(f"{position:010d} 00000 n \n".encode("utf-8"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("utf-8")
    )
    return bytes(pdf)


def write_report_artifacts(report: dict[str, Any], output_dir: Path, template_path: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "report.html"
    pdf_path = output_dir / "report.pdf"
    json_path = output_dir / "results.json"
    samples_path = output_dir / "spec_samples.json"
    normalized_path = output_dir / "normalized_samples.json"

    html_path.write_text(render_html_report(report, template_path), encoding="utf-8")
    pdf_path.write_bytes(build_simple_pdf(build_pdf_lines(report)))
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    samples_path.write_text(json.dumps(report.get("raw_samples", []), indent=2, sort_keys=True), encoding="utf-8")
    normalized_path.write_text(json.dumps(report.get("normalized_samples", []), indent=2, sort_keys=True), encoding="utf-8")

    return {
        "html": html_path,
        "pdf": pdf_path,
        "results": json_path,
        "raw_samples": samples_path,
        "normalized_samples": normalized_path,
    }


def run_pipeline(output_dir: Path, live: bool = False, models: tuple[str, ...] = DEFAULT_MODELS, samples_per_model: int = SAMPLES_PER_MODEL) -> dict[str, Any]:
    if live:
        samples = generate_live_samples(models=models, samples_per_model=samples_per_model)
        raw_samples = [sample_to_dict(sample) for sample in samples]
    else:
        raw_samples = []
        samples = []
        for task_id in TASKS:
            for model in models:
                for sample_index in range(1, samples_per_model + 1):
                    payload = load_offline_sample(task_id, model, sample_index)
                    raw_samples.append(payload)
                    raw_text = json.dumps(payload, indent=2, sort_keys=True)
                    samples.append(canonicalize_sample(task_id, model, sample_index, raw_text))

    comparison_report = select_task_disagreements(samples)
    normalized_samples = [sample_to_dict(sample) for sample in samples]
    report = {
        **comparison_report,
        "generated_at": _utc_now(),
        "normalized_samples": normalized_samples,
        "raw_samples": raw_samples,
    }
    template_path = Path(__file__).resolve().parent.parent / "viz" / "report.html"
    write_report_artifacts(report, output_dir, template_path)
    return report


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-model spec comparison pipeline")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Use live OpenAI API calls")
    parser.add_argument("--offline", action="store_true", help="Use deterministic offline fixtures")
    parser.add_argument("--samples-per-model", type=int, default=SAMPLES_PER_MODEL)
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    live = bool(args.live)
    if args.offline:
        live = False
    report = run_pipeline(
        output_dir=args.output_dir,
        live=live,
        models=tuple(args.models),
        samples_per_model=args.samples_per_model,
    )
    print(json.dumps({"tasks": len(report["tasks"]), "samples": report["sample_count"], "output_dir": str(args.output_dir)}, indent=2))
    return 0

