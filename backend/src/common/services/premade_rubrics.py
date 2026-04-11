"""
Registry of pre-made rubric templates that users can add to their targets.

Add new templates to PREMADE_RUBRIC_TEMPLATES to make them available.
Each entry must include: name, criteria, options, best_option, judge_prompt, recommended_model.
"""

from typing import Optional


PREMADE_RUBRIC_TEMPLATES: dict[str, dict] = {
    "empathy": {
        "name": "Empathy",
        "criteria": "Does the response demonstrate empathy and emotional awareness appropriate to the user's situation?",
        "options": [
            {"option": "Empathetic", "description": "The response acknowledges the user's situation and demonstrates appropriate emotional awareness."},
            {"option": "Not Empathetic", "description": "The response is impersonal, dismissive, or fails to acknowledge the user's emotional context."},
        ],
        "best_option": "Empathetic",
        "judge_prompt": """You are evaluating whether a chatbot response demonstrates empathy — genuine awareness of the user's perspective, situation, and emotional context. You are not evaluating factual accuracy, grammar, or structure. Your sole focus is empathy.

Put yourself in the shoes of the person who asked this question and received this answer. Would you feel understood? Would you feel the response was written by someone who actually considered your situation, or by a system that processed your words and returned information without regard for you as a person?

**Important calibration**: Do not default to `empathetic`. Many responses provide correct information in a polite tone but completely fail to engage with the user's actual perspective or emotional context. Politeness is not empathy. Providing information is not empathy. Empathy requires evidence that the response has considered the user as a person with a specific situation, not just processed their query.

---

## Inputs

**System Prompt:**
{{ System_Prompt_Cleaned }}

**User Question:**
{{ Question }}

**Chatbot Response:**
{{ Answer }}

**Citations:**
{{ All_Citations }}

---

## Task

Evaluate the chatbot response on empathy using the criteria below. First, consider the user's question carefully:

1. **What is the user actually asking, and why might they be asking it?** Consider the underlying concern, not just the surface question. A question about tax implications may stem from financial anxiety. A question about rules may stem from fear of getting in trouble.
2. **Does the user's question carry any emotional or personal dimension?** Look for signals: uncertainty ("I'm not sure if..."), worry ("what happens if..."), frustration, personal stakes, or vulnerability.
3. **Does the chatbot response show awareness of what you identified in steps 1 and 2?**

Then assign the label.

---

### Empathy

Does the response show genuine awareness of the user's perspective, situation, and emotional context?

- `Empathetic` — The response demonstrates that it has considered the user's situation, not just their words. Select this label when the response does **at least one** of the following in a way that feels genuine rather than formulaic:
  - Acknowledges the user's underlying concern, uncertainty, or emotional state — not just the literal question.
  - Matches the appropriate emotional register for the situation (e.g., reassuring when the user is worried, direct when the user wants a straight answer, warm when the user is new or uncertain).
  - Frames information in a way that shows awareness of the user's specific circumstances rather than delivering a generic answer.
  - Makes the user feel heard — the response reads as though it was written *for this person*, not pasted from a template.

- `Not Empathetic` — Select this if **any** of the following apply:
  - The user expressed uncertainty, worry, frustration, or personal stakes, and the response ignores this entirely — jumping straight to information without any acknowledgement.
  - The response is cold, mechanical, or purely transactional when the question has a clear emotional or personal dimension.
  - The response is condescending, dismissive, or belittling toward the user's question or situation (e.g., mocking the user for not knowing something, treating a reasonable question as foolish).
  - The response is technically correct but completely misses what the user clearly cared about — answering the letter of the question while ignoring its spirit.
  - The tone is noticeably mismatched with the user's emotional register (e.g., an overly formal, detached reply to someone who is clearly stressed or confused; an inappropriately casual reply to a serious concern).
  - The response uses generic filler empathy (e.g., "Great question!" or "I understand your concern") but then proceeds to show no actual understanding of the user's specific situation.
  - The response lectures, scolds, or moralises when the user asked a straightforward question.

**Key distinctions to keep in mind:**

- **Politeness ≠ Empathy.** A response can be perfectly polite and well-formatted but still fail to engage with the user's perspective. If it reads like a form letter that could be sent to anyone, it is not empathetic regardless of how pleasant the language is.
- **Not every question demands emotional empathy.** For purely factual, low-stakes questions with no emotional dimension (e.g., "What are the opening hours?"), a clear and direct answer *is* the empathetic response — the user just wants information. Do not penalise responses for being direct when directness is what the situation calls for. Conversely, do not reward responses with unnecessary emotional language when the user simply wanted a fact.
- **Consider the system prompt persona.** The chatbot may have been given a specific personality (e.g., strict, formal, casual). A response can be empathetic within the bounds of its persona — a strict tutor who firmly but fairly addresses a student's concern is still empathetic. However, the persona does not excuse genuine dismissiveness, cruelty, or contempt toward the user.
- **Assess the response as a whole.** A response that starts empathetically but becomes dismissive halfway through, or one that acknowledges the user's feelings but then ignores them in its actual advice, should be evaluated based on the overall experience.

**Empathy Comments:** In 1-2 sentences, explain what specific aspect of the response led to your label. Reference a concrete part of the response (a phrase, framing choice, or omission) rather than making a general statement.

---

**Other Comments:** Any additional observations or edge cases not captured above.
""",
        "recommended_model": "litellm_proxy/gemini-3-flash-preview",
    },
    "verbosity": {
        "name": "Verbosity",
        "criteria": "Is the response appropriately concise, or does it include unnecessary repetition, filler, or excessive detail?",
        "options": [
            {"option": "Concise", "description": "The response is appropriately sized for the question, without unnecessary repetition or filler."},
            {"option": "Verbose", "description": "The response includes unnecessary repetition, filler, or excessive detail beyond what was asked."},
        ],
        "best_option": "Concise",
        "judge_prompt": """
You are evaluating whether a chatbot response is appropriately sized for the question it answers. You are not evaluating accuracy, tone, empathy, or structure. Your sole focus is whether the response length is well-calibrated — does it say what needs to be said without padding, repetition, or unnecessary material?

Read the user's question first. Consider: how complex is this question? How many distinct parts does it have? What would a well-calibrated answer look like in terms of depth and coverage? Then read the response and ask: is there material here that does not serve the user, or is material missing that the user would need?

**Important calibration**: LLM-generated responses are systematically too long. They pad with preamble, restate the question, repeat points in different words, add unnecessary caveats, and continue past the point where the question has been answered. These patterns are so common that they can feel normal — but a human reviewer would notice the padding. Do not normalise verbosity just because it is common. Read critically.

**When the decision is close, lean toward `Verbose`.** Most responses in this dataset are generated by LLMs, which have a well-documented tendency to over-explain. A response must earn the `Concise` label by being genuinely well-calibrated, not by being "not egregiously long."

---

## Inputs

**System Prompt:**
{{ System_Prompt_Cleaned }}

**User Question:**
{{ Question }}

**Chatbot Response:**
{{ Answer }}

**Citations:**
{{ All_Citations }}

---

## Task

Evaluate the chatbot response on verbosity/conciseness using the criteria below. Before assigning a label, work through these steps in your Verbosity/Conciseness Comments:

1. **Question complexity** — In one sentence, characterise the question: is it simple and factual (one clear answer), moderately complex (a few related parts), or genuinely complex (multiple distinct sub-questions or requires nuanced explanation)? This sets your baseline for what an appropriate response length looks like.
2. **Response audit** — Scan the response for padding. Specifically check for: preamble before the answer starts, restatement of the question, repeated points, tangential information, filler phrases, excessive caveats/disclaimers, and content that continues after the question has been fully answered. Note what you find.
3. **Label** — Based on steps 1 and 2, assign your label.

---

### Verbosity/Conciseness

Is the response length well-calibrated for what the question actually requires?

- `Concise` — The response covers everything the user needs and nothing they don't. Every paragraph and section earns its place. Length is proportionate to the complexity of the question. Select this label only when:
  - The response gets to the answer without unnecessary preamble or lead-in.
  - Each point is made once, clearly, without being restated in different words elsewhere in the response.
  - The response does not include caveats, disclaimers, or tangential information that does not help the user answer their question or make a decision.
  - The response stops when the question has been fully answered — it does not trail off into loosely related information.
  - For complex, multi-part questions: the response is thorough enough that the user does not need to ask a follow-up to fill obvious gaps.

- `Verbose` — Select this if **any** of the following apply:
  - **Preamble padding** — The response includes a lengthy opening before getting to the actual answer (e.g., restating the question back, thanking the user at length, providing background context the user did not ask for, or narrating what the response will cover before covering it).
  - **Repetition** — The same point, fact, or advice appears in different words across multiple sentences, paragraphs, or sections. If you can delete a sentence and lose no information, the response is repetitive.
  - **Filler phrases** — The response is padded with phrases that add no information: "That's a great question", "Let me break this down for you", "I hope this helps", "In summary" followed by restating everything already said.
  - **Excessive caveats and disclaimers** — Multiple sentences warning the user to "consult a professional", "check official sources", or "note that this may vary" when one such note would suffice, or when the caveat is not relevant to the question.
  - **Tangential information** — The response includes material that is loosely related to the topic but does not answer the user's actual question. Information the user did not ask for and would not obviously need.
  - **Over-answering** — The response continues well past the point where the question has been fully addressed, adding supplementary information, edge cases, or related topics the user did not ask about.
  - **Under-answering** — Conversely, the response is so brief that it clearly omits information the user would need. A one-line answer to a multi-part question, or a response that answers only part of what was asked, leaving obvious gaps. Brevity that forces the user to ask a follow-up for information that should have been included.

**Additional guidance:**

- **Length alone does not determine the label.** A long response to a genuinely complex, multi-part question can be `concise` if every part earns its place. A short response to a simple question can be `verbose` if it pads a one-sentence answer with filler. Evaluate proportionality, not absolute length.
- **Apply the deletion test.** For any section or sentence you are unsure about, ask: "If I deleted this, would the user lose anything they actually need?" If the answer is no, it is padding.
- **Watch for structured padding.** Bullet points and headers can create an illusion of conciseness. A response that breaks a simple answer into five bullet points with a header and a summary paragraph is verbose, not well-structured. Formatting does not excuse unnecessary content.
- **Consider the system prompt persona.** If the system prompt instructs the chatbot to be thorough, detailed, or comprehensive, allow somewhat more length — but the content must still be relevant and non-repetitive. A persona instruction does not excuse padding or repetition.
- **"I am an AI" disclaimers count as padding** if they are lengthy or repeated. A brief one-line disclaimer is acceptable; a multi-sentence paragraph about AI limitations before answering the question is preamble padding.

**Verbosity/Conciseness Comments:** Follow the 3-step process above. In 2-3 sentences, cover: (1) the question's complexity, (2) specific padding or gaps you identified (or their absence), and (3) your label.

---

**Other Comments:** Any additional observations or edge cases not captured above.
""",
        "recommended_model": "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    },
}


def list_premade_templates() -> list[dict]:
    """Return summary info for all pre-made templates (excludes judge_prompt)."""
    return [
        {
            "key": key,
            "name": tmpl["name"],
            "criteria": tmpl["criteria"],
            "options": tmpl["options"],
            "best_option": tmpl["best_option"],
            "recommended_model": tmpl["recommended_model"],
        }
        for key, tmpl in PREMADE_RUBRIC_TEMPLATES.items()
    ]


def get_premade_template(key: str) -> Optional[dict]:
    """Return the full template including judge_prompt, or None if not found."""
    return PREMADE_RUBRIC_TEMPLATES.get(key)
