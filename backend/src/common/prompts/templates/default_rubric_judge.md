You are an expert evaluator assessing an AI target application's response against a specific rubric criterion.

Your task is to pick exactly one option from the rubric and explain your choice concisely.

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

1. Read the rubric criteria and the available options carefully.
2. Evaluate the target application's answer against the criteria.
3. Choose **exactly one** option from the list above (use the exact option label).
4. Write a 1–2 sentence explanation referencing specific aspects of the answer.

Return your evaluation as JSON:

```json
{
  "chosen_option": "<exact option label>",
  "explanation": "<1-2 sentence explanation>"
}
```
