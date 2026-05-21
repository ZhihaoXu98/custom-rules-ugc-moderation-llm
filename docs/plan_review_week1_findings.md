# Holistic plan review — propagating Week 1 findings across Weeks 1–11

**Drafted:** 2026-05-21 by Claude based on the audit work this week.
**Status:** review-only; no prompt files edited. You decide which to apply.

## Executive summary

Five Week-1 findings have ripple effects through the plan. In rough order of blast radius:

1. **Source-domain mismatch (Civil Comments × narrow rule-set text).** 49/50 of the stratified audit set came out `no_action` under `progamer_chat` because R2/R4 are narrowly worded (slur-words / credible-threat). CC contains plenty of insults and hyperbolic rhetoric but very few actual slur-words or referent-grounded threats. The same mismatch will hit Weeks 2–4: stratified-CC golden sampling will produce a flat distribution, derivation profiles will fire rarely on permissive rule sets, and SFT will train on a heavily-no_action distribution. **Counter-measure: switch primary chat-regime corpus from "uniform CC" to "ToxicChat + handcrafted adversarial + targeted CC slices." CC stays as comment-regime baseline.**

2. **R6 is not single-message-evaluable.** Coordinated/sustained harassment requires conversation context that `Content` doesn't carry. **A schema decision is owed** *before* Week 3 derivation profiles are designed: either (a) add `Content.prior_context: list[str] | None` as a pinned-contract change (retrain) or (b) explicitly scope R6 out of derivation/training and document the limit in the model card.

3. **Rule-set text is too narrow in spots.** R2 covers slur *words* not bigoted generalizations or body-shaming. R4 requires real-world referent. R6 requires patterns. Multiple Week-1 candidates surfaced these gaps (Stupid races / Fatchicks / Buggers / "stuff and roast it" / "head out of arse, weewili"). **Rule-set v2 owes explicit decisions on each gap** before training, otherwise training data will encode whatever the strict-letter reading happens to be.

4. **Adversarial slice scope (current plan: 50 hand-authored, Week 9).** Sketch in `docs/adversarial_progamer_chat_v0.md` argues for **~100 per rule set**, not 50 total. The cross-rule-set foils (same content, different judgments) are the highest-leverage demonstration of the Pareto pitch and should land earlier than Week 9.

5. **D-numbering collision.** Week 1 already has D-001..D-007 + the new "Week 1 reflection" entry. The reflection flagged a `prior_context` schema decision as **D-008 candidate**, but Week 2's plan already assigns D-008 to "Rubric is versioned." Either we slot the schema decision under Week 3 Day 1 (renumbered D-015a or similar), or every D-number from Week 2 onward shifts by 1.

The rest of this doc walks Weeks 1–11 noting what each week needs.

---

## Cross-cutting changes (touch multiple weeks)

### CC-1 · Schema decision on `prior_context` lands Week 3 Day 1

Before any derivation logic touches R6, the schema decision must be made. Two options:

- **Add `Content.prior_context: list[str] | None`** — pinned-contract change. Schema bumps; tests update; Week 3 derivation triggers can reference context. Cost: retrain Weeks 4+ if change comes later than Week 3 Day 1.
- **Scope R6 out** — derivation profiles in `data/rule_sets/*.yaml` don't define triggers for R6; training set won't contain R6-violation examples; model card explicitly disclaims R6 detection. Cost: a documented capability gap for an audit-time question.

Recommendation: **Option B (scope out)** because Week 1 schema is already locked, R6 detection isn't load-bearing for the Pareto pitch, and the docs/model_card.md "known limitations" section is the honest place for it. Document as D-014 (after Week 2's existing D-008..D-014) → keeps Week 2 numbering intact.

### CC-2 · Sourcing change: ToxicChat alongside CC for chat regime

Week 1 Day 5's data plan candidates list doesn't include **ToxicChat** (real chat conversations labeled for toxicity, ~10k examples — better distribution match for chat-regime rule sets than CC). Recommend adding it as the primary chat-regime corpus, with CC limited to comment-regime + small chat-regime baseline contributor (~20%).

