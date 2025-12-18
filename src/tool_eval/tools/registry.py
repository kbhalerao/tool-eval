"""Tool registry for managing eval tools."""

from dataclasses import dataclass, field
from typing import Callable, Any, get_type_hints
from pydantic import BaseModel
import inspect


def resolve_refs(schema: dict, defs: dict) -> dict:
    """Recursively resolve $ref references by inlining definitions."""
    if isinstance(schema, dict):
        # Handle $ref - inline the definition
        if "$ref" in schema:
            ref_path = schema["$ref"]
            # Format: #/$defs/ModelName
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                if def_name in defs:
                    # Return resolved definition (recursively resolve nested refs)
                    return resolve_refs(defs[def_name].copy(), defs)
            # If we can't resolve, return as-is (will fail but at least won't crash)
            return schema

        # Recursively process all keys
        return {k: resolve_refs(v, defs) for k, v in schema.items()}
    elif isinstance(schema, list):
        return [resolve_refs(item, defs) for item in schema]
    return schema


def simplify_schema(schema: dict, strip_metadata: bool = False) -> dict:
    """Simplify JSON schema for better LLM compatibility.

    - Resolves $ref by inlining definitions from $defs
    - Removes anyOf with null (just use the base type)
    - Removes $defs after resolution
    - Removes default: null (causes issues with some servers)
    - Optionally strips title/description to reduce size

    Args:
        schema: The schema to simplify
        strip_metadata: If True, remove title/description fields
    """
    # First pass: resolve all $ref references
    defs = schema.get("$defs", {})
    if defs:
        schema = resolve_refs(schema, defs)

    # Second pass: clean up the schema
    return _cleanup_schema(schema, strip_metadata)


def _cleanup_schema(
    schema: dict, strip_metadata: bool = False, in_anyof: bool = False
) -> dict:
    """Remove anyOf/null patterns and clean up schema.

    Args:
        schema: The schema to clean up
        strip_metadata: If True, remove title/description fields to reduce size
        in_anyof: If True, we're inside an anyOf array (preserve variant descriptions)
    """
    if isinstance(schema, dict):
        # Handle anyOf with null - common pattern for Optional[T]
        if "anyOf" in schema:
            non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
            if len(non_null) == 1:
                # Replace anyOf with the non-null type
                result = {k: v for k, v in schema.items() if k != "anyOf"}
                result.update(non_null[0])
                return _cleanup_schema(result, strip_metadata, in_anyof)
            else:
                # Multiple non-null variants - this is a real union type
                # Process the anyOf items with in_anyof=True to preserve their descriptions
                result = {}
                for k, v in schema.items():
                    if k == "anyOf":
                        result[k] = [
                            _cleanup_schema(item, strip_metadata, in_anyof=True)
                            for item in v
                        ]
                    else:
                        result[k] = _cleanup_schema(v, strip_metadata, in_anyof)
                return result

        # Recursively process
        result = {}
        for k, v in schema.items():
            # Remove $defs (already resolved)
            if k == "$defs":
                continue
            # Remove default: null (causes server errors)
            if k == "default" and v is None:
                continue
            # Optionally strip metadata to reduce schema size
            # BUT preserve description on anyOf variants (critical for discrimination!)
            if strip_metadata and k == "title":
                continue
            if strip_metadata and k == "description" and not in_anyof:
                continue
            result[k] = _cleanup_schema(v, strip_metadata, False)
        return result
    elif isinstance(schema, list):
        return [_cleanup_schema(item, strip_metadata, in_anyof) for item in schema]
    return schema


@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""

    name: str
    description: str
    tier: int
    func: Callable[..., Any]
    model: type[BaseModel]
    tags: list[str] = field(default_factory=list)

    def to_openai_tool(self, strip_metadata: bool = False) -> dict:
        """Convert to OpenAI tool format.

        Args:
            strip_metadata: If True, remove title/description from schema to reduce size
        """
        schema = self.model.model_json_schema()
        # Simplify schema for better LLM compatibility
        schema = simplify_schema(schema, strip_metadata)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class ToolRegistry:
    """Registry for eval tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        tier: int,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Callable:
        """Decorator to register a tool with its Pydantic model.

        The decorated function should have a single parameter that is a Pydantic model.

        Example:
            @registry.register(tier=1, description="Get weather for a city")
            def get_weather(args: WeatherArgs) -> str:
                return f"Weather in {args.city}: sunny"
        """

        def decorator(func: Callable) -> Callable:
            hints = get_type_hints(func)
            params = list(inspect.signature(func).parameters.values())

            if not params:
                raise ValueError(f"Tool {func.__name__} must have at least one parameter")

            # Get the Pydantic model from first param
            first_param = params[0]
            model = hints.get(first_param.name)

            if model is None or not (
                isinstance(model, type) and issubclass(model, BaseModel)
            ):
                raise ValueError(
                    f"Tool {func.__name__}'s first parameter must be a Pydantic model, "
                    f"got {model}"
                )

            tool_def = ToolDefinition(
                name=func.__name__,
                description=description or func.__doc__ or "",
                tier=tier,
                func=func,
                model=model,
                tags=tags or [],
            )
            self._tools[func.__name__] = tool_def
            return func

        return decorator

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_by_tier(self, tier: int) -> list[ToolDefinition]:
        """Get all tools for a given tier."""
        return [t for t in self._tools.values() if t.tier == tier]

    def get_by_tags(self, tags: list[str]) -> list[ToolDefinition]:
        """Get tools matching any of the given tags."""
        return [t for t in self._tools.values() if any(tag in t.tags for tag in tags)]

    def all(self) -> list[ToolDefinition]:
        """Get all registered tools."""
        return list(self._tools.values())

    def to_openai_tools(
        self, names: list[str] | None = None, strip_metadata: bool = False
    ) -> list[dict]:
        """Convert tools to OpenAI format.

        Args:
            names: Optional list of tool names to include. If None, includes all.
            strip_metadata: If True, remove title/description from schemas
        """
        tools = self._tools.values()
        if names:
            tools = [t for t in tools if t.name in names]
        return [t.to_openai_tool(strip_metadata) for t in tools]


# Global registry instance
tool_registry = ToolRegistry()
