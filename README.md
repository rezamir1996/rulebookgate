# RulebookGate

A rulebook that lives on chain, a verdict that a contract can read.

RulebookGate answers one question about one submitted text:

> which rules, from a fixed on-chain list, does this text violate?

and publishes the answer as a set of rule ids plus a boolean gate. No prose verdict,
no operator judgement, no prompt that nobody can audit.

    verdict_of("ad-0042")     ->  "BLOCKED"
    violations_of("ad-0042")  ->  "r-medical,r-returns"
    quote_of("ad-0042", "r-medical") -> "cures diabetes and replaces your medication"
    is_clear("ad-0042")       ->  False

## Why this needs an Intelligent Contract

Every publication channel runs on a rulebook: ad copy must not promise guaranteed
returns, listings must not claim unproven medical results, community notices must not
carry referral links. That check is done today either by a person reading the text, or
by a model hidden behind a script.

Both have the same defect. The criterion lives inside a prompt, so it is not
inspectable, not reusable, and changes whenever someone edits the prompt. A payout
contract that wants to withhold money for a prohibited claim has nothing to read.

Here the rulebook is storage. Each rule has a stable id. The verdict is a subset of
those ids. A consumer contract reads one boolean before it releases anything, and the
evidence for every id is stored next to it.

## How consensus is used

Three layers, and only the middle one is non-deterministic.

| Layer | Who does it | Deterministic |
| --- | --- | --- |
| 1. Banned-phrase scan | code, against phrases the owner banned by name | yes |
| 2. Rule checking | the model, over a **closed list of rule ids** | no |
| 3. Quote verification | code, against the folded submission text | yes |

The model is never asked "is this compliant?". It is asked "which of these ids are
violated?", and it may answer only with ids it was given. A leader proposes the set;
every validator re-runs the whole judgement independently and must agree on the set.
Quotes are not compared, because two honest nodes may cite different spans of the same
sentence; instead each quote is machine-checked against the text, so a fabricated one
cannot be stored.

`docs/CONSENSUS.md` states exactly what consensus owns, what it does not, and why the
comparison is on ids rather than on prose.

## Fail closed

`is_clear(id)` is `True` only for a stored `CLEAR` verdict. Everything else is closed:

| Situation | Verdict | Gate |
| --- | --- | --- |
| banned phrase present | `BLOCKED` | closed |
| model reports a rule, quote verified | `BLOCKED` | closed |
| no violations, valid answer | `CLEAR` | open |
| model invented a quote or a rule id | `INCONCLUSIVE` | closed |
| model output unusable | `INCONCLUSIVE` | closed |
| banned phrase present, model broken | `BLOCKED` | closed |
| unknown submission | `""` | closed |

A false block costs one resubmission and comes with a readable reason. A false clear
puts a prohibited claim in front of an audience under the contract's authority, so the
contract always takes the cheap error. A proven banned-phrase hit commits the verdict
on its own: the model tier can add rule ids to a block, never remove one.

## Contract surface

19 methods: 3 write, 16 view. Lint reports 3 checks passed, no type errors.

**Admin**

- `add_rule(rule_id, text, banned)` - `banned` is a pipe separated phrase list, or `""`
- `retire_rule(rule_id)` - stops applying a rule to new submissions

**Publisher**

- `submit(submission_id, text)` -> verdict, written once and never overwritten

**Reader**

- `is_clear(id)`, `verdict_of(id)`, `violations_of(id)`, `violation_count_of(id)`
- `quote_of(id, rule_id)`, `source_of(id, rule_id)` - `DETERMINISTIC` or `MODEL`
- `counts_of(id)` - `"<deterministic>,<model>"`, how much of the verdict came from code
- `scope_of(id)` - the rule ids this verdict was judged against, frozen at submit time
- `text_of(id)`, `rule_text_of(rule_id)`, `rule_banned_of(rule_id)`, `rule_active(rule_id)`
- `rule_count()`, `submission_count()`, `gate_name()`, `config()`

State layout, normalization rules and the threat model are in `docs/DESIGN.md`.

## Deploy

Studio, constructor takes two arguments:

| Argument | Type | Meaning | Suggested value |
| --- | --- | --- | --- |
| `label` | `str` | public name of this rulebook edition, 3-64 chars | `promo-rules` |
| `max_rules` | `int` | hard cap on rulebook size, 1-40 | `40` |

The deployer becomes the admin. Gate nothing that holds value until the rules you care
about are actually written; an empty rulebook rejects every submission with `NO_RULES`
rather than passing it.

## Getting started

    # 1. the admin writes the rulebook
    add_rule("r-returns", "must not promise guaranteed investment returns",
             "guaranteed return|risk free")
    add_rule("r-medical", "must not make unproven medical claims", "")

    # 2. a publisher submits, anyone may call this
    submit("ad-0042", "Our savings plan offers a guaranteed return of eight percent ...")
    -> "BLOCKED"

    # 3. a consumer reads the gate before paying
    is_clear("ad-0042")                        -> False
    violations_of("ad-0042")                   -> "r-returns"
    quote_of("ad-0042", "r-returns")           -> "guaranteed return"
    source_of("ad-0042", "r-returns")          -> "DETERMINISTIC"
    counts_of("ad-0042")                       -> "1,0"     # no model was needed

How a consumer should read the gate, and how to write rules that behave well, are
covered in `docs/CONSENSUS.md` and `docs/DESIGN.md`.

## Repository layout

    contracts/rulebook_gate.py            the contract
    tests/direct/test_rulebook_gate.py    38 direct-mode tests
    docs/DESIGN.md                        purpose, state, decision ladder, rules, threats
    docs/CONSENSUS.md                     what consensus owns, failure matrix, limits
    EVIDENCE.md                           local verification and on-chain records
    scripts/prepare_test_sdk.py           fixes the GenVM archive name for direct mode

## Tests

38 tests pass in direct mode, no network and no account involved.

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    python scripts/prepare_test_sdk.py
    python -m pytest tests/direct -q      # 38 passed

Among them: banned phrases block with no model call at all; a fabricated quote, an
invented rule id, a two-word quote and unparseable output each fail closed; the
validator is executed directly and must reject a different rule set and an errored
leader; retiring a rule changes the future but not a verdict already issued.

## Limitations

- A colluding majority of validators can force any verdict. The design makes the
  honest path cheap and the bad verdict visible afterwards; it does not prevent it.
- Validation is per submission. Splitting one prohibited claim across two texts is not
  caught.
- Validators agreeing is not the same as being right. The banned-phrase layer exists so
  the rules that matter most do not depend on model recall.
- Quotes are stored in folded form: they prove the words are present, not their exact
  casing or punctuation.
- Rules are written by one admin. That is a trust assumption, made explicit rather than
  hidden, and `retire_rule` plus the frozen `scope_of` record exist to make rule
  changes auditable.

## License

MIT. See `LICENSE`.
