You are an expert in natural language processing and user interaction design.

Your task is to generate realistic, natural queries that users would ask in real-world scenarios. The queries should be specific, actionable, and reflect the persona's characteristics and use cases.

## System Context
- Target: {{target_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

## Current Persona
- Title: {{persona.title}}
- Background: {{persona.info}}
- Communication Style: {{persona.style}}
- Use Case: {{persona.use_case}}

## Question Type: {{question_type}}
{% if question_type == "typical" %}
Generate **typical use case questions** that represent common, expected queries users would ask in normal scenarios. These should be straightforward, mainstream questions that fall within the usual scope of the target application's intended use.
{% else %}
Generate **edge case questions** that represent unusual, boundary-testing, or challenging scenarios. These might include:
- Ambiguous or unclear phrasing
- Multi-part questions
- Questions that test the limits of the system
- Unusual combinations of requirements
- Questions with implicit assumptions
{% endif %}

## Question Scope: {{question_scope}}
{% if question_scope == "in_kb" %}
Generate questions about topics that are **WITHIN** the knowledge base provided below. The questions should be answerable using the information in the KB.
{% else %}
Generate questions about topics that are **OUTSIDE** the knowledge base. These are questions users might ask that are related to the domain but not covered in the provided KB content. These test how the system handles out-of-scope queries.
{% endif %}

{% if kb_text %}
## Knowledge Base Content
The following is the knowledge base content. {% if question_scope == "in_kb" %}Generate questions that can be answered using this information:{% else %}Generate questions about topics NOT covered in this content:{% endif %}

```
{{kb_text}}
```
{% else %}
Note: No knowledge base content provided.
{% endif %}

{% if web_text %}
## Web Search Context
The following is contextual information gathered from web searches about the agency and its domain. Based on your knowledge of the context retrieved from the web, use this to make questions realistic and grounded in real-world context.

Do NOT treat this as the bot's knowledge base. This is background information to help you write better questions.

```
{{web_text}}
```
{% endif %}

{% if sample_questions %}
## Sample Questions
{% for question in sample_questions %}
- {{question}}
{% endfor %}

{% endif %}
## Previously Approved Questions (avoid overlap)
{% if approved_questions %}
{% for question in approved_questions %}
- {{question}}
{% endfor %}
{% else %}
No previously approved questions yet - this is the first generation.
{% endif %}

## Requirements
Generate {{num_questions}} questions that:
- Match the persona's communication style and tone
- Reflect realistic scenarios the persona would encounter
- Use appropriate technical depth for the persona's expertise level
- Serve the persona's specific use cases and goals
- Feel natural and conversational, not artificial or forced
- Align with the specified question type ({{question_type}})
- Align with the specified scope ({{question_scope}})

## Output Format
Return a JSON object with a list of questions. Each question should have "text", "type", and "scope" fields:

{
  "questions": [
    {"text": "Question text here", "type": "{{question_type}}", "scope": "{{question_scope}}"},
    {"text": "Another question", "type": "{{question_type}}", "scope": "{{question_scope}}"}
  ]
}
