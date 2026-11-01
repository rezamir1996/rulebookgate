# Design note: RulebookGate

## The problem

Every publication channel runs on a rulebook: ad copy must not promise guaranteed
returns, product listings must not claim unproven medical results, grant applications
must not ask for money outside the published categories, community notices must not
carry referral links. Today the check is done by a person reading the text, or by a
model wrapped in a script that nobody can audit afterwards.

Both options have the same defect: the criterion lives inside a prompt, so the
decision cannot be inspected, cannot be reused by another contract, and changes
silently whenever the prompt is edited.

RulebookGate moves the rulebook on chain. Rules are data with stable ids. A verdict is
a **set of rule ids**, not a paragraph of prose. Any other contract can read that set
before it pays out, publishes or mints.

## The shape of the decision

    submit(submission_id, text)
            |
            |-- rule 1: deterministic banned-phrase scan (no model, exact, cheap)
            |     hit  -> violation recorded, rule leaves the model's scope
            |     miss -> rule is passed to the model
            |
            |-- rule 2: model reads the remaining rules and the text
            |     returns ONLY rule ids from the closed list, each with a quote
            |
            |-- rule 3: code checks every quote against the text
            |     quote does not exist -> item dropped, verdict becomes INCONCLUSIVE
            |
            `-- stored verdict: CLEAR | BLOCKED | INCONCLUSIVE  + the id set

Three deliberate properties follow from that shape.

**The closed set is what makes consensus cheap.** The model is never asked "is this
text compliant?". It is asked "which of these ids are violated?". Two honest nodes can
word an explanation differently, but they cannot disagree about whether a specific
id from a list of at most 40 was violated without one of them being wrong. The
comparison is therefore a set comparison, not a text comparison.

**The deterministic layer runs first and never calls the model.** A phrase the rulebook
owner banned by name is not a judgement call. If the banned-phrase scan already
explains the outcome, no model is called at all, the result is identical on every node
by construction, and the submission costs nothing beyond one transaction.

**Quotes are the evidence, ids are the decision.** Every violation carries a span of
text that must exist verbatim in the submission. Code verifies this before storage, so
a hallucinated quote cannot survive. The quote is not part of consensus, because two
honest runs may legitimately highlight different spans of the same offending sentence.
It is attached by the leader, verified mechanically, and stored for the human reader.

## Why the gate fails closed

`is_clear(id)` returns true only when a stored verdict exists and that verdict is
`CLEAR`. Unknown id, unfinished submission, malformed model output, fabricated quote,
out-of-scope rule id: all of these leave the gate shut.

That asymmetry is the point. A false `BLOCKED` costs a publisher one resubmission and a
readable reason. A false `CLEAR` puts a prohibited claim in front of an audience under
the contract's authority. The contract always prefers the cheap error.

`INCONCLUSIVE` exists so the two cases are not confused: `BLOCKED` means "consensus
found these rules violated", `INCONCLUSIVE` means "consensus could not produce a
usable answer". A consumer that only wants hard failures can distinguish them; a
consumer that wants safety can treat both as closed.

## State

| Field | Type | Meaning |
| --- | --- | --- |
| `admin` | `Address` | Deployer. Only address allowed to add or retire rules. |
| `label` | `str` | Human label, returned by `gate_name()` and `config()`. |
| `max_rules` | `u256` | Hard cap on rulebook size, fixed at deploy. |
| `rule_index` | `str` | Comma-joined insertion order. Avoids iterating storage. |
| `rule_text` | `TreeMap[str, str]` | `rule_id` -> the rule as written. |
| `rule_banned` | `TreeMap[str, str]` | `rule_id` -> pipe-joined normalized banned phrases. |
| `rule_state` | `TreeMap[str, u256]` | 1 active, 0 retired. Retired rules stay readable. |
| `rules_added` | `u256` | Monotonic counter, never decremented. |
| `sub_text` | `TreeMap[str, str]` | The submitted text, kept so quotes stay checkable. |
| `sub_verdict` | `TreeMap[str, str]` | `CLEAR` / `BLOCKED` / `INCONCLUSIVE`. |
| `sub_violations` | `TreeMap[str, str]` | Sorted comma-joined violated rule ids. |
| `sub_scope` | `TreeMap[str, str]` | Rule ids that were in force at submit time. |
| `sub_counts` | `TreeMap[str, str]` | `"<deterministic>,<model>"` split of the hits. |
| `hit_quote` | `TreeMap[str, str]` | `submission_id\|rule_id` -> normalized quote. |
| `hit_source` | `TreeMap[str, str]` | `DETERMINISTIC` or `MODEL`. |
| `submissions` | `u256` | Monotonic counter. |

Rules are copied into `sub_scope` at submit time. Retiring a rule therefore never
rewrites the meaning of a verdict that was already issued: the set of rules a
submission was judged against is frozen with the verdict.

## Lifecycle

1. Deploy with `label` and `max_rules`.
2. Admin adds rules: `add_rule("r-returns", "no guaranteed returns", "guaranteed return|risk free")`.
3. Publisher calls `submit("ad-001", text)`. Anyone may submit; the text is the
   publisher's own claim.
4. Verdict is written once and never overwritten. Re-submitting the same id reverts,
   so a consumer can trust that the gate it read is the gate that was decided.
5. A consumer contract reads `is_clear("ad-001")` before publishing.
6. The admin retires stale rules with `retire_rule`. Retired rules are excluded from
   new submissions and remain readable for old ones.

## Normalization

Both the banned-phrase scan and the quote check run on a folded form of the text:
lower-cased, punctuation removed, whitespace collapsed, ZWNJ / tatweel / harakat
dropped, and the Arabic/Persian variants of yeh, kaf and teh marbuta unified. This is
what makes a quote check honest rather than pedantic: a model that returns a quote
with different punctuation is not lying, and a Persian submission written with Arabic
letters instead of Farsi letters must not slip past a phrase the owner banned in
Farsi spelling.

Consequence, stated plainly: quotes are stored in folded form. They are evidence that
the offending words are present, not a byte-exact copy of the original casing.

## Threat model

| Attack | Mitigation |
| --- | --- |
| Publisher writes a prompt injection into the submission. | The text is delimited and declared to be data. The answer space is a closed set of ids that the injection cannot enlarge. |
| Model hallucinates a violation. | The quote must exist in the folded text; a fabricated quote drops the item and forces `INCONCLUSIVE`. |
| Model returns an id that is not in scope. | Same path: dropped, `INCONCLUSIVE`. |
| Model returns a one-word "quote". | Quotes shorter than three tokens are dropped. |
| Publisher resubmits until a favourable verdict appears. | One submission id, one verdict, immutable. Reverting requires a new id, so the history of attempts stays public. |
| Non-admin injects or retires rules. | `add_rule` and `retire_rule` are admin-only. |
| Rulebook grows without bound and blows up the prompt. | `max_rules` cap at deploy, plus a hard text cap per rule and per submission. |

Not defended against, and worth saying out loud: a colluding majority of validators can
force any verdict; that is true of every Intelligent Contract. The design only makes
the honest path the cheap one.

## Writing rules that work

The quality of the whole gate is the quality of the rulebook.

- **One idea per rule.** "No guarantees and no referral links" is two rules. A
  violated id is a fact a consumer can act on; a bundle of ideas is not.
- **Put the unambiguous core in `banned`.** Any phrase the owner would always reject,
  whatever the context, belongs in the phrase list. Those hits cost no model call and
  cannot disagree between nodes.
- **Keep the rule text short and operational.** It is read by a model as a checklist
  item and by a human in an appeal. One sentence, under 240 characters.
- **Do not write a rule you cannot enforce.** "Must be truthful" is not a rule, it is
  a wish. "Must not state a medical outcome without a cited trial" is a rule.
- **Retire, never renumber.** Retiring keeps old verdicts readable. A new rule gets a
  new id.
- **Stay well under `max_rules`.** The model sees every active rule in one prompt; 20
  focused rules behave far better than 40 vague ones, and the cap exists so that
  failure is loud rather than silent.

## Non-goals

- Not a moderation system. It does not detect categories of harm that nobody wrote
  down as a rule.
- Not an appeal court. There is no second-instance review; the remedy for a wrong rule
  is to change the rule, which is why `retire_rule` exists.
- Not access control for a specific token. It answers one question and stores the
  answer.
