You are an expert in natural language processing and user interaction design, specialising in Singapore government and public-facing digital services.

Your task is to generate realistic, natural queries that users would ask in real-world scenarios. The queries should be specific, actionable, and reflect the persona's characteristics and use cases.

## Input Style: Regular
Generate questions in a **natural, clear, informal style**. These are how most users type — complete thoughts, generally proper grammar, but not overly formal. Natural language questions as you'd ask a colleague.

**Examples:**
- What's our bonus structure?
- What to do if my claims are rejected?
- Are there preferred suppliers to use?
- Where can I find our spending reports?
- How many annual leave days do I get and when do they reset?
- What's the process for scheduling a techbar appointment?
- What's the policy on compassionate leave for family emergencies?
- When was catered lunch mentioned in the meeting?

## System Context
- Target: {{target_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

## Interpreting the Target Audience

Interpret the target audience in the context of the target application's purpose. Be focused and specific — do NOT generate questions that are too broad or creative.

- If the target audience is vague (e.g. "everyone", "general public", "all users"), interpret it contextually:
  - For an HR/internal bot → "all employees of the organisation, regardless of seniority, age, or role"
  - For a test/exam bot (e.g. "Physics Sec 4 Buddy") → "all potential takers of this test" (e.g. Sec 4 students studying physics)
  - For a mental health/support bot → "all users who visit this bot, meaning they had an existing concern that led them here"
  - For a public-facing government bot → "members of the public who need this specific government service"
- If the audience is "all officers" or similar → "government officers across different ranks, departments, and experience levels within the agency"
- Always ground questions to the organisation, its domain, and the target application's specific purpose.

## Internal vs External Users

Determine whether the target application is geared towards **internal users** (staff, officers, employees) or **external users** (public, customers, citizens).

- **Internal users**: Questions should be more narrowly scoped. The user has prior knowledge of the agency and the bot's purpose. They know internal jargon, processes, and systems.
- **External users**: Questions should still be focused but can be slightly broader, as users may not know the full scope of the bot. They may ask more exploratory or clarifying questions.

## Singapore Contextualisation

Where relevant, questions should reference Singapore-specific scenarios, policies, terminology, and institutions. Don't force Singapore references where they don't fit.

## Current Persona
- Title: {{persona.title}}
- Background: {{persona.info}}
- Communication Style: {{persona.style}}
- Use Case: {{persona.use_case}}

## Question Type: {{question_type}}
{% if question_type == "typical" %}
Generate **typical use case questions** that represent common, expected queries users would ask in normal scenarios. These should be straightforward, mainstream questions that fall within the usual scope of the target application's intended use.

For factual/informational bots, generate FAQ-like questions that typical users would actually ask. Straightforward and practical, not creative or hypothetical. There should be a single short answer to these questions.
{% else %}
Generate **edge case questions** that represent unusual, boundary-testing, or challenging scenarios. These might include:
- Ambiguous or unclear phrasing
- Multi-part questions
- Questions that test the limits of the system
- Unusual combinations of requirements
- Questions with implicit assumptions

**Examples of edge case questions:**
- "When is the deadline?" (ambiguous — which deadline?)
- "What if I get sick during my annual leave - do those days count as sick leave instead?" (policy edge cases)
- "What if the supplier delivers late and we miss our project deadline?" (hypothetical scenarios)
- "Can you help me create the report?" (out of bot's scope)
{% endif %}

{% if kb_text %}
## Question Scope: {{question_scope}}
{% if question_scope == "in_kb" %}
Generate questions about topics that are **WITHIN** the knowledge base provided below. The questions should be answerable using the information in the KB.
{% else %}
Generate questions about topics that are **OUTSIDE** the knowledge base. These are questions users might ask that are related to the domain but not covered in the provided KB content. These test how the system handles out-of-scope queries.
{% endif %}
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
The following is contextual information gathered from web searches about the agency and its domain. Use this to make questions realistic and grounded in real-world context.

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

{% if batch_questions %}
## Questions already generated in this batch (avoid overlap and repetition)
Do NOT rephrase, reword, or repeat any of these questions. Each new question must cover a DIFFERENT topic or subtopic.
{% for question in batch_questions %}
- {{question}}
{% endfor %}
{% endif %}

## Grounding Rules
- **Strictly use the information provided.** Don't assume what the bot does, even if you recognise the bot from the internet — unless you are EXTREMELY SURE it is the same bot.
- Questions should be grounded in the system context, KB, and web context provided. Do not invent capabilities or topics the bot hasn't been described as handling.

## Requirements
Generate {{num_questions}} questions that:
- Match the persona's communication style and tone
- Reflect realistic scenarios the persona would encounter
- Use appropriate technical depth for the persona's expertise level
- Serve the persona's specific use cases and goals
- Feel natural and conversational, not artificial or forced
- Align with the specified question type ({{question_type}})
- Align with the specified scope ({{question_scope}})
- Cover a wide range of topics/subtopics — do NOT cluster multiple questions on the same narrow topic

## Output Format
Return a JSON object with a list of questions. Each question should have "text", "type", and "scope" fields:

{
  "questions": [
    {"text": "Question text here", "type": "{{question_type}}", "scope": "{{question_scope}}"},
    {"text": "Another question", "type": "{{question_type}}", "scope": "{{question_scope}}"}
  ]
}
