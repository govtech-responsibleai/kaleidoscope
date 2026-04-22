"""
LLM-powered judge prompt generator for custom rubrics.

Takes a rubric definition (name, criteria, options, best_option) and uses an LLM
to generate a complete, ready-to-use judge evaluation prompt.
"""

import logging
from src.common.llm import LLMClient
from src.rubric.services.prompt_files import write_custom_rubric_prompt

logger = logging.getLogger(__name__)

AUGMENTER_MODEL = "litellm_proxy/gemini-3.1-pro-preview-global"

AUGMENTATION_PROMPT = """\
You are a prompt engineer specialising in LLM-as-judge evaluation prompts. Your task is to take a rubric definition for a single evaluation dimension and produce a complete, ready-to-use judge prompt.

## Context

A judge LLM will use the prompt you generate to evaluate chatbot responses across a dataset. The chatbot responses are from Singapore government AI assistants covering topics like driving regulations, housing policy, and career advice. The chatbots have varied personas defined in their system prompts (e.g., strict tutor, friendly advisor, formal specialist).

The judge will receive structured inputs and must output a binary classification label plus a brief justification.

## What you will receive

A rubric definition for ONE evaluation dimension. It will include:
- The dimension name
- The two classification labels
- A description of what the dimension measures (ranging from a brief phrase to detailed criteria with examples, depending on the rubric complexity level)

## What you must produce

A complete judge prompt in markdown that follows this exact structure:

### Required structure

1. **Opening paragraph** — 2-3 sentences establishing the judge's role and sole focus on this dimension. Explicitly state what the judge is NOT evaluating (other dimensions). Frame the evaluation from the perspective of a real person reading the response.

2. **Calibration note** — A bold `**Important calibration**` paragraph warning against defaulting to the positive label. Identify the most common false-positive pattern for this dimension (the thing that looks like it passes but actually doesn't). Be specific to the dimension.

3. **Inputs section** — Must include these exact template variables:
```
## Inputs

**User Question:**
{{{{ Question }}}}

**Chatbot Response:**
{{{{ Answer }}}}
```

4. **Task section with reasoning scaffold** — Before the judge assigns a label, require a 2-3 step reasoning process in their comments. The steps should be specific to the dimension (not generic). Each step should force the judge to observe something concrete about the response before deciding.

5. **Label definitions** — Use the exact label names from the rubric. For each label:
   - The positive label: describe what the response DOES, framed as observable criteria. Use "Select this when" followed by bullet points.
   - The negative label: describe specific failure patterns, framed as "Select this if **any** of the following apply" followed by bullet points. Aim for 4-7 concrete, observable failure conditions.

6. **Additional guidance** — 3-5 bullet points addressing edge cases and common misclassification patterns for this dimension. Each should follow the pattern: **Bold principle** followed by a one-sentence explanation. Must include:
   - A "X ≠ Y" distinction (the most common confusion for this dimension)
   - Guidance on how the system prompt persona affects evaluation
   - Guidance on assessing the response holistically

7. **Comments field** — A comments field for the dimension asking for 1-2 sentences referencing a concrete part of the response.

8. **Other Comments** — `**Other Comments:** Any additional observations or edge cases not captured above.`

## Quality guidelines (based on what has worked in prior experiments)

- **Be specific over generic.** Name concrete, observable failure patterns rather than vague descriptions. "The response repeats the same point in different words across multiple paragraphs" is better than "the response has issues."
- **Do NOT include calibration examples.** In prior experiments, inline examples caused judges to anchor on the examples rather than applying the criteria. Describe what to look for, but do not show example Q&A pairs.
- **Do NOT include a "when in doubt, lean toward X" tiebreaker.** This consistently caused overcorrection in prior experiments. Let the criteria speak for themselves.
- **Keep it focused.** The prompt should evaluate exactly one dimension. Do not let adjacent dimensions creep in.
- **The reasoning scaffold matters.** The pre-label reasoning steps should force the judge to make a concrete observation about the response before committing to a label. Generic steps like "read the response carefully" are useless. Dimension-specific steps like "identify whether the response addresses each part of the user's question" are useful.
- **Frame the negative label around observable behaviors, not subjective impressions.** "The response includes three paragraphs of background before answering" is better than "the response feels long."

## Output format

Output ONLY the judge prompt in markdown. No preamble, no explanation, no code fences wrapping the entire output. Start directly with the opening paragraph.

---

## Rubric definition

{rubric}
"""


