"""Tool definitions for eval harness."""

from .registry import ToolRegistry, tool_registry
from .tier1 import get_weather, add_numbers, is_valid_email
from .tier2 import create_event, search_products, send_message, set_reminder
from .tier3 import create_order, schedule_meeting, register_employee, book_travel
from .tier4 import execute_action, build_query, send_notification
from .tier5 import (
    search_users, search_documents, search_calendar, search_products_v2, search_tickets,
    send_email, send_slack, send_sms, send_webhook,
    create_task, create_event_v2, create_note, create_reminder,
)
from . import tier6  # Import to trigger registration
from . import exploration  # Agentic exploration tools
from . import tier7  # Text-to-SQL

__all__ = [
    "ToolRegistry",
    "tool_registry",
    # Tier 1
    "get_weather",
    "add_numbers",
    "is_valid_email",
    # Tier 2
    "create_event",
    "search_products",
    "send_message",
    "set_reminder",
    # Tier 3
    "create_order",
    "schedule_meeting",
    "register_employee",
    "book_travel",
    # Tier 4
    "execute_action",
    "build_query",
    "send_notification",
]
