Worldview & background
"Secure Program Synthesis" (Quinn Dougherty, LessWrong sequence, 2026) - Seven-post sequence on the worldview behind this hackathon.

"How to Solve Secure Program Synthesis" (Max von Hippel, Simon Henniger, Quinn Dougherty, Evan Miyazono, LessWrong, March 2026) - The canonical statement of the SPS problem and what a solution looks like.

awesome-secure-program-synthesis (for-all.dev, maintained by Quinn Dougherty and Max von Hippel) - Curated companies, papers, repos, evals, and orgs in the SPS space.

"Specifications Don't Exist" (Mike Dodds, Galois, June 2025) - On why writing formal specifications is the bottleneck, not verification.

Per-track reading
Specification Elicitation
formal-specification-ide (Atlas Computing) - Reference IDE prototype for writing and reviewing mechanized specs alongside human-readable text.

Specification Validation
lean-tcb (OathTech, Apache 2.0) - Trusted computing base analyzer for Lean 4. Computes which definitions a human must review for a theorem to mean what it claims.

"On the Promises of 'High-Assurance' Cryptography" (Symbolic Software, Feb 2026) - Found four security vulnerabilities in Cryspen's formally verified libcrux. Sharp critique of "verified" claims.

Spec-Driven Development & Evaluation (a.k.a. Vericoding)
"Vericoding: A Benchmark for Formally Verified Program Synthesis" (arXiv 2509.22908, 2025) - Defines the vericoding benchmark for formally verified program synthesis from natural-language specs.

"Counterexample-guided Inductive Synthesis" (Remy Wang) - Approachable primer on CEGIS, the foundational technique for spec-driven program synthesis.

"Counterexample-guided Abstraction Refinement" (Clarke, Grumberg, Jha, Lu, Veith, CMU/Technion) - Foundational CEGAR paper, hosted as Stanford CS357 reading.

"Synthesizing Finite-state Protocols from Scenarios and Requirements" (Raghothaman et al., arXiv 1402.7150, Feb 2014) - Spec-driven synthesis from message sequence charts.

"Approximately Aligned Decoding" (Melcer et al., arXiv 2410.01103, Oct 2024) - Spec-conditioned LLM decoding that balances distribution distortion with computational efficiency.

"Zero-Degree-of-Freedom LLM Coding using Executable Oracles" (John Regehr, March 2026) - On collapsing the freedoms LLMs have to do bad work by surrounding them with executable oracles.

Adversarial Robustness for ITPs and Proof Tools
"Validating a Lean Proof" (Lean reference docs) - Escalating sequence of checks against benign mistakes and malicious proof attempts.

"Lean proved this program was correct; then I found a bug." (Kiran Gopinathan, April 2026) - Fuzzing a verified Lean implementation of zlib found a heap buffer overflow in the Lean runtime itself.

Tools
Lean 4 - Interactive theorem prover, the workhorse for many of these projects.

formal-specification-ide (Atlas Computing) - Reference spec IDE built around the Anthropic API.