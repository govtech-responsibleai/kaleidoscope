Given the following QUESTION, ANSWER, DOCUMENT and CLAIM you must analyze the claim and determine whether the claim can be inferred from the contents of the DOCUMENT.

The CLAIM is a statement extracted from the ANSWER. The ANSWER is provided for reference, but should NOT be considered in the evaluation of the current CLAIM.

The CLAIM must not offer new information beyond the context provided in the DOCUMENT.

The CLAIM also must not contradict information provided in the DOCUMENT.

IMPORTANT: The CLAIM does NOT need to cover all the claims in the DOCUMENT. 

Output your final label by strictly following this format: "true" if the claim can be inferred from the DOCUMENT and "false" if the claim cannot be inferred from the contents of the DOCUMENT.

Show your reasoning. Be concise in the reasoning and focus more on the failures, if any.

--
(These do not count as background information):
QUESTION:
{{question_text}}

ANSWER:
{{answer_text}}

--
DOCUMENT:
{{kb_documents}}

--

CLAIM to evaluate:
{{claim_text}}

--

Your output should be in JSON FORMAT with the keys "label" and "reasoning".

Ensure that the JSON is valid and properly formatted.

{
  "label": true,  // true = accurate, false = inaccurate/hallucinated
  "reasoning": "Brief explanation referencing the knowledge base document."
}