"""Shared Pydantic models for tools across tiers."""

from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field


# --- Tier 2 Models ---


class EventArgs(BaseModel):
    """Arguments for create_event tool."""

    title: str = Field(description="Event title")
    date: date = Field(description="Event date (YYYY-MM-DD)")
    attendees: list[str] = Field(description="List of attendee names or emails")


class ProductSearchArgs(BaseModel):
    """Arguments for search_products tool."""

    query: str = Field(description="Search query")
    max_price: float | None = Field(default=None, description="Maximum price filter")
    category: str | None = Field(default=None, description="Product category filter")


class MessageArgs(BaseModel):
    """Arguments for send_message tool."""

    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Message subject")
    body: str = Field(description="Message body")
    priority: Literal["low", "normal", "high"] = Field(
        default="normal", description="Message priority"
    )


# --- Tier 3 Models ---


class Address(BaseModel):
    """Shipping or billing address."""

    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"


class Customer(BaseModel):
    """Customer information."""

    name: str
    email: str
    phone: str | None = None


class OrderItem(BaseModel):
    """Item in an order."""

    product_id: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)


class Person(BaseModel):
    """Person for meeting scheduling."""

    name: str
    email: str
    required: bool = True


class TimeSlot(BaseModel):
    """Available time slot."""

    start: datetime
    end: datetime


class Room(BaseModel):
    """Meeting room."""

    name: str
    capacity: int
    location: str | None = None


# --- Tier 4 Models (Polymorphic) ---


class CreateAction(BaseModel):
    """Create action type."""

    action_type: Literal["create"] = "create"
    resource_type: str
    data: dict


class UpdateAction(BaseModel):
    """Update action type."""

    action_type: Literal["update"] = "update"
    resource_id: str
    changes: dict


class DeleteAction(BaseModel):
    """Delete action type."""

    action_type: Literal["delete"] = "delete"
    resource_id: str
    cascade: bool = False