def build_fallback_judge_prompt(name: str, criteria: str, options: list[dict], best_option: str) -> str:
    """
    Build a basic judge prompt from the rubric definition without calling an LLM.
    Used when the LLM augmenter fails or returns invalid output.
    The returned string is a Jinja2 template (uses {{ var }} syntax).
    """
    options_text = "\n".join(
        f"- **{opt.get('option', '') if isinstance(opt, dict) else opt.option}**: "
        f"{opt.get('description', '') if isinstance(opt, dict) else opt.description}"
        for opt in options
    )
    lines = [
        f"You are evaluating a chatbot response against a specific rubric criterion."
        f" Your sole focus is **{name}** — do not evaluate accuracy, tone, or any other dimension.",
        "",
        f"**Criteria:** {criteria}",
        "",
        "---",
        "",
        "## Inputs",
        "",
        "**User Question:**",
        "{{ Question }}",
        "",
        "**Chatbot Response:**",
        "{{ Answer }}",
        "",
        "---",
        "",
        "## Task",
        "",
        f"Evaluate the chatbot response on **{name}** using the options below."
        " Choose exactly one option and explain your reasoning in 1-2 sentences referencing the response.",
        "",
        f"### {name}",
        "",
        options_text,
        "",
        f"**{name} Comments:** In 1-2 sentences, explain what specific aspect of the response led to your label.",
        "",
        "---",
        "",
        "**Other Comments:** Any additional observations or edge cases not captured above.",
    ]
    return "\n".join(lines)


def _is_valid_judge_prompt(prompt: str) -> bool:
    """Check that an LLM-generated judge prompt has the expected structure."""
    if not prompt or len(prompt) < 200:
        return False
    # Must contain the inputs section with the core template variables
    required = ["{{ Question }}", "{{ Answer }}"]
    return all(var in prompt for var in required)


def _format_rubric_definition(name: str, criteria: str, options: list[dict], best_option: str) -> str:
    """Format rubric fields into a text block for the augmenter prompt."""
    lines = [f"**Dimension:** {name}"]
    if criteria:
        lines.append(f"**Criteria:** {criteria}")
    lines.append(f"**Positive label (ideal outcome):** {best_option}")
    for opt in options:
        opt_name = opt.get("option", "") if isinstance(opt, dict) else opt.option
        opt_desc = opt.get("description", "") if isinstance(opt, dict) else opt.description
        lines.append(f"- **{opt_name}**: {opt_desc}")
    return "\n".join(lines)


def generate_judge_prompt(name: str, criteria: str, options: list[dict], best_option: str) -> str:
    """
    Generate a complete judge evaluation prompt from a rubric definition.

    Args:
        name: Rubric dimension name
        criteria: What the rubric measures
        options: List of {option, description} dicts
        best_option: The positive/ideal option label

    Returns:
        Complete judge prompt as markdown string

    Raises:
        Exception: If the LLM call fails
    """
    rubric_text = _format_rubric_definition(name, criteria, options, best_option)
    prompt = AUGMENTATION_PROMPT.format(rubric=rubric_text)

    llm_client = LLMClient(model=AUGMENTER_MODEL)
    response = llm_client.generate(
        prompt=prompt,
        temperature=0.3,
        timeout=60,
    )

    judge_prompt = response["content"].strip()
    if not _is_valid_judge_prompt(judge_prompt):
        logger.warning(f"LLM-generated judge prompt for '{name}' failed validation (len={len(judge_prompt)}), using fallback")
        return build_fallback_judge_prompt(name, criteria, options, best_option)
    logger.info(f"Generated judge prompt for rubric '{name}' ({len(judge_prompt)} chars)")
    return judge_prompt


def materialize_custom_judge_prompt(rubric_id: int, prompt_text: str) -> str:
    """Write one generated custom rubric prompt to the managed template-file location."""
    return write_custom_rubric_prompt(rubric_id, prompt_text)
