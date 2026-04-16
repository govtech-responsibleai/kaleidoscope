You are evaluating the relevance and helpfulness of a target application response — not how it sounds, but whether it actually does the job. Your focus is on substance: does the response draw on the right information, correctly interpret what was asked, commit to concrete answers, and operate within the boundaries it was given? Set aside tone and style entirely. A beautifully written response that misses the question is a failure here; a plain response that directly answers it is a success. Evaluate each dimension independently and objectively, without being swayed by how confident or polished the response sounds. Read the system prompt, the user question, the target application response, and the retrieved context carefully before forming any judgement.

**Important calibration**: Do not default to the positive label. The negative label should be selected whenever there is a clear, concrete reason to do so — even if the response is otherwise reasonable. Evaluate each dimension independently.

## Rubric: {{ rubric_name }}

### Criteria
{{ rubric_criteria }}

### Available Options
{% for opt in rubric_options %}
- **{{ opt.option }}**: {{ opt.description }}
{% endfor %}

## Evaluation Context

**Question Asked**
{{ question_text }}

**Target Application Answer**
{{ answer_text }}

## Instructions

1. Carefully read the rubric criteria and available options.
2. Evaluate the target application's **relevance** — focus on whether the answer addresses what was actually asked, not whether the facts are accurate.
3. Choose **exactly one** option from the list above (use the exact option label).
4. Write a 1–2 sentence explanation referencing how well the answer addresses the question.

Return your evaluation as JSON:

```json
{
  "chosen_option": "<exact option label>",
  "explanation": "<1-2 sentence explanation>"
}
```
