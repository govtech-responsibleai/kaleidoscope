You are given a span of text extracted from an LLM response. Your task is to determine whether the marked text contains a **check-worthy factual claim** that should be verified against a knowledge base.

## Definition of a check-worthy claim

A text span is **check-worthy** if it asserts information that could reasonably be verified as true or false using a reliable knowledge source.

This includes, but is not limited to:

- assertions, facts, and definitions or explanations of concepts
- attributions, relationships, capabilities, requirements, rules, or constraints
- quantities, dates, statistics, rankings, or comparisons

When in doubt, prefer **True** if the span contains a concrete factual assertion that could be checked.

## What is NOT check-worthy?

Mark the span as **not check-worthy** if it does **not** make a factual assertion requiring verification.

This includes:

- opinions, preferences, advice, or subjective judgments
- greetings, disclaimers, or boilerplate
- role or behavior instructions originating from the system prompt
- purely structural text that organizes the response rather than asserting facts
- conversational lead-ins or framing text introducing bullets, lists, or next steps
- prompts or invitations for the user to respond

### Examples of NOT check-worthy structural / conversational text

The following are usually **False** unless they also contain a specific factual assertion:

- headers, section titles, and formatting
  - “Next steps”
  - “What you can do now”
  - “Summary:”
- prompt lines and action-oriented recommendations
  - “If you like, tell me:”
  - “Let me know if you want me to…”
  - “I recommend checking with support.”

## Use context carefully

Use the surrounding context to decide whether the marked text is a genuine claim, or merely structural or conversational.
If the marked text is a fragment, interpret it in context. Only label **True** when the marked span contributes a factual claim.

## Output format

Return your answer in JSON:

```json
{
  "checkworthy": "<True or False>",
  "reasoning": "Brief explanation of why the marked text is or is not a check-worthy factual claim."
}

=== SYSTEM PROMPT ===
{{system_prompt}}

=== CLAIM IN CONTEXT (the claim being evaluated is marked with >>> <<<) ===
{{claim_context}}

===

