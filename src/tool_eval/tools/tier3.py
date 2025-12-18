"""Tier 3 tools: Nested object structures."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field
from .registry import tool_registry


# --- Nested models ---


class Address(BaseModel):
    """Shipping or billing address."""
    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    state: str = Field(description="State/province code")
    zip_code: str = Field(description="Postal/ZIP code")
    country: str = Field(default="USA", description="Country code")


class Customer(BaseModel):
    """Customer information."""
    name: str = Field(description="Customer full name")
    email: str = Field(description="Customer email address")
    phone: str | None = Field(default=None, description="Phone number")


class OrderItem(BaseModel):
    """Item in an order."""
    product_id: str = Field(description="Product identifier")
    quantity: int = Field(description="Quantity to order", ge=1)
    unit_price: float = Field(description="Price per unit", ge=0)


class Person(BaseModel):
    """Person for meeting scheduling."""
    name: str = Field(description="Person's name")
    email: str = Field(description="Person's email")
    required: bool = Field(default=True, description="Whether attendance is required")


class TimeSlot(BaseModel):
    """Available time slot."""
    start: str = Field(description="Start time in ISO format (YYYY-MM-DDTHH:MM)")
    end: str = Field(description="End time in ISO format (YYYY-MM-DDTHH:MM)")


class Room(BaseModel):
    """Meeting room."""
    name: str = Field(description="Room name/identifier")
    capacity: int = Field(description="Maximum capacity")
    location: str | None = Field(default=None, description="Building/floor location")


class ContactInfo(BaseModel):
    """Contact information."""
    email: str = Field(description="Email address")
    phone: str | None = Field(default=None, description="Phone number")
    address: Address | None = Field(default=None, description="Physical address")


class Employee(BaseModel):
    """Employee record."""
    name: str = Field(description="Employee name")
    department: str = Field(description="Department name")
    contact: ContactInfo = Field(description="Contact information")
    manager_email: str | None = Field(default=None, description="Manager's email")


# --- Tool argument models ---


class CreateOrderArgs(BaseModel):
    """Arguments for create_order tool."""
    customer: Customer = Field(description="Customer placing the order")
    items: list[OrderItem] = Field(description="List of items to order")
    shipping: Address = Field(description="Shipping address")


class ScheduleMeetingArgs(BaseModel):
    """Arguments for schedule_meeting tool."""
    title: str = Field(description="Meeting title")
    participants: list[Person] = Field(description="List of participants")
    time_slots: list[TimeSlot] = Field(description="Proposed time slots")
    room: Room | None = Field(default=None, description="Optional meeting room")


class RegisterEmployeeArgs(BaseModel):
    """Arguments for register_employee tool."""
    employee: Employee = Field(description="Employee information")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")


class BookTravelArgs(BaseModel):
    """Arguments for book_travel tool."""
    traveler: Customer = Field(description="Traveler information")
    origin: Address = Field(description="Departure location")
    destination: Address = Field(description="Arrival location")
    departure_date: str = Field(description="Departure date YYYY-MM-DD")
    return_date: str | None = Field(default=None, description="Return date for round trip")


# --- Tool implementations ---


@tool_registry.register(
    tier=3,
    description="Create a new order with customer info, items, and shipping address",
    tags=["nested", "order", "complex"],
)
def create_order(args: CreateOrderArgs) -> dict:
    """Create a new order."""
    total = sum(item.quantity * item.unit_price for item in args.items)
    return {
        "status": "created",
        "order_id": "ORD-12345",
        "customer": args.customer.name,
        "item_count": len(args.items),
        "total": total,
        "shipping_city": args.shipping.city,
    }


@tool_registry.register(
    tier=3,
    description="Schedule a meeting with participants, time slots, and optional room",
    tags=["nested", "meeting", "complex"],
)
def schedule_meeting(args: ScheduleMeetingArgs) -> dict:
    """Schedule a meeting."""
    return {
        "status": "scheduled",
        "meeting_id": "MTG-67890",
        "title": args.title,
        "participant_count": len(args.participants),
        "slot_count": len(args.time_slots),
        "room": args.room.name if args.room else "TBD",
    }


@tool_registry.register(
    tier=3,
    description="Register a new employee with nested contact information",
    tags=["nested", "employee", "deep"],
)
def register_employee(args: RegisterEmployeeArgs) -> dict:
    """Register a new employee."""
    return {
        "status": "registered",
        "employee_id": "EMP-11111",
        "name": args.employee.name,
        "department": args.employee.department,
        "start_date": args.start_date,
    }


@tool_registry.register(
    tier=3,
    description="Book travel with origin and destination addresses",
    tags=["nested", "travel", "addresses"],
)
def book_travel(args: BookTravelArgs) -> dict:
    """Book travel arrangements."""
    return {
        "status": "booked",
        "booking_id": "TRV-22222",
        "traveler": args.traveler.name,
        "route": f"{args.origin.city} -> {args.destination.city}",
        "departure": args.departure_date,
        "return": args.return_date,
    }
