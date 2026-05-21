# Decision Log

## D-001: Tooling stack — uv + Ruff + mypy --strict + pytest

**Context.** Day 1 of Week 1. Picking the Python tooling stack I'll live in for 11 weeks. The project has pinned contracts (`src/schema.py`, `src/prompts.py`) that training and inference both depend on, so drift between them silently breaks runs. Installs need to be reproducible across my 4070 box and Modal A100. Iteration speed matters because most weeks I have ~14 hours and any minute spent fighting tooling is a minute not spent on eval rigor.

**Options considered.**
- conda + pip + flake8 + black + isort + mypy. What I'd default to two years ago. Slow installs, painful lockfiles, four linters to keep in sync.
- poetry + Ruff + mypy + pytest. Modern, solid, lockfile works. But uv is meaningfully faster on resolve and install, and the ergonomics around `uv run` and `uv tool` are better for the script-heavy phases (Weeks 3–5).
- uv + Ruff + mypy --strict + pytest. Picked.

**Decision.** uv + Ruff + mypy --strict + pytest.

**Why.**
- Speed. uv is 10–100× faster than pip on cold and warm installs. Ruff replaces flake8 + black + isort + several pyupgrade-style checks in one binary that runs in milliseconds. Over 11 weeks this compounds.
- Reproducibility. `uv.lock` is the single source of truth and works the same on my 4070 box and on Modal. No conda channel resolution surprises mid-training.
- Type safety where it matters. `mypy --strict` on `src/` catches the class of bug that costs a training run — a Pydantic field renamed in one place and not the other, an Optional that silently swallows None. Tests and scripts run with looser typing, which is the right tradeoff.
- One toolchain to learn. Ruff + mypy + pytest is what the rest of the modern Python ecosystem is converging on, so anything I learn here is transferable.

**What would change this.** A critical dependency (vLLM, TRL, AutoAWQ, xgrammar) shipping conda-only with no working pip wheel for my CUDA. Or uv's resolver hitting a bug on a transitive dependency I can't pin around — at which point I'd fall back to pip + a hand-maintained `requirements.txt` rather than reach for poetry. Or Pydantic v3 landing during the project and breaking `mypy --strict` in a way that costs more than a few hours to patch.

## D-002: Enums over strings for severity / primary_category / suggested_action

**Context.** Week 1 Day 2. Designing `src/schema.py`, which is a pinned contract: training data, the FastAPI service, the eval scripts, and the Week 11 demo dashboard all read these fields. Three categorical Judgment fields need a representation: `Severity`, `PrimaryCategory`, `SuggestedAction`. The choice is small in code but compounds across the project.

**Options considered.**
- `Literal["low", "moderate", "high", "critical"]`. Zero imports, JSON-schemas cleanly to `string + enum`. But the Python side stays string-typed everywhere; mypy doesn't catch a typo'd `"criticla"`, the IDE can't autocomplete valid values, and there's no obvious home for helpers like a severity ordering when Week 9 needs it.
- Raw `str` + a `@field_validator`. Maximally flexible, accepts synonyms. But pushes the contract out of the type system and into runtime code — the opposite of what a pinned contract should do.
- `StrEnum` (Python 3.11+). Explicit class, mypy and the IDE know every valid member, JSON-serializes to the bare string so the on-wire format is identical to Literal.

**Decision.** `StrEnum` for `Severity`, `PrimaryCategory`, `SuggestedAction`, plus `Regime` and `ContentRegime`.

**Why.**
- Refactor safety. Renaming `harassment` → `personal_attack` updates every call site under mypy. Strings drift.
- Static catch. `Severity.critic` is a type error at edit time; `"critic"` is a runtime mismatch or, worse, a silent bug if downstream code uses `in` checks.
- Same JSON wire format as Literal — guided decoding in Week 6 sees the same `{"type": "string", "enum": [...]}` either way, so there's no latency or correctness tax.
- Natural place to hang helpers later — `Severity.ordering()` for calibration plots, `SuggestedAction.is_terminal()` for the dashboard.

**What would change this.** Pydantic v2's `model_json_schema()` emits enums via `$defs`/`$ref`. If the Week 6 guided-decoding backend (xgrammar via vLLM) mishandles refs on a Qwen-tuned grammar, I'd dereference the schema at export time before reaching for Literal — the in-Python representation stays as enums regardless.

## D-003: RuleId as `^R\d{1,3}$`

**Context.** `Judgment.violated_rules` has to point back at specific entries in `RuleSet.rules`. The model emits these references in every judgment, training data is built around them, and the dashboard's per-rule slice in Week 11 reads them. The question is what shape the reference takes.

