"""Tier 5: Multi-tool selection with distractors."""

from pydantic import BaseModel, Field

from .registry import tool_registry


# =============================================================================
# SEARCH TOOLS (similar names, different purposes)
# =============================================================================

class SearchUsersArgs(BaseModel):
    """Search for users."""
    query: str = Field(description="Search query for user names or emails")
    department: str | None = Field(default=None, description="Filter by department")


@tool_registry.register(
    tier=5,
    description="Search for users by name or email",
    tags=["search", "users"],
)
def search_users(args: SearchUsersArgs) -> str:
    return f"Found users matching '{args.query}'"


class SearchDocumentsArgs(BaseModel):
    """Search for documents."""
    query: str = Field(description="Search query for document content")
    file_type: str | None = Field(default=None, description="Filter by file type (pdf, docx, etc)")


@tool_registry.register(
    tier=5,
    description="Search for documents by content or title",
    tags=["search", "documents"],
)
def search_documents(args: SearchDocumentsArgs) -> str:
    return f"Found documents matching '{args.query}'"


class SearchCalendarArgs(BaseModel):
    """Search calendar events."""
    query: str = Field(description="Search query for event titles or descriptions")
    date_from: str | None = Field(default=None, description="Start date filter (ISO format)")
    date_to: str | None = Field(default=None, description="End date filter (ISO format)")


@tool_registry.register(
    tier=5,
    description="Search for calendar events by title or description",
    tags=["search", "calendar"],
)
def search_calendar(args: SearchCalendarArgs) -> str:
    return f"Found events matching '{args.query}'"


class SearchProductsArgs(BaseModel):
    """Search for products."""
    query: str = Field(description="Search query for product names")
    category: str | None = Field(default=None, description="Product category filter")
    max_price: float | None = Field(default=None, description="Maximum price filter")


@tool_registry.register(
    tier=5,
    description="Search for products in the catalog",
    tags=["search", "products"],
)
def search_products_v2(args: SearchProductsArgs) -> str:
    return f"Found products matching '{args.query}'"


class SearchTicketsArgs(BaseModel):
    """Search support tickets."""
    query: str = Field(description="Search query for ticket content")
    status: str | None = Field(default=None, description="Filter by status (open, closed, pending)")
    priority: str | None = Field(default=None, description="Filter by priority (low, medium, high)")


@tool_registry.register(
    tier=5,
    description="Search for support tickets",
    tags=["search", "tickets"],
)
def search_tickets(args: SearchTicketsArgs) -> str:
    return f"Found tickets matching '{args.query}'"


# =============================================================================
# SEND/NOTIFY TOOLS (similar actions, different channels)
# =============================================================================

class SendEmailArgs(BaseModel):
    """Send an email."""
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body")


@tool_registry.register(
    tier=5,
    description="Send an email to a recipient",
    tags=["send", "email"],
)
def send_email(args: SendEmailArgs) -> str:
    return f"Email sent to {args.to}"


class SendSlackArgs(BaseModel):
    """Send a Slack message."""
    channel: str = Field(description="Slack channel name (e.g., #general)")
    message: str = Field(description="Message content")


@tool_registry.register(
    tier=5,
    description="Send a message to a Slack channel",
    tags=["send", "slack"],
)
def send_slack(args: SendSlackArgs) -> str:
    return f"Slack message sent to {args.channel}"


class SendSMSArgs(BaseModel):
    """Send an SMS."""
    phone: str = Field(description="Phone number with country code")
    message: str = Field(description="SMS message content")


@tool_registry.register(
    tier=5,
    description="Send an SMS text message",
    tags=["send", "sms"],
)
def send_sms(args: SendSMSArgs) -> str:
    return f"SMS sent to {args.phone}"


class SendWebhookArgs(BaseModel):
    """Send a webhook."""
    url: str = Field(description="Webhook URL")
    payload: dict = Field(description="JSON payload to send")


@tool_registry.register(
    tier=5,
    description="Send a webhook POST request",
    tags=["send", "webhook"],
)
def send_webhook(args: SendWebhookArgs) -> str:
    return f"Webhook sent to {args.url}"


# =============================================================================
# CREATE TOOLS (similar verbs, different objects)
# =============================================================================

class CreateTaskArgs(BaseModel):
    """Create a task."""
    title: str = Field(description="Task title")
    description: str | None = Field(default=None, description="Task description")
    assignee: str | None = Field(default=None, description="Assignee email")
    due_date: str | None = Field(default=None, description="Due date (ISO format)")


@tool_registry.register(
    tier=5,
    description="Create a new task",
    tags=["create", "task"],
)
def create_task(args: CreateTaskArgs) -> str:
    return f"Created task: {args.title}"


class CreateEventArgs(BaseModel):
    """Create a calendar event."""
    title: str = Field(description="Event title")
    start_time: str = Field(description="Event start time (ISO format)")
    end_time: str = Field(description="Event end time (ISO format)")
    attendees: list[str] | None = Field(default=None, description="List of attendee emails")


@tool_registry.register(
    tier=5,
    description="Create a new calendar event",
    tags=["create", "event"],
)
def create_event_v2(args: CreateEventArgs) -> str:
    return f"Created event: {args.title}"


class CreateNoteArgs(BaseModel):
    """Create a note."""
    title: str = Field(description="Note title")
    content: str = Field(description="Note content")
    tags: list[str] | None = Field(default=None, description="Tags for the note")


@tool_registry.register(
    tier=5,
    description="Create a new note",
    tags=["create", "note"],
)
def create_note(args: CreateNoteArgs) -> str:
    return f"Created note: {args.title}"


class CreateReminderArgs(BaseModel):
    """Create a reminder."""
    message: str = Field(description="Reminder message")
    remind_at: str = Field(description="When to remind (ISO format)")


@tool_registry.register(
    tier=5,
    description="Create a new reminder",
    tags=["create", "reminder"],
)
def create_reminder(args: CreateReminderArgs) -> str:
    return f"Created reminder: {args.message}"
