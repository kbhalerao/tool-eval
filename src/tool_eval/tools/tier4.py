"""Tier 4: Polymorphic/Union type tools."""

from typing import Literal, Union
from pydantic import BaseModel, Field

from .registry import tool_registry


# =============================================================================
# EXECUTE ACTION (Union of Create/Update/Delete)
# =============================================================================

class CreateAction(BaseModel):
    """Create a new resource."""
    action_type: Literal["create"] = Field(description="Action type indicator")
    resource_type: str = Field(description="Type of resource to create (user, post, comment)")
    name: str = Field(description="Name for the new resource")
    metadata: dict | None = Field(default=None, description="Optional metadata")


class UpdateAction(BaseModel):
    """Update an existing resource."""
    action_type: Literal["update"] = Field(description="Action type indicator")
    resource_id: str = Field(description="ID of resource to update")
    updates: dict = Field(description="Fields to update")


class DeleteAction(BaseModel):
    """Delete a resource."""
    action_type: Literal["delete"] = Field(description="Action type indicator")
    resource_id: str = Field(description="ID of resource to delete")
    soft_delete: bool = Field(default=False, description="Whether to soft delete")


class ExecuteActionArgs(BaseModel):
    """Arguments for execute_action tool."""
    action: Union[CreateAction, UpdateAction, DeleteAction] = Field(
        description="The action to execute - can be create, update, or delete"
    )


@tool_registry.register(
    tier=4,
    description="Execute a CRUD action on a resource (create, update, or delete)",
    tags=["polymorphic", "crud", "union"],
)
def execute_action(args: ExecuteActionArgs) -> str:
    """Execute a CRUD action."""
    action = args.action
    if isinstance(action, CreateAction):
        return f"Created {action.resource_type}: {action.name}"
    elif isinstance(action, UpdateAction):
        return f"Updated {action.resource_id}: {action.updates}"
    else:
        return f"Deleted {action.resource_id} (soft={action.soft_delete})"


# =============================================================================
# BUILD QUERY (Complex filter with union filter types)
# =============================================================================

class TextFilter(BaseModel):
    """Text-based filter."""
    filter_type: Literal["text"] = Field(description="Filter type indicator")
    field: str = Field(description="Field to filter on")
    operator: Literal["equals", "contains", "starts_with", "ends_with"] = Field(
        description="Text comparison operator"
    )
    value: str = Field(description="Value to compare against")


class NumericFilter(BaseModel):
    """Numeric filter."""
    filter_type: Literal["numeric"] = Field(description="Filter type indicator")
    field: str = Field(description="Field to filter on")
    operator: Literal["eq", "gt", "lt", "gte", "lte", "between"] = Field(
        description="Numeric comparison operator"
    )
    value: float = Field(description="Value to compare against")
    value2: float | None = Field(default=None, description="Second value for 'between' operator")


class DateFilter(BaseModel):
    """Date-based filter."""
    filter_type: Literal["date"] = Field(description="Filter type indicator")
    field: str = Field(description="Field to filter on")
    operator: Literal["before", "after", "between", "on"] = Field(
        description="Date comparison operator"
    )
    value: str = Field(description="Date value (ISO format)")
    value2: str | None = Field(default=None, description="Second date for 'between' operator")


class SortSpec(BaseModel):
    """Sort specification."""
    field: str = Field(description="Field to sort by")
    direction: Literal["asc", "desc"] = Field(default="asc", description="Sort direction")


class Pagination(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class BuildQueryArgs(BaseModel):
    """Arguments for build_query tool."""
    filters: list[Union[TextFilter, NumericFilter, DateFilter]] = Field(
        description="List of filters to apply"
    )
    sort: SortSpec | None = Field(default=None, description="Sort specification")
    pagination: Pagination = Field(default_factory=Pagination, description="Pagination params")


@tool_registry.register(
    tier=4,
    description="Build a database query with filters, sorting, and pagination",
    tags=["polymorphic", "query", "filter"],
)
def build_query(args: BuildQueryArgs) -> str:
    """Build a query from specifications."""
    filter_strs = []
    for f in args.filters:
        filter_strs.append(f"{f.field} {f.operator} {f.value}")

    result = f"Query: {' AND '.join(filter_strs)}"
    if args.sort:
        result += f" ORDER BY {args.sort.field} {args.sort.direction}"
    result += f" LIMIT {args.pagination.page_size} OFFSET {(args.pagination.page - 1) * args.pagination.page_size}"
    return result


# =============================================================================
# SEND NOTIFICATION (Union of channels)
# =============================================================================

class EmailNotification(BaseModel):
    """Email notification."""
    channel: Literal["email"] = Field(description="Notification channel")
    to: str = Field(description="Email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body")


class SMSNotification(BaseModel):
    """SMS notification."""
    channel: Literal["sms"] = Field(description="Notification channel")
    phone_number: str = Field(description="Phone number with country code")
    message: str = Field(description="SMS message (max 160 chars)")


class PushNotification(BaseModel):
    """Push notification."""
    channel: Literal["push"] = Field(description="Notification channel")
    device_id: str = Field(description="Target device ID")
    title: str = Field(description="Notification title")
    body: str = Field(description="Notification body")
    data: dict | None = Field(default=None, description="Additional payload data")


class SendNotificationArgs(BaseModel):
    """Arguments for send_notification tool."""
    notification: Union[EmailNotification, SMSNotification, PushNotification] = Field(
        description="The notification to send - email, SMS, or push"
    )
    priority: Literal["low", "normal", "high"] = Field(
        default="normal", description="Delivery priority"
    )


@tool_registry.register(
    tier=4,
    description="Send a notification via email, SMS, or push notification",
    tags=["polymorphic", "notification", "union"],
)
def send_notification(args: SendNotificationArgs) -> str:
    """Send a notification."""
    n = args.notification
    if isinstance(n, EmailNotification):
        return f"Email sent to {n.to}: {n.subject}"
    elif isinstance(n, SMSNotification):
        return f"SMS sent to {n.phone_number}: {n.message[:20]}..."
    else:
        return f"Push sent to {n.device_id}: {n.title}"
