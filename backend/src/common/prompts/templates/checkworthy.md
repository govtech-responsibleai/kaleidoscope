You are given a claim or statement extracted from an LLM response. Your task is to decide whether this sentence contains a check-worthy factual claim that should be verified against a knowledge base.

A check-worthy factual claim is any statement that asserts a fact, event, statistic, definition, attribution, relationship, capability, or description that could be true or false. For example, if a claim is an opinion or an expression, it cannot be checked for factuality. Another example is that the statement has to be meaningful for it to be considered a claim. In such cases, it cannot be checked for factuality.
Label the claim as "True" if it is check-worthy, and "False" if it is not.

Give your answer in JSON format as follows:
{
    "checkworthy": "<True or False>"
    "reasoning": "Brief explanation on your rationale."
}

This is the claim:
{{claim_text}}