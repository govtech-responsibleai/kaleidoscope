You are given a claim or statement extracted from an LLM response. Your task is to decide whether this sentence contains a check-worthy factual claim that should be verified against a knowledge base.

A check-worthy factual claim is any statement that asserts a fact, event, statistic, definition, attribution, relationship, capability, or description that could be true or false. For example, if a claim is an opinion or an expression, it cannot be checked for factuality. Another example is that the statement has to be meaningful for it to be considered a claim. In such cases, it cannot be checked for factuality.

Additionally, you are given the `system prompt` that was used to instruct the chatbot. If the claim originates from or is directly instructed by the system prompt (e.g. disclaimers, greetings, boilerplate, role descriptions, or behavioral instructions the chatbot was told to include), it is NOT check-worthy — these are intended behavior, not factual claims to verify against the knowledge base.

Label the claim as "True" if it is check-worthy, and "False" if it is not.

Give your answer in JSON format as follows:
{
    "checkworthy": "<True or False>"
    "reasoning": "Brief explanation on your rationale."
}

This is the system prompt:
{{system_prompt}}

This is the claim:
{{claim_text}}
