"""Tier 1 tools: Primitive parameter types."""

from pydantic import BaseModel, Field
from .registry import tool_registry


# --- Pydantic models for tool arguments ---


class WeatherArgs(BaseModel):
    """Arguments for get_weather tool."""

    city: str = Field(description="The city to get weather for")


class AddNumbersArgs(BaseModel):
    """Arguments for add_numbers tool."""

    a: int = Field(description="First number to add")
    b: int = Field(description="Second number to add")


class ValidateEmailArgs(BaseModel):
    """Arguments for is_valid_email tool."""

    email: str = Field(description="Email address to validate")


# --- Tool implementations ---


@tool_registry.register(
    tier=1,
    description="Get the current weather for a city",
    tags=["primitive", "extraction"],
)
def get_weather(args: WeatherArgs) -> str:
    """Get the current weather for a city."""
    # Mock implementation - in real use would call weather API
    return f"Weather in {args.city}: 72°F, sunny"


@tool_registry.register(
    tier=1,
    description="Add two numbers together",
    tags=["primitive", "math"],
)
def add_numbers(args: AddNumbersArgs) -> int:
    """Add two numbers together."""
    return args.a + args.b


@tool_registry.register(
    tier=1,
    description="Check if an email address is valid",
    tags=["primitive", "validation"],
)
def is_valid_email(args: ValidateEmailArgs) -> bool:
    """Check if an email address is valid.

    Simple validation - checks for @ and domain.
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, args.email))
