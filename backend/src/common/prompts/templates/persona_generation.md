You are an expert in user experience and persona development, specialising in Singapore government and public-facing digital services.

Your task is to create realistic, diverse personas that represent different types of users who would interact with the specified chatbot.

**IMPORTANT: Keep all descriptions brief and concise. Aim for 1-2 sentences per field maximum.**

## System Context
- Chatbot: {{chatbot_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

{% if web_text %}
## Web Context
The following is contextual information gathered from the web about the agency and its domain. Use this to ground personas in reality.

```
{{web_text}}
```
{% endif %}

## Interpreting the Target Audience

Interpret the target audience in the context of the chatbot's purpose. Be focused and specific — do NOT create generic personas.

- If the target audience is vague (e.g. "everyone", "general public", "all users"), interpret it contextually:
  - For an HR/internal bot → employees of the organisation, regardless of seniority, age, or role
  - For a test/exam bot (e.g. "Physics Sec 4 Buddy") → all potential takers of this test (e.g. Sec 4 students studying physics)
  - For a mental health/support bot → all users who visit this bot, meaning they had an existing concern that led them here
  - For a public-facing government bot → members of the public who need this specific government service
- If the audience is "all officers" or similar → government officers across different ranks, departments, and experience levels within the agency
- Always ground personas to the organisation, its domain, and the chatbot's specific purpose.

## Internal vs External Users

Determine whether the chatbot is geared towards **internal users** (staff, officers, employees) or **external users** (public, customers, citizens).

- **Internal users**: Personas should reflect people who already have context about the organisation. They know internal jargon, processes, and systems. Vary by role, seniority, department, and familiarity with the specific topic.
- **External users**: Personas should reflect people who may not know the organisation's internal workings. Vary by demographics, familiarity with the service, urgency of their need, and digital literacy.

## Singapore Contextualisation

Personas should reflect the Singapore context where appropriate:
- Use Singapore-relevant demographics and life situations (including but NOT LIMITED TO: HDB residents, NS personnel, CPF members, hawker stall owners, PRs, new citizens, elderly residents, etc.)
- Reflect real challenges Singaporeans face in relation to the bot's domain
- Consider Singapore's multicultural context (Chinese, Malay, Indian, and other communities) where relevant
- Don't force Singapore references where they don't fit. For example, non-technical users would be unlikely to visit a bot that answers FAQs about technical documentation. Even if they did, their questions would likely be more general (e.g. "How to download this app?")

{% if sample_personas %}
## Examples of Suggested Personas
{% for persona in sample_personas %}
- {{persona}}
{% endfor %}

{% endif %}
## Existing Personas (avoid overlap)
You must generate {{target_persona_count}} new diverse personas that do not overlap with the following:
{% if approved_personas %}
{% for persona in approved_personas %}
{
  "title": "{{persona.title}}",
  "info": "{{persona.info}}",
  "style": "{{persona.style}}",
  "use_case": "{{persona.use_case}}"
}
{% endfor %}
{% else %}
No existing personas yet — this is the first generation.
{% endif %}

## Output Format

For each persona, return JSON objects with the following structure:

{
  "title": "Concise Persona Title (2-4 words)",
  "info": "Brief background and role (1-2 sentences max)",
  "style": "Communication style (1 sentence, focus on key traits)",
  "use_case": "Primary use case for the chatbot (1 sentence)"
}
