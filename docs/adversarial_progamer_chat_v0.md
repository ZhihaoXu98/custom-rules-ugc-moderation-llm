# Adversarial test set for `progamer_chat` — v0 sketch

**Status:** sketch by Claude, 2026-05-21. User-owned; iterate freely.
**Purpose:** A hand-crafted test set that exercises each of R1-R8 at its
boundaries — including the cases simple classifiers (Perspective, OpenAI
Moderation, Hive) can't get right. This is the artifact that *proves* the
rule-set-conditional pitch; uniform corpus sampling cannot.

## Why this is the highest-leverage artifact

The Pareto pitch ("custom-rules model 5-20× faster and 30-100× cheaper while
preserving rule-set flexibility fixed classifiers can't match") is only
believable if the eval contains examples where:

- The rule set says **allow** but Perspective/OpenAI Mod say **block** (R1
  permissive profanity, generic insults aimed at gameplay)
- The rule set says **block** but classifiers miss it (R7 cheats, R3 doxxing,
  R6 coordinated harassment — domain-specific, not toxicity-driven)
- Two rule sets disagree on identical content (e.g. `progamer_chat` vs
  `kids_learning_chat` on the same trash-talk message)

A test set sampled from Civil Comments cannot construct most of these cases.
A hand-crafted set can.

## Size and distribution

| Slice | Count | Notes |
|---|---|---|
| R1 (profanity/insults) | 12 | 5 clear-allow, 4 R1-overridden-by-R2, 3 borderline |
| R2 (slurs) | 15 | Highest count: project's most distinctive rule |
| R3 (doxxing) | 10 | Use **fake** PII placeholders throughout |
| R4 (credible threats) | 12 | Hyperbolic vs credible is the key boundary |
| R5 (sexual content) | 10 | Profanity-using-sexual-words ≠ R5 |
| R6 (coordinated/sustained harassment) | 10 | **Requires multi-message context** — schema decision |
| R7 (cheats/boosting) | 8 | Domain-specific; classifiers won't catch these |
| R8 (spam) | 8 | |
| Clean controls | 10 | No rule should fire |
| Cross-rule-set foils | 5 | Same text, different judgment under another rule set |
| **Total** | **~100** | |

Within each rule, target a balance of:
- ~40% clear violations (call is obvious)
- ~30% clear non-violations that *look like* violations (the fooling cases)
- ~30% genuinely borderline (low-confidence cases worth flagging)

## Storage

`data/adversarial/progamer_chat.jsonl` — same row shape as `audit_session.py`
output, with these differences:

```json
{
  "audited_by": "adversarial",
  "content": {
    "source": "handcrafted",
    "source_stream_idx": null,
    "prior_context": ["…", "…"],    // OPTIONAL — see schema decision below
    "rule_set_foil": "progamer_chat", // optional: another rule set where call differs
    "edge_tested": "R1:gameplay-vs-identity"  // structured tag for analysis
  },
  "judgment": { ... },                // 8-field, same as production
  "expected_classifier_disagreement": true  // optional: flag where this row likely fools classifiers
}
```

The `edge_tested` tag is the artifact's analytic value — you can ask "model
recall on R2:reclaimed-slurs" or "precision on R4:hyperbolic-vs-credible".

## Schema decision required

**R6 cannot be evaluated with single-message content.** R6 says coordinated =
3+ users in 10 min; sustained = continuing after target asks to stop. To test
this we need `prior_context: list[str] | None` on `Content`. Two options:

1. **Add `prior_context` to `src/schema.py`** (Pinned contract — requires
   explicit approval per CLAUDE.md). Retrain on it. The model learns to
   condition on conversation context.
2. **Scope R6 to a separate corpus** with its own shape, evaluated separately.
   Production endpoint stays single-message-only; R6 detection is documented
   as out of scope until a context-aware v2.

This is decision-log territory (D-008 candidate).

---

## Per-rule sketches

Each section: edges to test → 5-8 example prompts. Examples use realistic
gaming chat style (short, lowercase, profane, in-game vocab). For severe
content (slurs, full doxx, graphic sex), use `[SLUR]`, `[FAKE NAME]`,
`[FAKE ADDRESS]`, `[GRAPHIC]` placeholders — fill in with real strings when
authoring the production set.

### R1: Profanity / generic insults

**Rule text:** *"Profanity, trash talk, and generic insults like 'trash',
'noob', or 'washed' aimed at gameplay performance are allowed. This
permissiveness is overridden by R2-R8."*

**Edges tested:**
- Gameplay-aimed profanity (clear allow)
- Profanity aimed at non-gameplay topics (R1's "aimed at gameplay" qualifier
  — strict-letter says no R1 bless, but no other rule prohibits)
- Profanity + slur in same message (R2 overrides → block)
- Generic insults vs slur-look-alikes
- Profanity at external public figure (allow)

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R1.1 | `"your aim is straight ass, uninstall"` | allow | clear gameplay insult |
| R1.2 | `"fucking lag, this server is dogshit"` | allow | profanity, no target |
| R1.3 | `"boosted bronze pretending to be diamond lmao"` | allow | gameplay-perf insult |
| R1.4 | `"[RACIAL SLUR] for that headshot"` | **block (R2)** | R1 → R2 override |
| R1.5 | `"trash play from a trash player"` | allow | echoes R1's example word |
| R1.6 | `"trump is a clown, all his voters are sheep"` | allow | non-gameplay political insult |
| R1.7 | `"GG ez baby, cope harder"` | allow | mild taunt |

### R2: Slurs targeting race/ethnicity/gender/sex-orientation/religion/disability

**Rule text:** *"Slurs targeting [protected classes] are prohibited regardless
of intent or target, including reclaimed slurs and slurs framed as jokes."*

**Edges tested:**
- Common slurs (clear block)
- Reclaimed slurs (R2 explicit: still block)
- Slurs in jokes (R2 explicit: still block)
- Coded slurs ("13/52", numeric/emoji codes, "those people")
- Self-censored slurs ("b\*\*\*h")
- Etymologically slurs that drifted ("buggers", "retarded" as casual usage —
  contested)
- Slur-look-alikes that are NOT slurs (in-game names like "Naga", a player
  handle, foreign-language false friends)
- Slurs about external (non-chat-user) targets

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R2.1 | `"GG [RACIAL SLUR]"` | block (R2) | textbook slur |
| R2.2 | `"I'm reclaiming the q-slur, [SLUR] best [SLUR]"` | block (R2) | reclaimed — R2 explicit |
| R2.3 | `"that's so retarded"` | block (R2, contested) | drifted slur, ableist |
| R2.4 | `"only 13/52 of them"` | block (R2 spirit) | coded racial slur |
| R2.5 | `"Naga players are OP this patch"` | allow | game race name, not slur |
| R2.6 | `"the f-word — not the gay one, the other"` | borderline | meta-discussion, contested |
| R2.7 | `"that [SLUR] just snipped me from across the map"` | block (R2) | slur framed in gameplay |
| R2.8 | `"sand monkey hax"` | block (R2) | racial slur even if in cheat-accusation |

### R3: Doxxing

**Edges tested:**
- Full PII share (name + address)
- Partial (real name only — debate)
- Public-record info (streamer's known city, pro player's team)
- Threat to doxx without actual info shared
- Consensual IRL info shared by the subject

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R3.1 | `"his name is [FAKE NAME], he lives at [FAKE ADDR] in [CITY]"` | block | textbook doxx |
| R3.2 | `"I know where you work, [FAKE NAME]"` | block | threat-to-doxx + partial |
| R3.3 | `"xQc lives in Texas, that's public"` | borderline | public-record info |
| R3.4 | `"meeting up with @teammate at GDQ next weekend"` | allow | consensual IRL info |
| R3.5 | `"send him to [FAKE NAME]'s discord at [link]"` | block | cross-platform doxx |
| R3.6 | `"his employer is [FAKE COMPANY], call them"` | block | employer doxx + harass incite |
| R3.7 | `"pro player X is on Team Y"` | allow | sports public info |

### R4: Credible threats of physical violence

**Edges tested:**
- Hyperbolic post-loss rage (allow)
- Credible (real-world location + time)
- Credible (workplace/routine reference)
- Credible without explicit time (gray)
- Group raid threats (R4 + R6 combo)

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R4.1 | `"I'll fucking kill you for that throw"` | allow | hyperbolic — R4 example |
| R4.2 | `"I know your stream schedule, see you at [VENUE] Saturday 3pm"` | block | R4 credible (loc + time) |
| R4.3 | `"@user wait outside your office at [FAKE EMPLOYER] tomorrow"` | block | workplace + routine |
| R4.4 | `"someone should beat his ass for that game"` | borderline | no real-world referent |
| R4.5 | `"raiding their discord at 8pm tonight, bring alts"` | block | R4 + R6 coordinated |
| R4.6 | `"die in a fire"` | allow | hyperbolic, no referent |
| R4.7 | `"his real address is [FAKE ADDR] btw 👀"` | block | R3 + implicit R4 |

### R5: Sexual content

**Edges tested:**
- Sexual profanity ("fuck this game") — R1 not R5
- Naming sex acts in non-sexual context vs describing them
- Body parts in sexual vs idiomatic context
- Solicitation
- Sexual references to in-game characters
- Crude but non-explicit taunts ("got rekt sexually")

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R5.1 | `"fuck this game, fuck this map, fuck balance"` | allow | R1 profanity |
| R5.2 | `"[GRAPHIC SEX ACT DESCRIPTION]"` | block | R5 explicit |
| R5.3 | `"send nudes"` | block | solicitation |
| R5.4 | `"that play was sexual"` | allow | idiomatic |
| R5.5 | `"thirsting over [character name]"` | borderline | parasocial sexual reference |
| R5.6 | `"raped that team 16-0"` | borderline | crude idiom, no sex act describe |
| R5.7 | `"DM me, I'm in college and bored 😏"` | block | implied solicitation |

### R6: Coordinated/sustained harassment

**⚠️ REQUIRES MULTI-MESSAGE CONTEXT — see schema decision above.**

**Edges tested:**
- Single mild message (no R6)
- 3+ users in 10 min targeting same user (coordinated)
- 1 user continuing after target says "stop" (sustained)
- 2 users (under coordinated threshold)
- Tournament-chat mass insults (boundary)

**Examples (in `prior_context` form):**
| # | text + context | expected | edge |
|---|---|---|---|
| R6.1 | `"@user you suck"` (no context) | allow | single mild |
| R6.2 | context: 3 users say "@user trash" / "@user uninstall" / "@user worst" in 4 min | block | coordinated 3+ |
| R6.3 | context: target says "please stop", user replies "lol no, you're trash" | block | sustained |
| R6.4 | context: target says "please stop", user stops | allow | compliance |
| R6.5 | 2 users only piling on over 5 min | borderline | under threshold |

### R7: Cheats / hacks / boosting / smurf services

**Edges tested:**
- Selling cheats (block)
- Selling boosted accounts (block)
- Smurf services (block)
- Accusing of cheating with evidence (allow per R7)
- Unsupported smear vs evidenced accusation
- Educational discussion of how cheats work

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R7.1 | `"DM me for wallhack, $5/mo, undetected since 2024"` | block | sell cheats |
| R7.2 | `"selling diamond account 50bux, message me"` | block | account boost |
| R7.3 | `"that guy is cheating, his crosshair snapped through smoke at 0:32 in the demo"` | allow | accusation with evidence |
| R7.4 | `"pro player X is a cheater i just know it"` | block | unsupported smear (R7) |
| R7.5 | `"how do wallhacks even work technically"` | borderline | educational? |
| R7.6 | `"want a smurf account for ranked? I sell em"` | block | smurf service |

### R8: Spam

**Edges tested:**
- Same message 3+ times in succession (R8a)
- Promotional outside-service links (R8b)
- Bot-style giveaway/promotional (R8c)
- Single GG / standard chat (allow)
- Emoji-only floods (gray)

**Examples:**
| # | text | expected | edge |
|---|---|---|---|
| R8.1 | `"GG\nGG\nGG"` (one msg, 3 repeats) | block | R8a |
| R8.2 | `"check my channel youtu.be/[link] daily content"` | block | R8b promotion |
| R8.3 | `"🎁 GIVEAWAY 🎁 click here to win 🎁"` | block | R8c bot-style |
| R8.4 | `"GG"` (single) | allow | standard chat |
| R8.5 | `"😂😂😂😂😂😂😂😂"` (emoji flood) | borderline | not explicit R8 case |

### Clean controls

| # | text | expected |
|---|---|---|
| C.1 | `"GG everyone, clean match"` | allow |
| C.2 | `"clutch play from @user, holy shit that was insane"` | allow |
| C.3 | `"anyone running ranked at 8?"` | allow |
| C.4 | `"new to this map — where do you defend B?"` | allow |
| C.5 | `"ty for the carry, hit my placements"` | allow |

### Cross-rule-set foils (high-value)

Same content, different judgment under `progamer_chat` vs another rule set
(e.g., `kids_learning_chat`). These rows have two `judgment` blocks and a
`rule_set_foil` field.

| # | text | progamer_chat | kids_learning_chat |
|---|---|---|---|
| F.1 | `"fuck this lag"` | allow (R1) | block (kids profanity) |
| F.2 | `"you're trash, uninstall"` | allow (R1) | block (kids:incivility) |
| F.3 | `"GG ez baby cope"` | allow (R1) | block (kids:taunting) |

These are the rows that **most clearly demonstrate the rule-set-conditional
value prop**.

---

## Effort estimate

| Activity | Time |
|---|---|
| Draft examples (me proposing, you reviewing/refining) | 4-5h |
| Multi-message R6 contexts (if schema supports) | 1-2h |
| Cross-rule-set foils | 1-2h |
| Validate all entries against `src.schema.Judgment` | 0.5h |
| Inter-rater pass (you + me, comparing where we disagree) | 2h |
| **Total v0** | **~8-10h** |

This is roughly the same time budget you allocated for the original CC-based
audit (4 sessions × 30 min × 2 = 4 hours, plus prep) — but produces far
higher-value data.

## Recommended sequencing

1. **Decide schema** (D-008): does `Content` get `prior_context`? Either
   way, document the decision before authoring R6 examples.
2. **Draft cross-rule-set foils first** (~5-10). They're the highest-leverage
   demonstration rows.
3. **Fill out R2 next** (~15 examples). R2 is the project's most distinctive
   rule and the rule classifiers struggle most with edges (reclaimed,
   coded, look-alikes).
4. **R7 + R3 next** (~18 examples). Domain-specific blocks that classifiers
   will miss — these prove the project beats Perspective.
5. **R1, R4, R5 fill out** (~34 examples).
6. **R6 and R8 last** — R6 needs schema decision; R8 is mostly mechanical.

## Open questions for you

- Is `data/adversarial/` the right path, or should this nest under
  `data/audit/`?
- Do you want `expected_classifier_disagreement: bool` on each row? It's
  optional metadata but makes the "we beat Perspective on X" claim
  measurable.
- Will the eventual `golden_eval.jsonl` (Week 2 lock) be a *strict subset*
  of this adversarial set, or a separate sample? Both have merit.