**Options considered.**
- Free text — the model quotes the rule it thinks was violated. Easy for the model to emit, unparseable downstream. Forces fuzzy matching to recover the rule.
- Integer index into `rules[]`. Compact, but tightly coupled to rule ordering. Reordering a rule set silently invalidates every Judgment that references it.
- Structured ID like `R1`, `R23`, validated by regex. Stable across reorderings, parseable, short enough that the model emits it without burning output budget.

**Decision.** `RuleId = Annotated[str, StringConstraints(pattern=r"^R\d{1,3}$")]`, used in both `Rule.id` and `Judgment.violated_rules`.

**Why.**
- Stability. R8 inserted between R7 and R9 doesn't invalidate any prior judgment that referenced R8 in an earlier rule set version.
- Validated at the schema boundary. Malformed IDs (`"rule 1"`, `"R007a"`, `"R1234"`) raise at construction time — neither training data nor model output sneaks them past.
- 1–3 digits caps a rule set at 999 rules, well above the schema's 3–20 bound. Headroom without being unbounded.
- Tokenizes cheaply. `R1`, `R23` are 1–2 tokens; the model spends almost nothing on rule references, leaving budget for evidence and reasoning.
- Reads naturally in eval slices ("R3 precision on rule set X = 0.84").

**What would change this.** If Week 8 eval shows cross-rule-set ID confusion (model emits R3 from rule set A while looking at rule set B), I'd namespace as `<ruleset-slug>:R3`. That's a schema change requiring retraining, so I'd want hard evidence first.

## D-004: Length caps on `evidence_spans` (5 × 300) and `reasoning` (400)

**Context.** Week 7 is the latency budget exercise — chat p95 ~300ms on the 4070, ~80ms projected on A100. Under AWQ INT4 + vLLM, output token count is the dominant variable. The Judgment schema has two free-text fields the model can run away with: `evidence_spans` (quoted excerpts) and `reasoning` (free-form explanation). Unbounded, either one can blow the budget on a single verbose generation.

