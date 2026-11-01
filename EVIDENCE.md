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

Deployment and calls on GenLayer Studionet are appended here after the contract is
deployed, with transaction hashes copied from the explorer rather than retyped. Until
that section is filled, treat this repository as locally verified only.