Cascade to:

- **Week 1 Day 5** (`docs/data_plan.md`) — add ToxicChat to candidates table.
- **Week 3 Day 4** (chat-length synthesizer) — partially replaced by ToxicChat real data; less synth needed.
- **Week 3 Day 3** (cross-product) — pull from {CC for comment, ToxicChat for chat, synth as gap-filler}.

### CC-3 · Stratification: target rule-firing content explicitly

The current Week 2 Day 2 stratification (40 high-tox / 40 mid / 40 low-risk / 30 clean) yields too many cases where the rule set deliberately permits the content. Week 1's experiment showed identity_attack/threat/sexual_explicit bands are higher-leverage. Recommend Week 2 sampling adopt the structure used by `scripts/_sample_ai_baseline.py`:

```
identity_attack >= 0.4  → ~25 examples  (R2 firing zone)
threat          >= 0.4  → ~20 examples  (R4 firing zone)
sexual_explicit >= 0.4  → ~15 examples  (R5 firing zone)
toxicity        >= 0.7  → ~30 examples  (R1 permissive zone — for asymmetry)
mid_tox (0.3-0.7)       → ~30 examples  (boundary)
low_tox (<0.3)          → ~30 examples  (clean baseline)
```

Total: ~150 candidates. Maintains Week 2's size; biases toward content that actually exercises R1-R8.

### CC-4 · Adversarial slice scope, earlier and bigger

Current plan (Week 9): 50 hand-authored, all rule sets combined. Sketch recommends: ~100 per rule set (focus on the 5 hand-written seed rule sets; ~500 examples total). High-priority sub-slice — **cross-rule-set foils** (same content with multi-rule-set judgments) — earns its own bucket of ~20-30 examples per pair and is the most defensible demo of rule-set-conditional behavior.

Two ways to absorb this into the plan:

- **Stretch the adversarial work across Weeks 7-9** — small daily authoring sessions during latency/serving weeks where you're CPU-idle.
- **Cut adversarial to "per-rule-set" mini-sets and scope the slice analysis tighter** — 100 total but well-distributed across 5 seed rule sets, with the foils as the headline.

Recommendation: middle path — **~100 hand-authored examples (vs current 50), with 5 of those rule-sets each getting ~20**, plus ~20 cross-rule-set foils. Add an explicit Week 3 task: "build a starter set of 25 foils during Week 3 Day 7 buffer to start populating the adversarial corpus early."

### CC-5 · Rule-set v2 decisions before Week 3

Each of these is a one-sentence decision the rule maintainer (you) owes before Week 3 derivation profiles encode them as triggers:

- **R2 spirit-vs-letter:** does R2 cover bigoted generalizations without slur words ("Stupid races"), drifted etymological slurs ("buggers"), self-censored slurs ("b\*\*\*h")? If yes: rule text widens, derivation triggers widen, training data shifts. If no: model card disclaims, audit set won't flag these.
- **R2 body-shaming:** does R2's protected-class list cover body weight/appearance? Currently it doesn't (race/ethnicity/gender/sexual orientation/religion/disability). Decision needed before training data encodes a "no" position.
- **R4 hyperbolic vs spirit:** does R4 fire on violent rhetoric without real-world referent ("stuff and roast it" against a political category)? Strict letter says no; spirit could say yes.
- **R6 single-message:** does R6 ever fire on a single aggressive personal-targeting message ("head out of arse, weewili")? Strict says no; spirit might warn.
- **R5 mentions vs descriptions:** does R5 cover naming sex acts ("fellatio") in non-sexual context, or only "describing" them?

Each of these is a 2-3 sentence rule-text change in the rule-set YAML. Document as D-015 (early Week 3 Day 1) — *before* the derivation profile is designed.

---

## Per-week deltas

### README (`00-README.md`)

**Status:** mostly OK. Two nits:

