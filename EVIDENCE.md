# Evidence

Two kinds of evidence are kept apart on purpose: what was verified locally on a
machine, and what is recorded on a public network. They are not interchangeable.

## Local verification

Run on the source in this repository, no network access, no funded account.

| Check | Command | Result |
| --- | --- | --- |
| Direct-mode tests | `python -m pytest tests/direct -q` | 38 passed |
| Contract lint | `genvm-lint check contracts/rulebook_gate.py` | 3 checks passed, validation passed, 19 methods (3 write, 16 view) |
| Type check | `genvm-lint typecheck contracts/rulebook_gate.py` | no type errors |

The documented walkthrough is not illustrative, it is the actual output of a direct-mode
run of the contract in this repository:

    submit("ad-0042", <text containing "guaranteed return">)  -> BLOCKED
    is_clear("ad-0042")            -> False
    violations_of("ad-0042")       -> r-returns
    quote_of("ad-0042", "r-returns")  -> guaranteed return
    source_of("ad-0042", "r-returns") -> DETERMINISTIC
    counts_of("ad-0042")           -> 1,0
    scope_of("ad-0042")            -> r-returns,r-medical
    config()                       -> promo-rules|40

`counts_of` reads `1,0`: one violation found by the phrase layer, zero by the model.
No model call was made for that submission.

## On-chain record

GenLayer Studionet. Every hash below was copied from the explorer, not retyped.

Contract: `0x2055aCe23ace03A8Ec7FB5a8304c4323883DFcb5`
Constructor: `promo-rules`, `40`

| Step | Transaction | Result |
| --- | --- | --- |
| deploy | `0x25b64e1d82e3d67c32b98ac9c25d7d053265bf6b1bf53c532d56cf5ba984425f` | FINALIZED, SUCCESS, 5 validators, 0 rotations |
| add_rule `r-returns` | `0x44a8ff13d2c729cafad47cca23434ed75e051215e7380c7aed8ba3d13d530ce4` | FINALIZED, SUCCESS |
| add_rule `r-medical` | `0xa1bba972f14dfa9d00fa2730f5c893581e8c82520fd3d5d6d170baf06a0351fc` | FINALIZED, SUCCESS |
| submit `ad-0001` | `0x313e766a00cdab633aaa8fb1b51fa44553d35068b2e86be30035456b36f81577` | FINALIZED, SUCCESS |
| submit `ad-0002` | `0x5576b37b09cfb3ae1b4d3db3b1e1646247ccb2a1654b7b005d2ea91004c7a556` | FINALIZED, SUCCESS |
| submit `ad-0003` | `0xba8601a8df2193b2c8ce6190e1fb9c84875f62b74a7ef9a94a6772fe7b607a40` | FINALIZED, SUCCESS |

### The three submissions

`ad-0001` hits a banned phrase. No model was called at all: the consensus output of the
transaction is the empty model result, and the verdict came from the phrase layer.

`ad-0002` breaks a rule that has no banned phrases, so this is the model branch. The
consensus output carries the rule id and the quote the model attached:

    ids    -> [r-medical]
    quotes -> {r-medical: "cures diabetes and replaces your medication"}

Three validators agreed, two were idle, none disagreed, and the leader was never
rotated. The quote is a real span of the submitted text, which is what the code
verified before storing it.

`ad-0003` is clean and its model answer is an empty list, so the gate opens.

### Reads taken from Studionet

    config()                          -> promo-rules|40
    gate_name()                       -> promo-rules
    rule_count()                      -> 2
    submission_count()                -> 3

    verdict_of(ad-0001)               -> BLOCKED
    counts_of(ad-0001)                -> 1,0
    source_of(ad-0001, r-returns)     -> DETERMINISTIC
    quote_of(ad-0001, r-returns)      -> guaranteed return

    verdict_of(ad-0002)               -> BLOCKED
    counts_of(ad-0002)                -> 0,1
    violations_of(ad-0002)            -> r-medical
    source_of(ad-0002, r-medical)     -> MODEL
    quote_of(ad-0002, r-medical)      -> cures diabetes and replaces your medication

    verdict_of(ad-0003)               -> CLEAR
    is_clear(ad-0003)                 -> True
    counts_of(ad-0003)                -> 0,0

    scope_of(ad-0002)                 -> r-returns,r-medical
    rule_active(r-medical)            -> True

The two layers are visible side by side: `1,0` for the phrase case, `0,1` for the case
that needed reading, `0,0` for the clean text.

### What this record does not show

- No failing case was submitted on chain. The `INCONCLUSIVE` path is covered by the
  local suite (fabricated quote, invented rule id, unparseable output), not by a live
  transaction, because provoking it requires a model that hallucinates on demand.
- Idle validators are normal in this consensus implementation and are counted as idle,
  not as disagreement; no transaction here recorded a disagreement.
- This is a demo rulebook of two rules, chosen to exercise both layers. It is not
  evidence that any real publication policy is enforceable end to end.
