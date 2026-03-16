"""
LLM client wrapper using LiteLLM.

Provides a unified interface for calling different LLM providers
with automatic retry, error handling, and token tracking.
"""
import asyncio
import logging
import threading
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

    # Class-level semaphore registry: one semaphore per model name.
    # Shared across ALL LLMClient instances so concurrent batch jobs
    # respect a single concurrency limit per provider/model.
    _semaphores: dict[str, asyncio.Semaphore] = {}
    _sem_lock = threading.Lock()

    def __init__(self, model: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            model: Model name (e.g., "gpt-4o-mini", "claude-3-5-sonnet-20241022")
                   Defaults to settings.default_llm_model
        """
        self.model = model or settings.default_llm_model
        # Global per-model semaphore to limit concurrent async requests
        with LLMClient._sem_lock:
            if self.model not in LLMClient._semaphores:
                LLMClient._semaphores[self.model] = asyncio.Semaphore(
                    settings.llm_max_concurrent
                )
            self._semaphore = LLMClient._semaphores[self.model]

    @staticmethod
    def _extract_json_string(content: str) -> str:
        """
        Extract JSON string from LLM response.

        Handles common LLM output issues:
        - Strips markdown code blocks (```json ... ``` or ``` ... ```)
        - Extracts JSON object/array from surrounding text

        Args:
            content: Raw LLM response string

        Returns:
            Clean JSON string ready for parsing
        """
        import re

        if not content or not content.strip():
            raise ValueError("LLM returned empty content")

        json_str = content.strip()

        # Strip markdown code blocks if present
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_str)
        if code_block_match:
            json_str = code_block_match.group(1).strip()

        return json_str

    @staticmethod
    def _sanitize_json_for_validation(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize JSON data before Pydantic validation.

        Handles common LLM output issues:
        - Converts string "True"/"False" to boolean true/false
        - Recursively processes nested dictionaries and lists

        Args:
            data: Parsed JSON dictionary

        Returns:
            Sanitized dictionary ready for Pydantic validation
        """
        def sanitize_value(value: Any) -> Any:
            # Handle string boolean conversion
            if isinstance(value, str):
                if value == "True":
                    return True
                elif value == "False":
                    return False
                return value
            # Recursively handle nested dictionaries
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            # Recursively handle lists
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            # Return other types as-is
            return value

        return {k: sanitize_value(v) for k, v in data.items()}

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
                num_retries=settings.llm_num_retries,
                timeout=600,
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
            # Log rate limit errors specifically
            if "429" in str(e) or "rate" in str(e).lower():
                logger.error(f"Rate limit error (after {settings.llm_num_retries} retries): {e}")
            else:
                logger.error(f"LLM generation failed: {e}")
            raise

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

        # Build response_format with JSON schema for structured output
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": response_model.model_json_schema(),
            }
        }

        # Generate with structured output
        response = self.generate(
            prompt=schema_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            **kwargs
        )

        # Parse and validate response against Pydantic model
        try:
            import json
            json_str = self._extract_json_string(response["content"])
            content_json = json.loads(json_str)
            # Sanitize JSON before validation (handles string "True"/"False" etc.)
            content_json = self._sanitize_json_for_validation(content_json)
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

            # Build response_format with JSON schema for structured output
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                }
            }

            # Call async LLM with structured output (with semaphore to limit concurrency)
            async with self._semaphore:
                logger.debug(
                    f"Acquired semaphore for {self.model} "
                    f"({self._semaphore._value} slots remaining)"
                )
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    num_retries=settings.llm_num_retries,
                    timeout=600,
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
            logger.debug(f"Raw content type: {type(content)}, content: {content[:500] if content else 'None/Empty'}")
            json_str = self._extract_json_string(content)
            logger.debug(f"Extracted JSON string: {json_str[:500] if json_str else 'None/Empty'}")
            content_json = json.loads(json_str)
            # Sanitize JSON before validation (handles string "True"/"False" etc.)
            content_json = self._sanitize_json_for_validation(content_json)
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

        except Exception as e:
            # Log rate limit errors specifically
            if "429" in str(e) or "rate" in str(e).lower():
                logger.error(f"Rate limit error (after {settings.llm_num_retries} retries) for {response_model.__name__}: {e}")
            else:
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