**Options considered.**
- No caps. Easiest to author. But a 1200-char reasoning string is ~300 output tokens, which alone is roughly the entire chat-regime decode budget.
- Soft caps via prompt instruction only. Brittle — SFT data with occasional long examples will pull the model long.
- Hard caps in the schema, enforced at validation time (rejects bad training data) and at inference time (via guided decoding's grammar bounds).

**Decision.** `evidence_spans`: max 5 entries, each 1–300 chars. `reasoning`: 1–400 chars. Both via `StringConstraints` and `Field(max_length=...)`.

**Why.**
- Worst-case output is bounded: `5 × ~75 tokens + ~100 tokens + JSON scaffold ≈ 550 tokens`. That sits comfortably inside the chat-regime budget on the 4070.
- Forces the SFT data to model concise judgments. We are explicitly not training a chain-of-thought reasoner — the model's job is to decide and cite, not to deliberate at length.
- Train/serve contracts align. The grammar enforces at inference what the schema enforces at training; no drift.
- Easy to relax (raise the cap, retrain). Hard to retrofit (every existing Judgment would need re-validation or regeneration).

**What would change this.** If Week 7 measurements show a class of legitimate violations whose evidence span genuinely exceeds 300 chars (e.g., a single quoted message of slurs longer than that), I'd raise the per-span cap and re-baseline. The first-pass policy is "constrain hard, relax with evidence in hand."

## D-005: `confidence` as a single float, not per-rule

**Context.** Each Judgment can violate multiple rules. The schema could expose confidence per rule (`[{rule: R1, confidence: 0.87}, {rule: R3, confidence: 0.42}]`) or as a single top-level scalar for the whole judgment. Week 9 is the calibration week (temperature scaling, isotonic regression on the held-out set), so the choice has downstream consequences I want to think about now.

**Options considered.**
- Per-rule confidence. Maximally informative — surfaces "high confidence on R1, low on R3, both flagged." Lets the dashboard show graded risk per rule. But calibration fragments into one curve per rule with sparse training signal each, the schema gains a parallel structure, and the output token cost rises meaningfully.
- Single top-level `confidence: float in [0, 1]`. One scalar, calibrated once against the binary `violates_policy` target. Simpler eval, simpler training signal, smaller wire format.
- Both. Overkill for v1.

**Decision.** Single top-level `confidence: float`, range `[0.0, 1.0]`.

**Why.**
- Calibration is one curve, not 20. The supervised signal is binary at the Judgment level; a single scalar is what that signal naturally exposes.
- Token budget. One float instead of a parallel structure saves ~30 output tokens, which matters at the Week 7 latency margins.
- Downstream consumers (FastAPI service, dashboard, eval scripts) care about a single "should we act on this?" signal in v1. Per-rule granularity is a nice-to-have that doesn't pay rent yet.
- Trade-off, documented: the demo can't natively show per-rule confidence. If the Week 11 dashboard story demands it, I'll derive it from a second forward pass or a small per-rule head — not by changing the pinned schema.

**What would change this.** If Week 9 calibration reveals that one global confidence hides systematically different reliability across categories (e.g., well-calibrated on harassment, overconfident on hate_speech), I'd consider per-category confidence — 8 floats, still tractable, still one calibration step per category. Per-rule remains the wrong granularity unless we see specifically per-rule failures.

## D-006: YAML over JSON for rule sets on disk

**Context.** Week 1 Day 3-4. The five seed rule sets just landed and the validator that loads them through `RuleSet.model_validate(...)` is wired into CI. The container format was a real choice: `data/rule_sets/*.yaml` vs `data/rule_sets/*.json`. Same Pydantic model on either side; the question is what humans see when they open the file. Over 11 weeks I expect to author or revise on the order of 20-30 rule sets — the 5 seeds, plus iteration during DPO pair generation in Week 4, plus late additions when calibration in Week 9 surfaces gaps.

**Options considered.**
- JSON. The model emits it, the FastAPI service speaks it, and `data/judgment_schema.json` is JSON. One format would have a tidy uniformity. But multi-line rule text requires `\n` escapes, which destroys the visual scanability hand-authored rules depend on, and comments aren't part of the spec — a draft like `// TODO: tighten R3` can't survive in the file.
- TOML. Comments survive, but multi-line strings need triple quotes that fight with the embedded quotes inside rule bodies (`"trash"`, `"noob"`, `"frick"` show up all over the seed catalog).
- YAML. Folded scalars (`>-`) collapse newlines into spaces while preserving paragraph-style authoring, comments live inline next to the rules they qualify, and YAML's whitespace structure mirrors the conceptual structure of a rule set (header → list of rules) better than JSON's brackets-and-commas.

**Decision.** YAML for rule sets on disk; JSON for everything the model emits or the API speaks.

**Why.**
- Authoring ergonomics where it actually matters. Rule sets are the one artifact in the project I will hand-edit dozens of times. Anything that costs 5-10 seconds per edit compounds across hundreds of edits.
- Comments survive. I can scribble `# loosened after Week 4 DPO pass` next to R7 without inventing a parallel metadata file. JSON can't carry that.
- Schema enforcement is identical either way. `yaml.safe_load(...)` and `json.loads(...)` both feed `RuleSet.model_validate(...)`; the YAML choice doesn't loosen a single constraint.
- The wire format stays JSON. Guided decoding in Week 6 sees `data/judgment_schema.json`; the FastAPI endpoint accepts and returns JSON; eval scripts emit JSONL. YAML is contained to author-time.
- Folded scalars let multi-line rule text read like English while still fitting the validated `ShortText` cap (300 chars per rule) — the line breaks are presentation, not content.

**What would change this.** If Week 3 training-data generation needs rule sets as JSON in a hot loop and `yaml.safe_load` cost shows up in profiles (it's ~10× slower than `json.loads`), I'd cache a `*.compiled.json` next to each YAML and treat the YAML as authoring source of truth. Same model on both sides; only the on-disk artifact layer changes.

## D-007: 5-rule-set seed catalog spans strictness deliberately, not cosmetically

**Context.** Week 1 Day 3-4. The seed catalog needed a size and a shape. The temptation was to pick five "reasonable" rule sets in the spirit of a default content-policy template — the kind of thing a generic moderation API ships with. I deliberately didn't. The whole pitch of this project is that the model attends to the rule-set text instead of falling back to a learned global threshold, and the catalog has to make that attention non-optional from the first SFT step.

**Options considered.**
- Default-strictness catalog. A flat set of "reasonable" rule sets centered on the same baseline. Easy to author, fast to eval. But it lets the model learn "violation = content above some global obscenity threshold" with rule-set text as decoration around the baseline — exactly the failure mode this project exists to defeat.
- Procedurally generated rule sets at training time. Defer hand-curation; let the Week 2 curriculum generator invent rule sets. Cheap variety, but no grounding in real deployment regimes and no human ground truth to sanity-check the model's judgments against. Variety is easy; realism is hard.
- Hand-written catalog spanning structural disagreement. Five rule sets that yield opposite judgments on identical content. `dating_dm` allows consensual sexual content between matched users; `kids_learning_chat` flags any romantic reference. `progamer_chat` allows "you're trash at this game"; `kids_learning_chat` flags it. `news_comments` permits sharply worded political speech; `niche_subreddit` flags political tangents as off-topic.

**Decision.** Hand-written catalog of five rule sets, chosen so the gradient is structural rather than cosmetic. Shape:

| Set | Profanity | Trash talk | Sexual content | Lowest violation bar |
|---|---|---|---|---|
| progamer_chat | allowed | allowed | prohibited | doxxing, slurs |
| kids_learning_chat | prohibited (incl. mild) | prohibited | prohibited | mild insults, off-platform contact |
| news_comments | allowed | political ok / personal no | prohibited | personal attacks on commenters |
| niche_subreddit | not addressed | allowed in critique | prohibited | off-topic, low-effort |
| dating_dm | allowed | n/a | allowed between matches w/ consent | unsolicited explicit, post-rejection |

**Why.**
- Defends against a default-strictness prior. SFT loss on a flat catalog teaches the *content distribution* of violations; loss on a structurally diverse catalog forces the model to attend to rule-set text to disambiguate. Cross-rule-set eval in Week 8 will tell us whether the diversity was sufficient, but no training-time trick can rescue a catalog that doesn't span the space in the first place.
- Every `primary_category` in the schema lands on opposite labels somewhere in the catalog. `sexual` is prohibited in four sets and allowed in dating_dm; `harassment` is calibrated differently in every set (mild banter ok in progamer, mild insult is a violation in kids). The model sees the same category map to opposite judgments depending on context — the exact signal the fine-tune is supposed to learn.
- Mirrors realistic deployment targets. Each rule set corresponds to a moderation regime an actual platform runs. The pitch (5-20× faster, 30-100× cheaper, rule-set-flexible) lives or dies on whether the catalog reflects scenarios a real customer would buy against.
- Five, deliberately. Each rule set generates ~200-600 SFT pairs in Week 3; ten dilutes per-set signal and inflates the eval matrix (5 × evaluators × calibration slices is already non-trivial). Five buys density per set while keeping eval tractable.

**What would change this.** If Week 8 cross-rule-set eval shows the model collapses to a learned default on novel rule sets it didn't see in training, the seed catalog is too narrow — I'd add 2-3 adjacent rule sets, or introduce procedurally generated rule sets at training time to force generalization. If the opposite — model overfits per-rule-set tokens and fails to transfer — the catalog is too disjoint, and I'd add a "shared backbone" of rules (no slurs, no doxxing) inherited across sets so identical sub-policies appear in different surface contexts.

## Week 1 reflection — audit findings

Day 6–7 surprise: how rarely Perspective's high-toxicity scores actually fire a `progamer_chat` rule. Across 50 stratified Civil Comments candidates (identity_attack ≥ 0.4, threat ≥ 0.4, sexual_explicit ≥ 0.4, plus tox-banded fillers), exactly one row violated — *"mental midgets"* under R2. The other 49 were political invective, hyperbolic post-loss rage, and idioms using sexual or violent vocabulary, all sliding under R2's slur-specific and R4's credible-threat-specific bars exactly as written. The rule set behaves correctly on that distribution; Civil Comments alone, under `progamer_chat`, doesn't exercise it enough to function as gold eval.

Two structural breaks worth surfacing for Week 3 Day 1:

1. **R6 is not single-message-evaluable.** Coordinated (3+ users in 10 min) and sustained (continuing past a "stop" request) both require conversation context that `Content` doesn't carry. Either `Content.prior_context: list[str]` lands as a pinned-contract change (retrain) or R6 detection scopes to a separate context-aware corpus and the model card caveats it.
2. **R2 narrowness.** Bigoted generalizations without slur words (*"Stupid races"*), etymological slurs that drifted (*"buggers"*), self-censored slur references (*"b\*\*\*h"*), and body-shaming (*"Fatchicks"*) all need explicit rule-text decisions before training. Same with R4 on violent rhetoric without real-world referent (*"stuff and roast it"* against a political category).

Adversarial replacement sketched in `docs/adversarial_progamer_chat_v0.md`. Week 3 sourcing pivots from uniform CC shuffle to ToxicChat + handcrafted adversarial set; CC stays only as a ≤20% benign-baseline contributor.

_Drafted by Claude 2026-05-21 from the Day 6–7 audit pair-session, then approved by the author. Revise for voice before this is cited in model_card.md (Week 10) or the blog post (Week 11)._
