"""
Rubric classifying service.

Classifies custom rubrics into categories so as to assign them to the right judges.
"""

import logging
from src.common.llm import LLMClient

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"accuracy", "voice", "relevancy", "default"}

SYSTEM_PROMPT = """You are a rubric classifier. Given a rubric name and criteria, classify it into exactly one of these categories:

- accuracy: factual correctness, truthfulness, hallucination avoidance, citation correctness
- voice: tone, style, brand personality, formality, empathy, communication style
- relevancy: on-topic responses, addressing the question asked, focus and conciseness
- default: anything that does not clearly fit accuracy, voice, or relevancy (e.g. formatting, safety, length)

Reply with only one word from: accuracy, voice, relevancy, default"""


def classify_rubric(name: str, criteria: str) -> str:
    """
    Classifies a rubric into a category.

    Args:
        name (str): The name of the rubric.
        criteria (str): The criteria/description of the rubric.

    Returns:
        str: One of: "accuracy", "voice", "relevancy", "default"
    """
    try:
        llm_client = LLMClient(model="gpt-5-nano")
        prompt = f"Rubric name: {name}\nCriteria: {criteria or 'No criteria provided'}"
        response = llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=5,
        )
        category = response["content"].strip().lower()
        if category not in VALID_CATEGORIES:
            logger.warning(f"Unexpected category '{category}' for rubric '{name}', falling back to 'default'")
            return "default"
        return category
    except Exception as e:
        logger.error(f"Error occurred while classifying rubric '{name}': {e}")
        return "default"