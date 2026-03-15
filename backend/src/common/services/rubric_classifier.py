"""
Rubric classifying service.

Classifies custom rubrics into categories so as to assign them to the right judges.
"""

import logging
from src.common.llm import LLMClient

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"accuracy", "voice", "relevancy", "default"}

SYSTEM_PROMPT = """You are a rubric classifier. Given a rubric name and criteria, classify it into exactly one of these categories:

- accuracy: Anything related to the truthfulness or correctness of the information provided. This includes factual accuracy, hallucination detection, citation verification, data correctness, consistency with source material, or any rubric that evaluates whether the content is true, supported, or verifiable.
- voice: Anything related to how the response communicates, independent of whether it is correct. This includes tone, writing style, formality level, empathy, professionalism, brand voice, personality, readability, clarity of language, politeness, verbosity, or any rubric that evaluates the manner or style of communication.
- relevancy: Anything related to whether the response addresses what was asked and stays on topic. This includes topicality, completeness relative to the question, specificity, helpfulness, actionability, scope appropriateness, or any rubric that evaluates whether the answer is useful and responsive to the user's actual needs.
- default: Use this only when the rubric clearly does not fit any of the above three categories. Examples include formatting requirements, safety/compliance, response length constraints, or structural rules.

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
        llm_client = LLMClient(model="litellm_proxy/gemini-2.5-flash-lite")
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