"""
Rubric classifying service.

Classifies custom rubrics into categories so as to assign them to the right judges.
"""

import logging
from src.common.llm import LLMClient

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"relevance", "voice", "default"}

SYSTEM_PROMPT = """You are a rubric classifier. Given a rubric name and criteria, classify it into exactly one of these categories:

- relevance: Anything related to whether the response addresses what was asked and stays on topic. This includes topicality, completeness relative to the question, specificity, helpfulness, actionability, scope appropriateness, or any rubric that evaluates whether the answer is useful and responsive to the user's actual needs.
- voice: Anything related to how the response communicates, independent of whether it is correct. This includes tone, writing style, formality level, empathy, professionalism, brand voice, personality, readability, clarity of language, politeness, verbosity, or any rubric that evaluates the manner or style of communication.
- default: Use this only when the rubric clearly does not fit any of the above two categories. Examples include formatting requirements, safety/compliance, response length constraints, structural rules, or anything related to factual accuracy or correctness.

Reply with only one word from: relevance, voice, default"""


def classify_rubric(name: str, criteria: str) -> str:
    """
    Classifies a rubric into a category.

    Args:
        name (str): The name of the rubric.
        criteria (str): The criteria/description of the rubric.

    Returns:
        str: One of: "relevance", "voice", "default"
    """
    try:
        llm_client = LLMClient()
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