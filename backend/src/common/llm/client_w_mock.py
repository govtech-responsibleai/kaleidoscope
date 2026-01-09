"""
LLM client wrapper using LiteLLM.

Provides a unified interface for calling different LLM providers
with automatic retry, error handling, and token tracking.
"""
import logging
from typing import Dict, List, Optional, Any, Type, TypeVar
from pydantic import BaseModel
import litellm

import dotenv
dotenv.load_dotenv()

from src.common.config import get_settings, MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE

# litellm.callbacks = ["arize_phoenix"] # See https://docs.litellm.ai/docs/observability/phoenix_integration
settings = get_settings()
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Configure LiteLLM
litellm.set_verbose = False  # Set to True for debugging

class LLMClient:
    """Client for making LLM API calls using LiteLLM."""

    def __init__(self, model: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            model: Model name (e.g., "gpt-4o-mini", "claude-3-5-sonnet-20241022")
                   Defaults to settings.default_llm_model
        """
        self.model = model or settings.default_llm_model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Response format (e.g., {"type": "json_object"})
            **kwargs: Additional arguments passed to litellm.completion()

        Returns:
            Dict containing:
                - content: Generated text
                - prompt_tokens: Number of prompt tokens
                - completion_tokens: Number of completion tokens
                - total_tokens: Total tokens used
                - model: Model used
                - cost: Estimated cost in USD

        Raises:
            Exception: If API call fails after retries
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Check if model forces temperature params (e.g. for reasoning)
        if [keyword in self.model for keyword in MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE]:
            temperature = 1.0

        try:
            logger.info(f"Calling {self.model} with {len(prompt)} char prompt")

            response = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                **kwargs
            )

            # Extract response data
            content = response.choices[0].message.content
            usage = response.usage

            result = {
                "content": content,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "model": response.model,
            }

            # Calculate cost using LiteLLM's built-in cost tracking
            try:
                cost = litellm.completion_cost(completion_response=response)
                result["cost"] = cost
            except Exception as e:
                logger.warning(f"Failed to calculate cost: {e}")
                result["cost"] = 0.0

            logger.info(
                f"✓ Generated {usage.completion_tokens} tokens "
                f"(total: {usage.total_tokens}, cost: ${result['cost']:.4f})"
            )

            return result

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate JSON completion from LLM.

        Automatically sets response_format to JSON mode.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments

        Returns:
            Dict containing the response (same as generate())
        """
        return self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> tuple[T, Dict[str, Any]]:
        """
        Generate structured output from LLM using Pydantic models.

        This method enforces that the LLM output conforms to the provided Pydantic model schema,
        ensuring consistent and validated responses.

        Args:
            prompt: User prompt
            response_model: Pydantic model class defining the expected output structure
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments

        Returns:
            Tuple of (parsed_model_instance, metadata_dict) where:
                - parsed_model_instance: Validated Pydantic model instance
                - metadata_dict: Dict with prompt_tokens, completion_tokens, total_tokens, model, cost

        Raises:
            Exception: If API call fails or response doesn't match schema
        """
        # Add schema to prompt to guide the LLM
        schema_prompt = f"{prompt}\n\nRespond with JSON matching this schema:\n{response_model.model_json_schema()}"

        # MOCK temporarily - uncomment below for real LLM calls
        # Generate with JSON mode
        response = self.generate_json(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Parse and validate response against Pydantic model
        try:
            import json
            content_json = json.loads(response["content"])
            parsed_model = response_model.model_validate(content_json)

            # Return model instance and metadata separately
            metadata = {
                "prompt_tokens": response["prompt_tokens"],
                "completion_tokens": response["completion_tokens"],
                "total_tokens": response["total_tokens"],
                "model": response["model"],
                "cost": response["cost"],
            }

            return parsed_model, metadata

        except Exception as e:
            logger.error(f"Failed to parse LLM response into {response_model.__name__}: {e}")
            logger.error(f"Response content: {response.get('content', '')[:500]}")
            raise ValueError(f"LLM response doesn't match expected schema: {e}")
        
        # # MMMOCK RESPONSE
        # from src.common.models import (
        #     CheckworthyResult, ClaimJudgmentResult, ResponseJudgmentResult,
        #     PersonaListOutput, PersonaBase, QuestionListOutput, QuestionBase
        # )

        # if response_model == CheckworthyResult:
        #     parsed_model = CheckworthyResult(
        #         checkworthy=True,
        #         reasoning="This is a factual claim that can be verified."
        #     )
        # elif response_model == ClaimJudgmentResult:
        #     parsed_model = ClaimJudgmentResult(
        #         label=True,
        #         reasoning="This claim is supported by the knowledge base."
        #     )
        # elif response_model == ResponseJudgmentResult:
        #     parsed_model = ResponseJudgmentResult(
        #         label=True,
        #         reasoning="The response is overall accurate and well-supported."
        #     )
        # elif response_model == PersonaListOutput:
        #     parsed_model = PersonaListOutput(
        #         personas=[
        #             PersonaBase(
        #                 title="Tech-Savvy User",
        #                 info="Early adopter interested in new technology",
        #                 style="Direct and concise",
        #                 use_case="Exploring advanced features"
        #             )
        #         ]
        #     )
        # elif response_model == QuestionListOutput:
        #     parsed_model = QuestionListOutput(
        #         questions=[
        #             QuestionBase(
        #                 text="What is the main purpose of this service?",
        #                 type="typical",
        #                 scope="in_kb"
        #             )
        #         ]
        #     )
        # else:
        #     raise ValueError(f"Unknown response_model for mock: {response_model.__name__}")

        # metadata = {
        #     "prompt_tokens": 100,
        #     "completion_tokens": 100,
        #     "total_tokens": 200,
        #     "model": "mock-lm",
        #     "cost": 0.0002
        # }

        return parsed_model, metadata

    async def generate_structured_async(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> tuple[T, Dict[str, Any]]:
        """
        Generate structured output from LLM using Pydantic models (async version).

        This is the async version of generate_structured() for use with asyncio.
        Use this when you need to make multiple LLM calls concurrently.

        Args:
            prompt: User prompt
            response_model: Pydantic model class defining the expected output structure
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments

        Returns:
            Tuple of (parsed_model_instance, metadata_dict) where:
                - parsed_model_instance: Validated Pydantic model instance
                - metadata_dict: Dict with prompt_tokens, completion_tokens, total_tokens, model, cost

        Raises:
            Exception: If API call fails or response doesn't match schema
        """
        # Add schema to prompt to guide the LLM
        schema_prompt = f"{prompt}\n\nRespond with JSON matching this schema:\n{response_model.model_json_schema()}"

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": schema_prompt})

        # Check if model forces temperature params (e.g. for reasoning)
        if [keyword in self.model for keyword in MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE]:
            temperature = 1.0
            
        try:
            logger.info(f"Calling {self.model} (async) with {len(schema_prompt)} char prompt")

            # MOCK temporarily - uncomment below for real LLM calls
            # Call async LLM with JSON mode
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **kwargs
            )

            # Extract response data
            content = response.choices[0].message.content
            usage = response.usage

            # Calculate cost using LiteLLM's built-in cost tracking
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception as e:
                logger.warning(f"Failed to calculate cost: {e}")
                cost = 0.0

            logger.info(
                f"✓ Generated {usage.completion_tokens} tokens "
                f"(total: {usage.total_tokens}, cost: ${cost:.4f})"
            )

            # Parse and validate response against Pydantic model
            import json
            content_json = json.loads(content)
            parsed_model = response_model.model_validate(content_json)

            # Return model instance and metadata separately
            metadata = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "model": response.model,
                "cost": cost,
            }

            return parsed_model, metadata

            # # MMMOCK RESPONSE - Replace with appropriate data based on response_model
            
            # import time
            # import random 

            # label = random.choices([True, False], weights=[0.8, 0.2])[0]
            # time.sleep((1 + int(label))/1) # 1s if False, 2s if True
            
            # from src.common.models import CheckworthyResult, ClaimJudgmentResult, ResponseJudgmentResult

            # if response_model == CheckworthyResult:
            #     parsed_model = CheckworthyResult(
            #         checkworthy=label,
            #         reasoning="This is a factual claim that can be verified."
            #     )
            # elif response_model == ClaimJudgmentResult:
            #     parsed_model = ClaimJudgmentResult(
            #         label=label,
            #         reasoning="This claim is supported by the knowledge base."
            #     )
            # elif response_model == ResponseJudgmentResult:
            #     parsed_model = ResponseJudgmentResult(
            #         label=label,
            #         reasoning="The response is overall accurate and well-supported."
            #     )
            # else:
            #     # Default mock for unknown models
            #     raise ValueError(f"Unknown response_model for mock: {response_model.__name__}")

            # metadata = {
            #     "prompt_tokens": 100,
            #     "completion_tokens": 100,
            #     "total_tokens": 200,
            #     "model": "mock-lm",
            #     "cost": 0.0002
            # }

            return parsed_model, metadata

        except Exception as e:
            logger.error(f"Async LLM generation failed for {response_model.__name__}: {e}")
            raise ValueError(f"LLM response doesn't match expected schema: {e}")

    def batch_generate(
        self,
        prompts: List[str],
        mode: str = "text",
        response_model: Optional[Type[T]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> List[Any]:
        """
        Generate completions for multiple prompts.

        Supports three modes:
        - "text": Regular text generation (returns List[Dict])
        - "json": JSON generation (returns List[Dict])
        - "structured": Structured output with Pydantic validation (returns List[Tuple[Model, Dict]])

        Args:
            prompts: List of user prompts
            mode: Generation mode - "text", "json", or "structured"
            response_model: Pydantic model class (required for mode="structured")
            system_prompt: System prompt applied to all
            temperature: Sampling temperature
            max_tokens: Maximum tokens per generation
            **kwargs: Additional arguments

        Returns:
            - mode="text" or "json": List[Dict[str, Any]]
            - mode="structured": List[Tuple[Model, Dict[str, Any]]]

        Raises:
            ValueError: If mode="structured" but response_model is not provided
        """
        if mode == "structured" and response_model is None:
            raise ValueError("response_model is required when mode='structured'")

        results = []
        for i, prompt in enumerate(prompts):
            logger.info(f"Processing prompt {i+1}/{len(prompts)} (mode={mode})")

            if mode == "text":
                result = self.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            elif mode == "json":
                result = self.generate_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            elif mode == "structured":
                result = self.generate_structured(
                    prompt=prompt,
                    response_model=response_model,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'text', 'json', or 'structured'")

            results.append(result)

        return results
