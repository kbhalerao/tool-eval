"""
Tier 6: Strategic Tool Selection with Diagnostic Rationale

Tests whether models can choose the optimal research strategy based on user intent.
Modeled on real agronomic research agent that must decide:
- Products-first: Search catalog → drill into trials (for discovery, brand validation)
- Trials-first: Search performance data → identify winners (for analytics, conditions)

Each tool includes a rationale field forcing the model to articulate its reasoning.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional

from .registry import tool_registry


# =============================================================================
# Rationale field - required for audit trail and diagnostic insight
# =============================================================================

RATIONALE_DESC = (
    "Decision rationale for audit trail. Briefly explain: "
    "(1) why this search strategy was selected, "
    "(2) what user intent signals drove the choice. "
    "Required for traceability."
)


# =============================================================================
# Shared types - deep nesting for schema complexity
# =============================================================================

class GeoLocation(BaseModel):
    """Geographic coordinates with search radius."""
    lat: float = Field(description="Latitude")
    lon: float = Field(description="Longitude")
    radius_miles: int = Field(default=50, description="Search radius in miles")


class LocationQuery(BaseModel):
    """Location specified by name (will be geocoded)."""
    name: str = Field(description="Location name (city, county, state)")
    radius_miles: int = Field(default=50, description="Search radius in miles")


class MaturityRange(BaseModel):
    """Crop maturity range filter."""
    min_days: Optional[int] = Field(default=None, description="Minimum relative maturity")
    max_days: Optional[int] = Field(default=None, description="Maximum relative maturity")


class YieldMetrics(BaseModel):
    """Yield performance thresholds."""
    min_advantage_bushels: Optional[float] = Field(
        default=None,
        description="Minimum yield advantage over check (bushels/acre)"
    )
    top_percentile: Optional[int] = Field(
        default=None,
        description="Only include products in top N percentile (e.g., 30 for top 30%)"
    )


class TrialConditions(BaseModel):
    """Conditions to filter trial data."""
    years: Optional[list[int]] = Field(default=None, description="Filter to specific years")
    soil_types: Optional[list[Literal["clay", "loam", "sand", "silt_loam", "clay_loam"]]] = Field(
        default=None,
        description="Filter by soil texture"
    )
    min_trials: Optional[int] = Field(
        default=None,
        description="Minimum number of trials required for inclusion"
    )
    irrigation: Optional[Literal["irrigated", "dryland", "any"]] = Field(
        default=None,
        description="Filter by irrigation status"
    )


class ProductFilters(BaseModel):
    """Filters for product catalog search."""
    crop: Literal["corn", "soybeans"] = Field(description="Crop type")
    brands: Optional[list[str]] = Field(default=None, description="Filter to specific brands")
    traits: Optional[list[str]] = Field(
        default=None,
        description="Required traits (e.g., 'VT2P', 'E3', 'RR2X')"
    )
    maturity: Optional[MaturityRange] = Field(default=None, description="Maturity range filter")
    exclude_discontinued: bool = Field(default=True, description="Exclude discontinued products")


class PerformanceFilters(BaseModel):
    """Filters for performance/trial search."""
    crop: Literal["corn", "soybeans"] = Field(description="Crop type")
    conditions: Optional[TrialConditions] = Field(default=None, description="Trial condition filters")
    yield_thresholds: Optional[YieldMetrics] = Field(default=None, description="Yield performance thresholds")
    consistency_weight: Optional[float] = Field(
        default=None,
        description="Weight for consistency vs peak yield (0-1, higher = prefer consistent)"
    )


# =============================================================================
# Strategy 1: Product-First Search
# =============================================================================

class ProductFirstSearchArgs(BaseModel):
    """
    Search product catalog first, then drill into trial data for matches.

    BEST FOR:
    - Discovery queries: "What's available near me?"
    - Brand validation: "Tell me about Pioneer hybrids"
    - Known product lookup: "I want to try DeKalb 60-01"
    - Availability-focused: "What can I get for my farm?"

    NOT IDEAL FOR:
    - Performance-focused queries (use trial_first_search)
    - Condition-specific analysis (use trial_first_search)
    """
    rationale: str = Field(description=RATIONALE_DESC)
    query: str = Field(description="Natural language description of what user is looking for")
    location: LocationQuery = Field(description="Geographic area to search")
    filters: Optional[ProductFilters] = Field(default=None, description="Product catalog filters")
    include_trial_summary: bool = Field(
        default=True,
        description="Include aggregated trial performance for matched products"
    )
    max_results: int = Field(default=10, description="Maximum products to return")


# =============================================================================
# Strategy 2: Trial-First Search
# =============================================================================

class TrialFirstSearchArgs(BaseModel):
    """
    Search trial performance data first, then identify top-performing products.

    BEST FOR:
    - Performance queries: "What's winning in local trials?"
    - Condition-specific: "Best for clay soil", "drought tolerance"
    - Analytics: "Most consistent performers", "highest yield advantage"
    - Geographic performance: "What works in Story County?"

    NOT IDEAL FOR:
    - Brand/product validation (use product_first_search)
    - Availability/discovery queries (use product_first_search)
    """
    rationale: str = Field(description=RATIONALE_DESC)
    query: str = Field(description="Natural language description of performance criteria")
    location: LocationQuery = Field(description="Geographic area for trial data")
    filters: Optional[PerformanceFilters] = Field(default=None, description="Performance/trial filters")
    rank_by: Literal["yield_advantage", "consistency", "top_percentile", "trial_count"] = Field(
        default="yield_advantage",
        description="Primary ranking metric"
    )
    max_results: int = Field(default=10, description="Maximum products to return")


# =============================================================================
# Strategy 3: Comparative Analysis (requires both)
# =============================================================================

class CompareProductsArgs(BaseModel):
    """
    Compare specific products head-to-head on trial performance.

    BEST FOR:
    - Direct comparison: "Compare Pioneer vs DeKalb"
    - Narrowing choices: "Which of these three is best?"
    - Validation: "How does my current seed compare to alternatives?"

    REQUIRES: User has identified specific products to compare.
    """
    rationale: str = Field(description=RATIONALE_DESC)
    products: list[str] = Field(
        description="Product names or IDs to compare (2-5 products)"
    )
    location: LocationQuery = Field(description="Geographic area for comparison")
    comparison_metrics: list[Literal["yield", "consistency", "emergence", "standability", "moisture"]] = Field(
        default=["yield", "consistency"],
        description="Metrics to compare"
    )
    conditions: Optional[TrialConditions] = Field(
        default=None,
        description="Filter comparison to specific conditions"
    )


# =============================================================================
# Register tools via decorator
# =============================================================================

@tool_registry.register(
    tier=6,
    description=(
        "Search product catalog first, then enrich with trial data. "
        "Use for: discovery ('what's available'), brand validation ('tell me about X brand'), "
        "known product lookup, availability-focused queries."
    ),
)
def product_first_search(args: ProductFirstSearchArgs) -> dict:
    """Product-first search strategy."""
    return {"status": "mock", "strategy": "product_first", "args": args.model_dump()}


@tool_registry.register(
    tier=6,
    description=(
        "Search trial performance data first, then identify top products. "
        "Use for: performance questions ('what's winning'), condition-specific analysis "
        "('best for clay'), geographic performance, consistency/yield ranking."
    ),
)
def trial_first_search(args: TrialFirstSearchArgs) -> dict:
    """Trial-first search strategy."""
    return {"status": "mock", "strategy": "trial_first", "args": args.model_dump()}


@tool_registry.register(
    tier=6,
    description=(
        "Compare specific products head-to-head on performance metrics. "
        "Use when user has identified 2-5 specific products to compare directly."
    ),
)
def compare_products(args: CompareProductsArgs) -> dict:
    """Product comparison."""
    return {"status": "mock", "strategy": "compare", "args": args.model_dump()}
