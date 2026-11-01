# How consensus is used

## What the validators own

| Part of the outcome | Produced by | Compared across nodes? |
| --- | --- | --- |
| Banned-phrase hits | deterministic code | no need, identical by construction |
| Which rule ids the model reports | the model, independently on every node | **yes, as a set** |
| Quote attached to a violation | the leader | no, verified mechanically instead |
| Quote exists in the text | deterministic code | no need, identical by construction |
| Quote is at least three tokens | deterministic code | no need |
| `CLEAR` / `BLOCKED` / `INCONCLUSIVE` | deterministic code, from the two layers above | no need |
| Everything stored | deterministic code | no need |

The design goal is that the only thing which can differ between two honest nodes is
the middle row, and that row is a small set of ids drawn from a list of at most 40
items that both nodes already hold in storage. That is why the equivalence test can be
strict equality on the set and still converge.

## The nondet block

    def leader_fn():
        return self._judge(prompt, folded, pending)      # one model call

    def validator_fn(leader_result) -> bool:
        if not isinstance(leader_result, gl.vm.Return):
            return False
        leader = leader_result.calldata
        if not isinstance(leader, dict):
            return False
        mine = self._judge(prompt, folded, pending)      # independent re-run
        return leader.get("ids") == mine["ids"]

    result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

Four properties worth stating explicitly.

**No storage is touched inside the nondet block.** `folded`, `pending` and the prompt
are computed before it starts and passed as plain arguments. Every write happens after
`run_nondet_unsafe` returns.

**The validator is not a format check.** It does not inspect the leader's JSON for
plausibility; it re-runs the whole judgement against the same closed rule list and
compares the conclusion. Two nodes that disagree about whether rule `r-medical` is
violated produce a disagreement, which is exactly what the consensus layer is for.

**`ids` are compared, `quotes` are not.** Two honest nodes reading the same offending
sentence may highlight different spans: one cites the whole clause, the other the
predicate. Comparing spans would turn a correct agreement into a dispute. The quote is
therefore treated as the leader's evidence attachment, and it earns its keep because
code checks it against the submission before it is stored. A leader cannot use this
freedom to smuggle in a violation: the id still has to match, and a quote that is not
in the text destroys the whole verdict.

**Bad leader output is a disagreement, not a crash.** `_judge` catches every exception
and returns `{"ok": False}`. On chain, a leader who returns unparseable output will
fail its validator whenever an honest node produced a usable answer. If every node
fails, the stored verdict is `INCONCLUSIVE`, which closes the gate.

## Failure matrix

| Situation | Stored verdict | Gate |
| --- | --- | --- |
| A banned phrase is present | `BLOCKED` | closed |
| Model reports a rule, quote verified | `BLOCKED` | closed |
| No double hits, valid empty answer | `CLEAR` | open |
| Model output is not JSON | `INCONCLUSIVE` | closed |
| Model invents a quote | `INCONCLUSIVE` | closed |
| Model invents a rule id | `INCONCLUSIVE` | closed |
| Model returns a two-word "quote" | `INCONCLUSIVE` | closed |
| A banned phrase is present, model broken | `BLOCKED` | closed |
| No submission, or an unknown id | `""` | closed |
| Rulebook has no active rules | transaction reverts | n/a |

The one place where a broken model is ignored is the row where a banned phrase already
proved a violation. That is deliberate: code that proved a block should not be
overruled by a model that failed to answer. The verdict is monotone in that sense --
the model tier can add rule ids to a block, never remove one and never soften a proven
block into `INCONCLUSIVE`.

## Read order for a consumer

A contract that pays or publishes should ask, in this order:

1. `verdict_of(submission_id)` -> `CLEAR`, `BLOCKED`, `INCONCLUSIVE`, or `""`.
2. `is_clear(submission_id)` -> the single boolean, `True` only for `CLEAR`.
3. To explain a refusal: `violations_of(id)`, then per rule `quote_of(id, rule_id)`
   and `source_of(id, rule_id)`.

    ALLOW  if is_clear(submission_id)     # CLEAR
    HOLD   otherwise                      # BLOCKED, INCONCLUSIVE, or no verdict yet

Gating on `is_clear` rather than on `violations_of(id) == ""` is the whole point: an
unknown submission and an inconclusive one both have an empty violation string, and
both must stay shut.

Submission ids are caller chosen, 2 to 64 characters of letters, digits, `-`, `_` and
`.`. Derive them from something stable about the item being judged, for example
`"<campaign>-<slot>-<hash prefix>"`, because a rejected text keeps its id and its
verdict forever: the public record then shows every version that was attempted.

One submission costs one transaction plus one model call, unless every active rule was
settled by a banned phrase, in which case there is no model call at all. A rulebook
whose common violations are phrases is markedly cheaper to run than one that relies
entirely on reading.

## What this does not give you

- **No guarantee against a colluding majority.** A majority of validators can report
  any set of ids. This contract does not make that impossible; it makes the honest
  path the cheap one and records the evidence so a bad verdict is visible afterwards.
- **No semantic memory.** Each submission is judged in isolation. A publisher who
  splits a prohibited claim across two texts is not caught.
- **The model can miss a violation.** Validators agree with each other, and agreement
  is not correctness. The banned-phrase layer exists partly so that the most important
  rules do not depend on model recall at all.
- **Language coverage is uneven.** The fold handles Latin and Persian/Arabic script
  features, but the model's reading quality across languages is whatever the model's
  is.
