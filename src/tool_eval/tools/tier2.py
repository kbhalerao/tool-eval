"""Tier 2 tools: Structured parameter types (dates, lists, optionals, enums)."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field
from .registry import tool_registry


# --- Pydantic models for tool arguments ---


class CreateEventArgs(BaseModel):
    """Arguments for create_event tool."""

    title: str = Field(description="Event title")
    date: datetime.date = Field(description="Event date in YYYY-MM-DD format")
    attendees: list[str] = Field(description="List of attendee names or emails")


class SearchProductsArgs(BaseModel):
    """Arguments for search_products tool."""

    query: str = Field(description="Search query")
    max_price: float | None = Field(default=None, description="Maximum price filter")
    category: str | None = Field(default=None, description="Product category filter")


class SendMessageArgs(BaseModel):
    """Arguments for send_message tool."""

    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Message subject")
    body: str = Field(description="Message body")
    priority: Literal["low", "normal", "high"] = Field(
        default="normal", description="Message priority level"
    )


class SetReminderArgs(BaseModel):
    """Arguments for set_reminder tool."""

    title: str = Field(description="Reminder title")
    date: datetime.date = Field(description="Reminder date in YYYY-MM-DD format")
    tags: list[str] | None = Field(default=None, description="Optional tags for categorization")


# --- Tool implementations ---


@tool_registry.register(
    tier=2,
    description="Create a calendar event with attendees",
    tags=["structured", "date", "list"],
)
def create_event(args: CreateEventArgs) -> dict:
    """Create a calendar event."""
    return {
        "status": "created",
        "event_id": "evt_123",
        "title": args.title,
        "date": args.date.isoformat(),
        "attendees": args.attendees,
    }


@tool_registry.register(
    tier=2,
    description="Search for products with optional filters",
    tags=["structured", "optional"],
)
def search_products(args: SearchProductsArgs) -> dict:
    """Search for products."""
    return {
        "query": args.query,
        "filters": {
            "max_price": args.max_price,
            "category": args.category,
        },
        "results": [],  # Mock empty results
    }


@tool_registry.register(
    tier=2,
    description="Send an email message with priority",
    tags=["structured", "enum"],
)
def send_message(args: SendMessageArgs) -> dict:
    """Send an email message."""
    return {
        "status": "sent",
        "message_id": "msg_456",
        "to": args.to,
        "subject": args.subject,
        "priority": args.priority,
    }


@tool_registry.register(
    tier=2,
    description="Set a reminder for a specific date",
    tags=["structured", "date", "optional-list"],
)
def set_reminder(args: SetReminderArgs) -> dict:
    """Set a reminder."""
    return {
        "status": "set",
        "reminder_id": "rem_789",
        "title": args.title,
        "date": args.date.isoformat(),
        "tags": args.tags,
    }
