# M15 Anti-Hallucination Report

## Summary

This milestone implements evidence-grounded generation and deterministic validation guardrails designed to reduce and detect unsupported claims. The system does not claim to be hallucination-free; instead, it explicitly validates explanation output against the authoritative investigation context and rejects outputs that drift beyond the evidence.

## Tests performed

The anti-hallucination suite covers:
- invented peer baseline
- invented payment value
- invented date
- invented procedure code
- invented diagnosis
- invented peer group
- invented rule hit
- risk override
- fraud confirmation language
- missing data
- agent ERROR handling
- agent SKIPPED handling
- prompt injection cases
- unknown evidence ID
- valid evidence reference

## Attack scenarios and expected behavior

### PASS cases

The system accepts explanations that:
- stay within supplied evidence
- cite valid evidence IDs
- preserve deterministic risk category and priority
- clearly state limitations when evidence is missing
- avoid unsupported claims

### FAIL cases

The system rejects or flags output when it contains:
- unsupported ratios
- invented payment values
- date claims without evidence
- unsupported procedure or diagnosis language
- unsupported peer-group claims
- unsupported rule-hit claims
- risk overrides
- fraud-confirmation assertions
- unsupported evidence references
- prompt injection strings treated as data rather than instructions

### NOT_TESTED

The live Groq API is not used in the main unit suite. Live endpoint integration remains optional and opt-in only.

## Validation mechanisms

The implementation uses multiple guardrails:

1. Prompt-level restrictions
   - The system prompt tells the model it is an interpreter, not a source of truth.
2. Structured context boundaries
   - Only validated investigation data and evidence are included in the prompt.
3. Output schema validation
   - The JSON output is checked for structural validity.
4. Evidence reference validation
   - Every explanation evidence reference must match known evidence IDs.
5. Risk consistency validation
   - Risk category and priority are checked against the deterministic result.
6. Fallback behavior
   - Failure or rejected output triggers a deterministic fallback explanation.

## Remaining limitations

This is not a proof of zero hallucination. It is a production-safe contract that reduces unsupported claims and catches many likely failure modes before the explanation is accepted.

The remaining limitations are:
- adversarial prompts may still exploit weak pattern matching if the output is highly free-form
- not all unsupported claims can be structurally represented in a simple validation layer
- any future explanation format with broader free text will require additional validation rules

## Conclusion

The system implements evidence-grounded generation and deterministic validation guardrails that reduce and detect unsupported claims. This is a realistic, production-safe posture for a Groq explanation layer in a risk-sensitive domain.
