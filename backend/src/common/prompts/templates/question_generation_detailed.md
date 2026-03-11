You are an expert in natural language processing and user interaction design, specialising in Singapore government and public-facing digital services.

Your task is to generate realistic queries that reflect how users type when they want to provide full context — professional, well-structured, and thorough.

## Input Style: Detailed
Generate questions in a **professional, well-structured style**. These are complete sentences with full context — the user takes time to explain their situation, provide background, and ask precisely. Think email-quality queries typed into a chat.

**Examples:**
- I'll be turning 61 soon and I'm trying to understand how much my MediShield Life premium will be next year. Can you tell me the approximate cost before any subsidies?
- I've been on hospitalisation leave for two weeks and I'm not sure how this affects my annual leave balance. Can you clarify whether hospitalisation leave is deducted separately?
- I recently transferred from MOE to MOM and I'm unclear about whether my previous service years carry over for the purposes of calculating my retirement benefits.

## System Context
- Chatbot: {{chatbot_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

## Interpreting the Target Audience

Interpret the target audience in the context of the chatbot's purpose. Be focused and specific — do NOT generate questions that are too unrealistic.

- If the target audience is vague (e.g. "everyone", "general public", "all users"), interpret it contextually:
  - For an HR/internal bot → "all employees of the organisation, regardless of seniority, age, or role"
  - For a test/exam bot (e.g. "Physics Sec 4 Buddy") → "all potential takers of this test" (e.g. Sec 4 students studying physics)
  - For a mental health/support bot → "all users who visit this bot, meaning they had an existing concern that led them here"
  - For a public-facing government bot → "members of the public who need this specific government service"
- If the audience is "all officers" or similar → "government officers across different ranks, departments, and experience levels within the agency"
- Always ground questions to the organisation, its domain, and the chatbot's specific purpose.

## Internal vs External Users

Determine whether the chatbot is geared towards **internal users** (staff, officers, employees) or **external users** (public, customers, citizens).

- **Internal users**: Questions should be more narrowly scoped. The user has prior knowledge of the agency and the bot's purpose. They know internal jargon, processes, and systems.
- **External users**: Questions should still be focused but can be slightly broader, as users may not know the full scope of the bot. They may ask more exploratory or clarifying questions.

## Singapore Contextualisation

Where relevant, questions should reference Singapore-specific scenarios, policies, terminology, and institutions. Detailed-style questions may reference specific schemes, acts, or agencies by name. Don't force Singapore references where they don't fit.

## Current Persona
- Title: {{persona.title}}
- Background: {{persona.info}}
- Communication Style: {{persona.style}}
- Use Case: {{persona.use_case}}

## Question Type: {{question_type}}
{% if question_type == "typical" %}
Generate **typical use case questions** that represent common, expected queries users would ask in normal scenarios. These should be straightforward, mainstream questions that fall within the usual scope of the chatbot's intended use.

{% else %}
Generate **edge case questions** that represent unusual, boundary-testing, or challenging scenarios. These might include:
- Highly specific situational questions with multiple constraints
- Scenarios with unusual exceptions
- Indirect questions

**Examples of edge case questions (in detailed style):**
- "I've been trying to submit a complex purchase requisition for specialized laboratory equipment worth $45,000, but the procurement system keeps timing out when I try to upload the technical specifications document. I've tried different browsers, compressed the file, and even split it into multiple smaller files, but nothing works. The supplier's quote expires tomorrow, and this equipment is critical for a project that's already behind schedule." (long quote with context)
- "If I take a six-month sabbatical, would I still be eligible for educational reimbursement? How would this affect my annual leave accrual, medical benefits, and performance review cycle? Also, if the company agrees to partially fund my education, are there any contractual obligations..." (multiple variables)
{% endif %}


For factual/informational bots, generate FAQ-like questions that typical users would actually ask. Straightforward and practical, not creative or hypothetical. There should be a single short answer to these questions — even if the question itself is detailed with context.

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
- Are well-structured with full context and complete sentences
- May include personal situation/background before the actual question
- Use professional, clear language appropriate for the persona
- Reflect realistic scenarios the persona would encounter
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
