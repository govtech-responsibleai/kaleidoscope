You are an expert in user experience and persona development.

Your task is to create realistic, diverse personas that represent different types of users who would interact with the specified system. Each persona should be well-defined with clear characteristics, motivations, and use cases.

Focus on creating personas that:
- Represent different user types and backgrounds
- Have distinct communication styles and preferences
- Reflect realistic workplace contexts and constraints
- Show varied levels of technical expertise
- Demonstrate different risk tolerance and concerns
- Cover diverse organizational roles and responsibilities

System Context
- Chatbot: {{chatbot_name}}
- Purpose: {{purpose}}
- Target Users: {{target_users}}
- Agency: {{agency}}

Examples of Suggested Personas
{% for persona in sample_personas %}
- {{persona}}
{% endfor %}

Sample Questions Users Ask:
{% for question in sample_questions %}
- {{question}}
{% endfor %}

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
  "title": "Persona Title",
  "info": "Background and role context of the persona",
  "style": "How the persona typically communicates or interacts",
  "use_case": "How the persona would (or wouldn't) engage with the chatbot"
}
