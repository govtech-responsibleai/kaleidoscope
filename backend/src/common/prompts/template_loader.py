"""
Prompt template loader with variable substitution using Jinja2.

Loads .md prompt templates and substitutes variables.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound

logger = logging.getLogger(__name__)


class PromptTemplateLoader:
    """Loader for prompt templates with variable substitution."""

    def __init__(self, templates_dir: str = None):
        """
        Initialize template loader.

        Args:
            templates_dir: Directory containing prompt templates.
                          Defaults to src/common/prompts/templates/
        """
        if templates_dir is None:
            # Default to templates directory relative to this file
            current_dir = Path(__file__).parent
            templates_dir = str(current_dir / "templates")

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.debug(f"PromptTemplateLoader initialized with dir: {templates_dir}")

    def load_template(self, template_name: str) -> Template:
        """
        Load a template by name.

        Args:
            template_name: Name of template file (e.g., "persona_generation.md")

        Returns:
            Jinja2 Template object

        Raises:
            TemplateNotFound: If template file doesn't exist
        """
        try:
            template = self.env.get_template(template_name)
            logger.debug(f"Loaded template: {template_name}")
            return template
        except TemplateNotFound:
            logger.error(f"Template not found: {template_name}")
            raise

    def render(self, template_name: str, **variables) -> str:
        """
        Load and render a template with variables.

        Args:
            template_name: Name of template file
            **variables: Variables to substitute in template

        Returns:
            Rendered prompt string

        Example:
            >>> loader = PromptTemplateLoader()
            >>> prompt = loader.render(
            ...     "persona_generation.md",
            ...     target_name="RAI Bot",
            ...     purpose="Provide responsible AI guidance",
            ...     target_persona_count=5
            ... )
        """
        template = self.load_template(template_name)
        rendered = template.render(**variables)
        logger.debug(f"Rendered template: {template_name} ({len(rendered)} chars)")
        return rendered

    def render_from_string(self, template_string: str, **variables) -> str:
        """
        Render a template from a string (not a file).

        Args:
            template_string: Template content as string
            **variables: Variables to substitute

        Returns:
            Rendered prompt string
        """
        template = self.env.from_string(template_string)
        rendered = template.render(**variables)
        return rendered

    def list_templates(self) -> list[str]:
        """
        List all available templates in the templates directory.

        Returns:
            List of template filenames
        """
        templates_path = Path(self.templates_dir)
        if not templates_path.exists():
            return []

        return [
            f.name
            for f in templates_path.iterdir()
            if f.is_file() and f.suffix in [".md", ".txt"]
        ]


# Global instance for convenience
_default_loader = None


def get_loader() -> PromptTemplateLoader:
    """Get the default global template loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptTemplateLoader()
    return _default_loader


def render_template(template_name: str, **variables) -> str:
    """
    Convenience function to render a template using the default loader.

    Args:
        template_name: Name of template file
        **variables: Variables to substitute

    Returns:
        Rendered prompt string
    """
    loader = get_loader()
    return loader.render(template_name, **variables)
