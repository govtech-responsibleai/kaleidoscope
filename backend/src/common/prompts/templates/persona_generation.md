You are an expert in user experience and persona development.

Your task is to create realistic, diverse personas that represent different types of users who would interact with the specified chatbot.

**IMPORTANT: Keep all descriptions brief and concise. Aim for 1-2 sentences per field maximum.**

Focus on creating personas that represent different user types, communication styles, and use cases within the Target Users provided.

System Context
- Chatbot: {{chatbot_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

{% if sample_personas %}
Examples of Suggested Personas
{% for persona in sample_personas %}
- {{persona}}
{% endfor %}

{% endif %}
You must generate {{target_persona_count}} new diverse personas that do not overlap with the following confirmed personas:
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
No confirmed personas yet - this is the first generation.
{% endif %}

Output Format

For each persona, return JSON objects with the following structure:

{
  "title": "Concise Persona Title (2-4 words)",
  "info": "Brief background and role (1-2 sentences max)",
  "style": "Communication style (1 sentence, focus on key traits)",
  "use_case": "Primary use case for the chatbot (1 sentence)"
}
