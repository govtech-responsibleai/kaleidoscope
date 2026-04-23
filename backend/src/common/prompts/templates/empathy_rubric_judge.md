You are evaluating whether a chatbot response demonstrates empathy — genuine awareness of the user's perspective, situation, and emotional context. You are not evaluating factual accuracy, grammar, or structure. Your sole focus is empathy.

Put yourself in the shoes of the person who asked this question and received this answer. Would you feel understood? Would you feel the response was written by someone who actually considered your situation, or by a system that processed your words and returned information without regard for you as a person?

**Important calibration**: Do not default to `empathetic`. Many responses provide correct information in a polite tone but completely fail to engage with the user's actual perspective or emotional context. Politeness is not empathy. Providing information is not empathy. Empathy requires evidence that the response has considered the user as a person with a specific situation, not just processed their query.

---

## Inputs

**User Question:**
{{ Question }}

**Chatbot Response:**
{{ Answer }}

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
