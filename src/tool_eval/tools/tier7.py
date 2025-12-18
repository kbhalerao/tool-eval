"""Tier 7: Text-to-SQL generation against Sakila database."""

import sqlite3
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Literal

from .registry import tool_registry

DB_PATH = Path(__file__).parent.parent.parent.parent / "sakila.db"

SCHEMA_SUMMARY = """
Sakila DVD Rental Database Schema:

TABLES:
- actor (actor_id, first_name, last_name)
- film (film_id, title, description, release_year, language_id, rental_duration, rental_rate, length, replacement_cost, rating)
- film_actor (actor_id, film_id) -- many-to-many join
- category (category_id, name)
- film_category (film_id, category_id) -- many-to-many join
- language (language_id, name)
- customer (customer_id, store_id, first_name, last_name, email, address_id, active)
- rental (rental_id, rental_date, inventory_id, customer_id, return_date, staff_id)
- payment (payment_id, customer_id, staff_id, rental_id, amount, payment_date)
- inventory (inventory_id, film_id, store_id)
- store (store_id, manager_staff_id, address_id)
- staff (staff_id, first_name, last_name, address_id, email, store_id, active, username)
- address (address_id, address, district, city_id, postal_code, phone)
- city (city_id, city, country_id)
- country (country_id, country)

KEY RELATIONSHIPS:
- film -> film_actor -> actor (films have many actors)
- film -> film_category -> category (films have categories)
- film -> inventory -> rental -> customer (rental chain)
- rental -> payment (payments for rentals)
- customer/staff/store -> address -> city -> country (location hierarchy)

NOTES:
- rental_rate is per-day rental price
- replacement_cost is film replacement value
- rating is MPAA rating (G, PG, PG-13, R, NC-17)
- Dates are TIMESTAMP format

IMPORTANT - SQLite dialect:
- This is SQLite, NOT MySQL or PostgreSQL
- Use strftime('%Y-%m', date_col) for month extraction, NOT DATE_FORMAT or DATE_TRUNC
- String values are UPPERCASE (e.g., first_name='PENELOPE' not 'Penelope')
- Use || for string concatenation, not CONCAT()
"""


class SQLQueryArgs(BaseModel):
    """Execute a SQL query against the Sakila database."""

    sql: str = Field(
        description="The SQL query to execute. Must be a SELECT statement."
    )
    rationale: str = Field(
        description="Explanation of query logic: which tables are joined and why, "
        "what aggregations are used, how the result answers the question."
    )


@tool_registry.register(
    tier=7,
    description=f"Execute a SQL query against the Sakila DVD rental database. "
    f"Use this to answer questions about films, actors, customers, rentals, and revenue. "
    f"\n\n{SCHEMA_SUMMARY}"
)
def execute_sql(args: SQLQueryArgs) -> dict:
    """Execute SQL query and return results."""

    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    # Basic safety check
    sql_lower = args.sql.lower().strip()
    if not sql_lower.startswith("select"):
        return {"error": "Only SELECT queries are allowed"}

    dangerous = ["drop", "delete", "update", "insert", "alter", "create", ";--"]
    for word in dangerous:
        if word in sql_lower:
            return {"error": f"Query contains forbidden keyword: {word}"}

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(args.sql)

        rows = cursor.fetchmany(100)  # Limit results
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        results = [dict(row) for row in rows]
        total_rows = len(results)

        # Check if there are more
        if cursor.fetchone():
            total_rows = "100+ (truncated)"

        conn.close()

        return {
            "columns": columns,
            "rows": results,
            "row_count": total_rows,
            "sql": args.sql,
        }

    except sqlite3.Error as e:
        return {"error": f"SQL error: {str(e)}", "sql": args.sql}
    except Exception as e:
        return {"error": str(e), "sql": args.sql}