- The "11-week arc" table (line 34) lists Week 9 as "Rigorous eval" with "50-example adversarial slice." If we expand to ~100, update this single number.
- The "Pareto position" framing assumes the model achieves F1 within 3 points of GPT-4o-mini. If Week 4 SFT plateaus lower than ~0.75 due to derivation noise, this number softens. Keep the framing as a *claim* (justified by Week 9 measurement); don't bake the number into Week-1 README.

### Week 1 (`01-week-01.md`)

**Status:** done. Deviations from plan worth noting in your reflection or a separate addendum:

- **Goal #8** (line 25): "50 hand-audited (content, rule_set, judgment) triples in `data/audit/week1.jsonl`." Reality: 50 in `data/audit/week1.human_approved.jsonl` (AI-drafted, human-reviewed) + a small handful in `week1.jsonl` from the interactive pair-audit. Worth noting in the deliverables checklist OR consolidating into one file as you choose.
- **Step 1.11 "Audit sessions across two days"** (line 380): plan was 4 sessions across 5 rule sets. Reality: I built a stratified sampler that targeted progamer_chat specifically (more useful diagnostic of rule-set-text narrowness than spreading thin). Week 3's derivation audit (the larger 100-example audit) is where multi-rule-set coverage genuinely matters.
- **Step 1.12 reflection**: landed. Mentions D-008 candidate for `prior_context`; recommend renaming reference to D-014 or D-015 to avoid collision with Week 2's D-008.
- **Step 1.9 data plan** (line 308): add ToxicChat to the candidate list and recommend it as primary chat-regime source.

### Week 2 (`02-week-02.md`)

**Status:** needs the most adjustment. Five changes:

- **Step 2.3 stratification (line 119):** replace the 40/40/40/30 bands with the rule-firing-targeted bucketing from CC-3 above. Same 150 total; better signal.
- **Step 2.1 rubric (line 62):** the rubric must explicitly address how to label R6 violations on single-message Content (likely: "R6 cannot fire on single-message audit examples; mark as `violates_policy=false` with a note in `reasoning`"). Otherwise three labelers will diverge on context-dependent rules.
- **Step 2.1 rubric for R2 spirit-vs-letter:** the rubric must commit to which reading (strict words-only or spirit-includes-generalizations) before the human labels 150 candidates. The decision should be made in CC-5 above and propagated.
- **D-008 conflict:** if you adopt CC-1 Option B and slot `prior_context` decision as D-014 (scope-R6-out), Week 2's existing D-008..D-014 sequence holds. If you adopt Option A (add `prior_context`), need to renumber Week 2's D-008..D-014 → D-009..D-015 and Week 1 reflection-block decisions → D-008.
- **Step 2.6 human labeling pacing (line 263):** plan assumes 20-30 per 30-min session. Week 1 reality was 8-12 per session (more like the realistic pacing in Week 3 Day 5 audit). Update expectations: 7 sessions across 3-4 days, not 5-7.

### Week 3 (`03-week-03.md`)

**Status:** highest concentration of changes. Seven substantive deltas:

