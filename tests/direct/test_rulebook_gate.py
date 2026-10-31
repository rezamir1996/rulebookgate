"""Direct-mode tests for RulebookGate. No network, no Studio: the GenVM runs in memory.

The file is ASCII only. Script folding is exercised through codepoint escapes so the
fold table is covered without putting non-ASCII bytes in the source.
"""

CLEAN = (
    "Join our community gardening workshop this Saturday. We will cover soil "
    "preparation, seasonal planting and simple composting for small balconies. "
    "Bring gloves and a reusable water bottle. The session runs for two hours and "
    "seats are limited, so register early at the front desk."
)

BANNED_HIT = (
    "Our savings plan offers a guaranteed return of eight percent every single year. "
    "Sign up before Friday and our advisors will walk you through the paperwork in "
    "person or online at the branch."
)

MEDICAL = (
    "Drinking this herbal blend every morning cures diabetes and replaces your "
    "medication. Customers report better sleep and steady energy within the first "
    "week, and the blend ships in a resealable pouch."
)

# A quote that really is a span of MEDICAL, after folding.
GOOD_QUOTE = "cures diabetes and replaces your medication"
# A quote that sounds plausible and appears nowhere in MEDICAL.
FAKE_QUOTE = "cures diabetes and replaces insulin injections"

PROMPT = r"(?s).*rulebook checker.*"

ARABIC_YEH = "\u064a"
FARSI_YEH = "\u06cc"
ARABIC_KAF = "\u0643"
KEHEH = "\u06a9"
ZWNJ = "\u200c"
TATWEEL = "\u0640"


def _gate(direct_deploy, name="promo-rules", cap=40):
    return direct_deploy("contracts/rulebook_gate.py", name, cap)


def _seed(gate):
    """One rule with banned phrases, one rule that needs reading, one link rule."""
    gate.add_rule(
        "r-returns",
        "must not promise guaranteed investment returns",
        "guaranteed return|risk free",
    )
    gate.add_rule(
        "r-medical",
        "must not make unproven medical claims",
        "",
    )
    gate.add_rule(
        "r-links",
        "must not carry referral or affiliate links",
        "ref link|use my code",
    )
    return gate


def _medical_hit(quote=GOOD_QUOTE, rule_id="r-medical"):
    return '{"violations": [{"rule_id": "' + rule_id + '", "quote": "' + quote + '"}]}'


def _no_hits():
    return '{"violations": []}'


# ------------------------------------------------------------ deterministic layer
def test_banned_phrase_blocks_without_any_model_call(direct_vm, direct_deploy):
    """No mock_llm is registered: if the contract called the model this would fail."""
    gate = _gate(direct_deploy)
    gate.add_rule("r-returns", "must not promise guaranteed returns", "guaranteed return")

    assert gate.submit("ad-1", BANNED_HIT) == "BLOCKED"
    assert gate.is_clear("ad-1") is False
    assert gate.violations_of("ad-1") == "r-returns"
    assert gate.source_of("ad-1", "r-returns") == "DETERMINISTIC"
    assert gate.quote_of("ad-1", "r-returns") == "guaranteed return"
    assert gate.counts_of("ad-1") == "1,0"


def test_clean_text_is_clear(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _no_hits())

    assert gate.submit("ad-2", CLEAN) == "CLEAR"
    assert gate.is_clear("ad-2") is True
    assert gate.violations_of("ad-2") == ""
    assert gate.violation_count_of("ad-2") == 0


