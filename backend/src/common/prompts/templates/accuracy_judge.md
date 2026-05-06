## Instructions
Given the following `Question`, `Answer`, `knowledge base` and `claim` you must analyze the `claim` and determine whether the `claim` can be inferred from the contents of the `knowledge base`.

The `claim` is a statement extracted from the `Answer`. The `Answer` is provided FOR REFERENCE to where and how the `claim` was extracted from the `Answer`. Do not use the `Answer` in your evaluation of the `claim` other than to understand the context of the single short `claim`.

The `knowledge base` consists of multiple source dcuments, each delimited and labeled (e.g. === Source Document: testing.md ===).

Your task is to:
1. Decide whether the `claim` can be inferred using only information explicitly stated in the `knowledge base`.
2. Assign a final label:
   - "true" if the claim can be inferred from the knowledge base, OR if the claim states a common-sense fact (see below)
   - "false" if the claim cannot be inferred and is not common sense, or is incomplete

### Common-sense exception

A claim counts as common sense if it is a universally known, uncontroversial fact that any adult would accept without a source — e.g., "Singapore is a country", "humans can walk", "water boils at 100 °C at sea level".

If a claim is common sense, label it "true" even if the knowledge base does not mention it. In your reasoning, note that the claim is a universally known fact rather than citing a source document.

### Reasoning guidelines

Your reasoning must be written as a neutral, standalone factual explanation.

You MUST follow all rules below:

- If the claim is common sense, state that it is a universally known fact rather than citing a source document.
- You MAY use judgement phrasing such as:
  - “This can be inferred from…”
  - “This is not explicitly mentioned…”
  - “This is only partially covered…”
- Do NOT refer to the `Answer` or describe the extraction process.
- Avoid meta commentary about the evaluation process itself.
- Do NOT mention or refer to:
  - “the knowledge base"
  - “the answer”
  - “the claim”
  - “this statement” / “this excerpt” / “this sentence"
- Prefer concrete references to source documents (by name) and what they contain.
- Be concise (1–2 sentences preferred).

### Citation requirement

- If the claim can be inferred from the knowledge base, you MUST explicitly name the source document(s) where the relevant information appears. If the claim is common sense, no source citation is required.
- If the information is missing, incomplete, or more specific than what the knowledge base provides, explain what is absent or underspecified.
- A valid source citation MUST exactly match one of the document filenames shown in the delimiter: === Source Document: <filename> ===
- Filenames are VERY important and are the DEFAULT citation targets, as they refer the user to visit the correct document. Section titles, chapter names, or document descriptions alone are useful, but insufficient.
- Always enclose the filename in backticks (e.g. `guardrails.md`).


--
(For reference only):
`Question`:
{{question_text}}

`Answer`:
{{answer_text}}

--

`knowledge base`:
{{kb_documents}}

--

`claim` (Short text extracted from the full answer):
{{claim_text}}

--

### Output format

Return a valid JSON object with the following keys:

{
  "label": true,   // true = can be inferred, false = cannot be inferred or incomplete
  "reasoning": "Brief, neutral explanation grounded in the knowledge base."
}