- **Day 1 prerequisite (new):** schema decision on `prior_context` (CC-1) and rule-set v2 text decisions (CC-5) **must precede** Step 3.1. Add as Step 3.0 explicitly.
- **Step 3.1 derivation triggers (line 71):** if R6 is scoped out, derivation profiles must not contain R6 triggers. Note this explicitly so generated rule sets (Step 3.4) also skip R6 derivation.
- **Step 3.4 generated rule sets (line 154):** the 20 generated rule sets will probably include rules-needing-context (analogues of R6). The audit step (3.5) should reject or hand-tune these to fit the chosen R6 scope.
- **Step 3.7 cross-product source mix (line 232):** the current sampling stratification (35%/25%/25%/15% across toxicity bands of CC) carries the same flat-distribution issue. Replace with mix-from-multiple-sources: 50% ToxicChat (real chat-regime data, labeled for toxicity), 35% CC stratified per CC-3, 15% synth. Specifically for R2 firing: include slur-containing examples from ToxicChat's high-identity-attack subset which contains more actual slurs than CC's news comments.
- **Step 3.10 chat-length synthesizer (line 326):** ToxicChat covers this need partially. Keep the synthesizer for gap-filling (chat-style content matching specific derivation profiles) but expect to need less of it (~2k instead of ~5k).
- **Step 3.12 100-example derivation audit target (line 449):** the target ≥0.85 `violates_policy` agreement is at risk if CC-vs-rule-set mismatch propagates. Realistic outcome from CC-stratified sampling: ~0.75-0.85 on permissive rule sets, ~0.80-0.90 on strict. **Document the per-rule-set breakdown — averaging will hide rule-set-specific noise.**
- **D-numbering (D-015 through D-022, lines 28-30):** if you slot the rule-set v2 decisions and the schema scope-out under Week 3 Day 1, several new D-entries land here. Recommend renumbering Week 3 to D-016..D-024 (shifting Week 3's existing 8 entries down by 1) to make room for D-015 ("R6 scope decision + rule-set v2 text amendments"). Knock-on: Week 4 D-023..D-028 → D-024..D-029, and so on.

Recommendation: bundle the renumbering as a single pass at the end of this review — don't shift D-numbers piecemeal.

### Week 4 (`04-week-04.md`)

**Status:** mostly OK, two minor adjustments:

- **Goal #11 F1 target ≥0.75 (line 28):** if Week 3 derivation produces noisier-than-expected training data (e.g., 0.78 agreement instead of 0.88), SFT F1 ceiling drops correspondingly. Soften the target to "F1 ≥ 0.72 on `violates_policy` (vs untuned Qwen ~0.62)" with the rationale: 12-15 point lift over untuned is the meaningful claim regardless of absolute number.
- **Step 4.17 top-20 error clustering (line 446):** add to the clustering rubric: "for any cluster traceable to R2/R4/R6 narrow-text gaps, surface as a rule-text issue (not a model issue)." Otherwise rules-need-fixing failures get logged as model failures, and Week 5's DPO mistake-mining will try to teach the model to mimic a rule the rule maintainer doesn't even want.

### Week 5 (`05-week-05.md`)

**Status:** mostly OK. One change:

- **Step 5.2 mining criteria (line 116):** the "strong disagreement" definition (line 73) should explicitly exclude disagreements traceable to R2/R4/R6 narrow-text gaps. Otherwise DPO will train to mimic strict-letter when the rule maintainer's intent is spirit-of-rule.

### Week 6 (`06-week-06.md`)

**Status:** no changes. Serving infrastructure is independent of training-data quality.

### Week 7 (`07-week-07.md`)

**Status:** no changes. Latency optimization is independent.

### Week 8 (`08-week-08.md`)

**Status:** one minor change:

- **Step 8.7 frontend sample content (line 277-281):** the curated demo content should include a **cross-rule-set foil** example — same chat message shown to two rule sets, demonstrating different judgments. This is the single most demo-worthy artifact of the project; current plan mentions it in the demo-video shot list (Step 8.10) but not in the frontend sample-content curation. Add: "include at least 3 cross-rule-set foils in `frontend/lib/sample_chat.ts` — messages where switching the rule set dropdown produces visibly different judgments."

### Week 9 (`09-week-09.md`)

**Status:** needs adversarial scope expansion. Three changes:

- **Step 9.5 adversarial scope (line 169):** expand from 50 hand-authored total to ~100, with explicit budget per rule set (~20 per the 5 seed rule sets). Add explicit slot for cross-rule-set foils (~20 separately, on top of the 100). Refer to `docs/adversarial_progamer_chat_v0.md` for the per-rule-set sketch.
- **Step 9.5 timing (line 161):** 100 examples at 10-12/session = 9-10 sessions across Days 3-4. That's tight. Either: (a) start adversarial authoring in Week 3 Day 7 buffer (banked-time slot), so Week 9 has ~50 already, or (b) accept cut to 75 examples if Week 3 starter set didn't happen.
- **Step 9.5 categories (line 178):** current categories are obfuscation/jailbreak/prompt-injection/emote-spam/multilingual/long-form. These are *generic* attack categories. Add an explicit *per-rule-set* category — "same content judged differently by different rule sets" — which is the Pareto-pitch evidence. This is the cross-rule-set foils slot.

### Week 10 (`10-week-10.md`)

**Status:** one change:

- **Step 10.1 model card limitations (line 51, "out-of-scope uses"):** add explicit limits surfaced by Week 1 audit:
  - "R6 coordinated/sustained harassment is not detected from single-message inference (requires conversation context that the API doesn't currently accept)."
  - "Rule-set text is strict-letter on R2 (slur words, not bigoted generalizations); deployments needing spirit-of-rule R2 should layer a generalization detector."
  - "Civil Comments training data under-represents real chat distributions; ToxicChat augmentation in Week 3 partially addresses this but non-English chat-regime performance is weakest."

### Week 11 (`11-week-11.md`)

**Status:** no changes structurally. Blog post angle:

- The "rule-set-conditional" pitch is more believable when accompanied by the cross-rule-set foils as the demo. The hook (Step 11.1) should reference one specific foil ("the same message — 'gg ez baby cope' — gets `no_action` under progamer_chat and `warn` under kids_learning_chat. That's the rule-set conditioning the project tests.")

---

## Recommended sequencing (if applying all)

1. **Today (or before Week 2 Day 1):** make the two decisions (CC-1: scope R6 out vs add `prior_context`; CC-5: rule-set v2 text amendments for R2/R4/R5). Capture as D-008 (replacing my earlier reflection's "D-008 candidate" wording).
2. **Week 1 reflection update:** rename D-008 reference to D-014 (or wherever the prior_context decision actually lands per CC-1 outcome).
3. **Week 2 Day 1 (rubric):** propagate the v2 rule-text decisions into the rubric; explicitly address R6 single-message handling.
4. **Week 2 Day 2 (sampling):** swap the toxicity-band stratification for the rule-firing-targeted bucketing.
5. **Week 3 Day 1 (schema/derivation):** new Step 3.0 — schema decision + rule-set v2 text update committed before any derivation logic.
6. **Week 3 Day 3 (cross-product):** add ToxicChat as primary chat-regime source.
7. **Week 3 Day 7 (buffer):** start adversarial authoring early — even 10-15 examples banked saves Week 9 friction.
8. **Week 4-5:** adjust F1 targets; exclude rule-text-gap disagreements from mistake mining.
9. **Week 8 demo curation:** include 3+ cross-rule-set foils.
10. **Week 9 adversarial:** expand scope; cite the sketch doc.
11. **Week 10 model card:** add Week-1-surfaced limitations explicitly.
12. **Week 11 blog post hook:** lead with a specific cross-rule-set foil.

## What I'd skip

- Don't renumber D-001..D-007 (those are committed in your voice already).
- Don't replace Civil Comments entirely — it's still useful as comment-regime baseline and `/leak-check`-traceable source.
- Don't expand adversarial to 500 examples (the 100 with cross-rule-set foils is plenty for the Pareto-pitch evidence; 500 is over-budget on content-exposure time).
- Don't bump the schema to add `prior_context` unless you specifically want R6 detection — the model card limitation is the cheap path.

---

## Open questions for you

1. **R6 scope decision:** add `prior_context` to schema (Option A — capability gain, retrain cost) or document the gap (Option B — recommended)?
2. **Rule-set v2 amendments:** decide each of the five R2/R4/R5 gaps before propagating into Week 2 rubric, Week 3 derivation, Week 9 adversarial. Don't try to defer; the cost is rework downstream.
3. **D-numbering policy:** comfortable shifting Week 2+ D-numbers, or prefer to keep Week 2 stable and slot new decisions as D-014a/D-014b/etc.?
4. **Adversarial timing:** start early in Week 3 Day 7 buffer, or compress into Week 9 Days 3-4?