def test_banned_phrase_matching_ignores_case_and_punctuation(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    gate.add_rule("r-returns", "must not promise guaranteed investment returns", "guaranteed return")

    assert gate.submit("ad-3", "Our plan delivers a Guaranteed, Return this year for every saver.") == "BLOCKED"
    assert gate.quote_of("ad-3", "r-returns") == "guaranteed return"


def test_banned_phrase_matching_is_token_aligned(direct_vm, direct_deploy):
    """'ref link' must not fire on a longer word that merely starts the same way."""
    gate = _gate(direct_deploy)
    gate.add_rule("r-links", "must not carry referral or affiliate links", "ref link")
    direct_vm.mock_llm(PROMPT, _no_hits())

    assert gate.submit("ad-4", "The preflight linker tool ships today with a full repair kit included.") == "CLEAR"


def test_persian_letter_variants_are_folded_before_matching(direct_vm, direct_deploy):
    """The same banned word in Arabic letters must not slip past a Farsi spelling."""
    farsi = FARSI_YEH + KEHEH + FARSI_YEH + " " + FARSI_YEH + KEHEH
    gate = _gate(direct_deploy)
    gate.add_rule("r-script", "banned wording in persian", farsi)

    arabic = ARABIC_YEH + ZWNJ + ARABIC_KAF + TATWEEL + ARABIC_YEH + " " + ARABIC_YEH + ARABIC_KAF
    text = "this notice repeats " + arabic + " three times and then some more words follow here"
    assert gate.submit("ad-5", text) == "BLOCKED"
    assert gate.source_of("ad-5", "r-script") == "DETERMINISTIC"


def test_deterministic_hit_survives_a_broken_model(direct_vm, direct_deploy):
    """Two rules still need the model and no mock exists. The proven block must stand."""
    gate = _seed(_gate(direct_deploy))

    assert gate.submit("ad-25", BANNED_HIT) == "BLOCKED"
    assert gate.violations_of("ad-25") == "r-returns"
    assert gate.is_clear("ad-25") is False


def test_all_rules_settled_by_phrases_spends_no_model_call(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    gate.add_rule("r-returns", "must not promise guaranteed returns", "guaranteed return")

    assert gate.submit("ad-6", BANNED_HIT) == "BLOCKED"
    assert gate.counts_of("ad-6") == "1,0"


# ------------------------------------------------------------------ model layer
def test_model_reports_a_rule_with_a_verified_quote(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit())

    assert gate.submit("ad-7", MEDICAL) == "BLOCKED"
    assert gate.violations_of("ad-7") == "r-medical"
    assert gate.source_of("ad-7", "r-medical") == "MODEL"
    assert gate.quote_of("ad-7", "r-medical") == GOOD_QUOTE
    assert gate.counts_of("ad-7") == "0,1"


def test_deterministic_and_model_hits_are_merged_and_sorted(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit())
    both = BANNED_HIT + " " + MEDICAL

    assert gate.submit("ad-8", both) == "BLOCKED"
    assert gate.violations_of("ad-8") == "r-medical,r-returns"
    assert gate.violation_count_of("ad-8") == 2
    assert gate.counts_of("ad-8") == "1,1"
    assert gate.source_of("ad-8", "r-returns") == "DETERMINISTIC"
    assert gate.source_of("ad-8", "r-medical") == "MODEL"


def test_fabricated_quote_fails_closed(direct_vm, direct_deploy):
    """The model asserts a violation and invents the evidence: nothing is trusted."""
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit(FAKE_QUOTE))

    assert gate.submit("ad-9", MEDICAL) == "INCONCLUSIVE"
    assert gate.is_clear("ad-9") is False
    assert gate.violations_of("ad-9") == ""


def test_out_of_scope_rule_id_fails_closed(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit(rule_id="r-imaginary"))

    assert gate.submit("ad-10", MEDICAL) == "INCONCLUSIVE"
    assert gate.is_clear("ad-10") is False


def test_one_extra_hallucinated_item_taints_a_valid_verdict(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(
        PROMPT,
        '{"violations": [{"rule_id": "r-medical", "quote": "' + GOOD_QUOTE + '"},'
        ' {"rule_id": "r-imaginary", "quote": "steady energy within the first week"}]}',
    )

    assert gate.submit("ad-11", MEDICAL) == "INCONCLUSIVE"
    assert gate.violations_of("ad-11") == "r-medical"


def test_two_word_quote_is_not_accepted_as_evidence(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit("cures diabetes"))

    assert gate.submit("ad-12", MEDICAL) == "INCONCLUSIVE"


def test_malformed_model_output_fails_closed(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, "sounds fine to me")

    assert gate.submit("ad-13", MEDICAL) == "INCONCLUSIVE"
    assert gate.is_clear("ad-13") is False


def test_missing_violations_key_fails_closed(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, '{"verdict": "ok"}')

    assert gate.submit("ad-14", CLEAN) == "INCONCLUSIVE"


# -------------------------------------------------------------------- validator
def test_validator_agrees_when_the_rule_set_matches(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit())
    gate.submit("ad-15", MEDICAL)

    assert direct_vm.run_validator() is True


def test_validator_rejects_a_different_rule_set(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit())
    gate.submit("ad-15", MEDICAL)

    other = {"ids": ["r-links"], "quotes": {}, "dropped": 0, "ok": True}
    assert direct_vm.run_validator(leader_result=other) is False


def test_validator_rejects_a_leader_that_errored(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _medical_hit())
    gate.submit("ad-15", MEDICAL)

    assert direct_vm.run_validator(leader_error=RuntimeError("boom")) is False


# ------------------------------------------------------------------ rule state
def test_only_the_admin_may_add_rules(direct_vm, direct_deploy, direct_alice):
    gate = _gate(direct_deploy)
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("NOT_ADMIN"):
            gate.add_rule("r-x", "an injected rule nobody approved", "")


def test_only_the_admin_may_retire_rules(direct_vm, direct_deploy, direct_alice):
    gate = _seed(_gate(direct_deploy))
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("NOT_ADMIN"):
            gate.retire_rule("r-medical")


def test_rulebook_cap_is_enforced(direct_vm, direct_deploy):
    gate = _gate(direct_deploy, cap=1)
    gate.add_rule("r-one", "the only rule this gate can hold", "")
    with direct_vm.expect_revert("RULEBOOK_FULL"):
        gate.add_rule("r-two", "a second rule that must not fit", "")


def test_duplicate_rule_id_is_rejected(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    gate.add_rule("r-one", "the first version of the rule", "")
    with direct_vm.expect_revert("RULE_EXISTS"):
        gate.add_rule("r-one", "a silently rewritten version", "")


def test_empty_banned_phrase_is_rejected(direct_vm, direct_deploy):
    """A phrase that folds to nothing would match every submission."""
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("BAD_BANNED"):
        gate.add_rule("r-empty", "a rule with an unusable phrase", " | | ")


def test_rule_id_cannot_contain_the_key_separator(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("BAD_RULE_ID"):
        gate.add_rule("r|one", "a rule id that would corrupt storage keys", "")


def test_retiring_a_rule_removes_it_from_new_submissions(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    gate.retire_rule("r-returns")
    direct_vm.mock_llm(PROMPT, _no_hits())

    assert gate.rule_active("r-returns") is False
    assert gate.submit("ad-16", BANNED_HIT) == "CLEAR"


def test_scope_is_frozen_at_submission_time(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    direct_vm.mock_llm(PROMPT, _no_hits())
    gate.submit("ad-17", CLEAN)
    frozen = gate.scope_of("ad-17")

    gate.retire_rule("r-medical")
    assert gate.scope_of("ad-17") == frozen
    assert "r-medical" in frozen


def test_retiring_twice_is_rejected(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    gate.retire_rule("r-medical")
    with direct_vm.expect_revert("ALREADY_RETIRED"):
        gate.retire_rule("r-medical")


def test_unknown_rule_cannot_be_retired(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    with direct_vm.expect_revert("RULE_NOT_FOUND"):
        gate.retire_rule("r-ghost")


# ---------------------------------------------------------------- submission rules
def test_gate_fails_closed_before_any_submission(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    assert gate.is_clear("ad-none") is False
    assert gate.verdict_of("ad-none") == ""
    assert gate.violations_of("ad-none") == ""


def test_verdicts_are_immutable(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    gate.submit("ad-18", BANNED_HIT)
    direct_vm.mock_llm(PROMPT, _no_hits())
    with direct_vm.expect_revert("ALREADY_SUBMITTED"):
        gate.submit("ad-18", CLEAN)


def test_submission_needs_a_rulebook_first(direct_vm, direct_deploy):
    gate = _gate(direct_deploy)
    with direct_vm.expect_revert("NO_RULES"):
        gate.submit("ad-19", CLEAN)


def test_thin_text_is_rejected(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    with direct_vm.expect_revert("BAD_TEXT"):
        gate.submit("ad-20", "too short to judge")


def test_repeated_letters_are_not_accepted_as_text(direct_vm, direct_deploy):
    """Long enough in bytes, one token after folding: must not reach the model."""
    gate = _seed(_gate(direct_deploy))
    with direct_vm.expect_revert("TEXT_TOO_THIN"):
        gate.submit("ad-21", "-" * 200)


def test_submission_id_cannot_contain_the_key_separator(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy))
    with direct_vm.expect_revert("BAD_SUBMISSION_ID"):
        gate.submit("ad|22", CLEAN)


# ------------------------------------------------------------------- read surface
def test_counters_and_config_are_readable(direct_vm, direct_deploy):
    gate = _seed(_gate(direct_deploy, name="affiliate-ads", cap=12))
    direct_vm.mock_llm(PROMPT, _no_hits())
    gate.submit("ad-23", CLEAN)
    gate.submit("ad-24", BANNED_HIT)

    assert gate.config() == "affiliate-ads|12"
    assert gate.gate_name() == "affiliate-ads"
    assert gate.rule_count() == 3
    assert gate.submission_count() == 2
    assert gate.rule_text_of("r-medical") == "must not make unproven medical claims"
    assert gate.rule_banned_of("r-returns") == "guaranteed return|risk free"
    assert gate.text_of("ad-23") == CLEAN


# One contract class per test is a direct-mode limitation, so each bound gets its own test.
def test_gate_name_lower_bound_is_enforced(direct_vm, direct_deploy):
    with direct_vm.expect_revert("BAD_GATE_NAME"):
        direct_deploy("contracts/rulebook_gate.py", "ab", 10)


def test_max_rules_lower_bound_is_enforced(direct_vm, direct_deploy):
    with direct_vm.expect_revert("BAD_MAX_RULES"):
        direct_deploy("contracts/rulebook_gate.py", "promo-rules", 0)


def test_max_rules_upper_bound_is_enforced(direct_vm, direct_deploy):
    with direct_vm.expect_revert("BAD_MAX_RULES"):
        direct_deploy("contracts/rulebook_gate.py", "promo-rules", 41)
