Gross World LoC is skyrocketing because of AI. By default, we have no way of knowing if what we're vibecoding does what we think it does. Secure program synthesis throws formal methods, proof assistants, type systems, model checkers, at all the code coming out of AI systems. Three days. Small teams. Real research output.

Top teams from this hackathon are invited to apply to the Secure Program Synthesis Fellowship (June-October 2026), where mentor-led teams take projects further with Apart Research project managers, compute, and API credits.

Organized by Apart Research and Atlas Computing
Top teams get
Invitation to the Secure Program Synthesis Fellowship
$2,000 in cash prizes across all tracks
🥇 1st Place
$1,000
🥈 2nd Place
$500
🥉 3rd Place
$300
🏅 4th Place
$100
🏅 5th Place
$100
What this hackathon is about
Three days to build a research artifact at the intersection of AI, formal methods, and security. The bottleneck in trustworthy software is no longer writing code, it's specifying what the code should actually do and verifying it does. We want sharp prototypes that move that needle.

The hackathon runs alongside the Secure Program Synthesis Fellowship. Strong teams here get invited to apply to the four-month Fellowship that starts in June, where you continue the work with a mentor, an Apart project manager, compute, and API credits.

Tracks
Same four focus areas as the Fellowship. Pick one and ship something concrete by Sunday.

1. Specification Elicitation
Tools that pull formal specifications out of ambiguous sources: documentation, legacy code, requirements docs, conversations with domain experts. Structured editors, GUIs, pipelines that translate informal intent into Lean (or similar).

Example projects:

A Coq/Lean spec drafting assistant that turns a natural-language requirement into a candidate spec, with reviewer tooling for the human in the loop.

An IDE extension that surfaces hidden assumptions in a legacy C codebase.

2. Specification Validation
Methods that check whether a candidate specification actually captures the system's intended behavior. Testing, cross-checking, mutation, formal validation.

Example projects:

Property-based fuzzing harness that flags specs which underconstrain or overconstrain the system.

Cross-model spec comparison: generate two spec candidates from different LLMs, surface where they disagree.

3. Spec-Driven Development & Evaluation (a.k.a. Vericoding)
Workflows where a spec generates multiple candidate implementations and ranks them. CEGIS-style loops, spec-conditioned codegen, automatic discrimination between implementations. This is sometimes called vericoding: formally verified program synthesis from specs.

Example projects:

An agent that generates N implementations from a spec and uses the spec as the evaluator.

Lean-backed test harness that catches semantic regressions LLM coders introduce.

4. Adversarial Robustness for ITPs and Proof Tools
Find the failure modes in interactive theorem provers (Lean, Coq, Isabelle, F*) and the LLM-assisted tools that build on them. The new frontier of adversarial robustness for ITPs: fuzzing kernels, defeating proof autocompleters, exploiting unsound automation. Not classical ML adversarial examples.

Example projects:

Adversarial inputs that defeat a state-of-the-art proof autocompleter.

Red-team study of an "AI as proof reviewer" pipeline, looking for whether the AI rubber-stamps wrong proofs.

Fuzz a Lean-verified library for runtime-level soundness gaps, in the style of Kiran Gopinathan's zlib bug (see Resources tab).

Who should join
Generalist software engineers with one or two deeper areas in any of: proof engineering (verified software preferred, but ITP math proofs work too), redteaming and fuzzing, SMT and model checking, secure systems design, or agent / ML evals work. If your expertise sits adjacent to this and you can spin up quickly, that's also a fit.

No formal methods background required to join, but expect to lean on teammates who have it.

What you will do
Friday May 22: Kickoff, track briefings, team formation.

Saturday May 23: Build.

Sunday May 24: Final pushes, submissions, demo.

What happens after
Top teams are invited to apply to the Secure Program Synthesis Fellowship, June-October 2026. The Fellowship pairs senior researchers (e.g. Erik Meijer, Mike Dodds) with small teams to take projects from prototype to research artifact, with compute, API credits, and demo-day travel funding.