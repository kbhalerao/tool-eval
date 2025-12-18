# Tool Calling Capabilities of Local LLMs: An Empirical Evaluation

**Abstract**: We evaluate tool calling capabilities across four local LLMs (Granite Tiny, Qwen 30B, Qwen 80B, Nemotron) using a 7-tier test suite of 125 test cases. Results show all models achieve 100% on primitive tasks, but diverge significantly on union types (70-100%), nested structures (68-93%), and strategic reasoning (70-95%). Thinking models provide substantial accuracy gains on complex tasks (+9-25%) at 2-3x latency cost, but offer no benefit for pattern-matching tasks like tool selection.

---

## 1. Introduction

This evaluation measures tool calling capabilities of local LLMs to answer:

1. **At what complexity do models fail?**
2. **When does thinking overhead pay off?**
3. **What distinguishes reliability from capability?**

### Infrastructure

- **Server**: LMStudio via OpenAI-compatible `/v1/responses` API
- **Harness**: Custom Python framework with Pydantic tool schemas
- **Scoring**: Exact match with tolerance for optional parameters (omission = null)

### Models Tested

| Model | Type | Parameters |
|-------|------|------------|
| Granite Tiny | Non-thinking | ~3B |
| Qwen 30B | Non-thinking | 30B |
| Qwen 80B | Non-thinking | 80B |
| Nemotron Nano | Thinking | ~8B |

---

## 2. Tier 1: Primitive Parameters (13 tests)

Single-parameter tools with basic types: `get_weather(city)`, `add_numbers(a, b)`, `is_valid_email(email)`.

### Sample Test Cases

```yaml
# Direct extraction
- prompt: "What's the weather in San Francisco?"
  expected_tool: get_weather
  expected_args: { city: "San Francisco" }

# Contextual extraction
- prompt: "I have 42 apples and my friend gives me 18 more. How many do I have?"
  expected_tool: add_numbers
  expected_args: { a: 42, b: 18 }

# Abbreviation handling
- prompt: "Get me the weather for NYC"
  expected_tool: get_weather
  expected_args: { city: "New York City" }
```

### Results

| Model | Success | Tool Acc | Arg Score | Latency | Thinking |
|-------|---------|----------|-----------|---------|----------|
| Qwen 30B | 100% | 100% | 0.85 | 797ms | 0 |
| Granite Tiny | 100% | 100% | 0.85 | 886ms | 0 |
| Qwen 80B | 100% | 100% | 0.85 | 1,279ms | 0 |
| Nemotron | 100% | 100% | 0.85 | 1,649ms | 1,867 (45%) |

**Finding**: All models saturate at 100% tool selection. Tier 1 does not differentiate models.

The 0.85 arg score reflects abbreviation handling—models pass "NYC" directly rather than expanding to "New York City". This is arguably correct behavior (the model shouldn't assume expansion rules).

---

## 3. Tier 2: Structured Types (21 tests)

Complex parameter types: dates, lists, optionals, enums.

**Tools**:
- `create_event(title, date, attendees[])` — date parsing + list extraction
- `search_products(query, max_price?, category?)` — optional parameters
- `send_message(to, subject, body, priority)` — enum (low/normal/high)
- `set_reminder(title, date, tags[]?)` — optional list

### Sample Test Cases

```yaml
# Date + list extraction
- prompt: "Create an event called 'Team Sync' on 2025-01-15 with attendees alice@co.com and bob@co.com"
  expected_tool: create_event
  expected_args:
    title: "Team Sync"
    date: "2025-01-15"
    attendees: ["alice@co.com", "bob@co.com"]

# Optional parameter inference
- prompt: "I'm looking for a budget wireless mouse, nothing over fifty dollars"
  expected_tool: search_products
  expected_args:
    query: "wireless mouse"
    max_price: 50
    category: null

# Enum inference from tone
- prompt: "ASAP - email cto@startup.com, subject 'Security breach detected', tell them 'We found unauthorized access in the logs'"
  expected_tool: send_message
  expected_args:
    to: "cto@startup.com"
    subject: "Security breach detected"
    body: "We found unauthorized access in the logs"
    priority: "high"  # inferred from "ASAP"
```

### Results

| Model | Success | Tool Acc | Arg Score | Latency | Thinking |
|-------|---------|----------|-----------|---------|----------|
| **Nemotron** | 100% | 100% | **0.97** | 3,799ms | 4,401 (44%) |
| Qwen 30B | 100% | 100% | 0.94 | 2,020ms | 0 |
| Qwen 80B | 100% | 100% | 0.94 | 2,796ms | 0 |
| Granite Tiny | 100% | 100% | 0.90 | 2,554ms | 0 |

**Finding**: Thinking model achieves highest arg score (+3%) at 2x latency cost.

### Token Efficiency

| Model | Tokens/Test | Arg Score | Tokens per 0.01 Score |
|-------|-------------|-----------|----------------------|
| Granite Tiny | 41 | 0.90 | 0.46 |
| Qwen 30B | 45 | 0.94 | 0.48 |
| Qwen 80B | 44 | 0.94 | 0.47 |
| Nemotron | 269 | 0.97 | 2.77 |

Nemotron uses 6x more tokens for +3% improvement. At Tier 2 complexity, thinking is inefficient.

---

## 4. Tier 3: Nested Objects (13 tests)

Deeply nested structures: objects within objects, arrays of objects.

**Tools**:
- `create_order(customer, items[], shipping)` — nested customer + array of items + nested address
- `schedule_meeting(participants[], time_slots[], room?)` — arrays of objects + optional nested
- `register_employee(employee{contact{address}})` — 3-level nesting
- `book_travel(traveler, origin, destination)` — multiple address objects

### Sample Test Cases

```yaml
# Nested customer + array of items + shipping address
- prompt: |
    Order for Jane Doe (jane.doe@corp.com, phone 555-1234):
    - 3x WIDGET-A at $15.00
    - 1x GADGET-B at $45.50
    Ship to 456 Oak Ave, San Francisco, CA 94102
  expected_tool: create_order
  expected_args:
    customer:
      name: "Jane Doe"
      email: "jane.doe@corp.com"
      phone: "555-1234"
    items:
      - { product_id: "WIDGET-A", quantity: 3, unit_price: 15.00 }
      - { product_id: "GADGET-B", quantity: 1, unit_price: 45.50 }
    shipping:
      street: "456 Oak Ave"
      city: "San Francisco"
      state: "CA"
      zip_code: "94102"
      country: "USA"

# 3-level nesting: employee → contact → address
- prompt: |
    Register new employee: Tom Wilson in Engineering department.
    Contact: tom.wilson@company.com, phone 555-9876.
    Office: 789 Tech Park, Austin, TX 78701.
    Starting 2025-01-20.
  expected_tool: register_employee
  expected_args:
    employee:
      name: "Tom Wilson"
      department: "Engineering"
      contact:
        email: "tom.wilson@company.com"
        phone: "555-9876"
        address:
          street: "789 Tech Park"
          city: "Austin"
          state: "TX"
          zip_code: "78701"
          country: "USA"
      manager_email: null
    start_date: "2025-01-20"

# Prose-style extraction (harder)
- prompt: |
    Hey, I need to order some stuff. I'm Mike Johnson and you can reach me at
    mike.j@gmail.com. Send it to my house at 42 Elm Street in Portland, Oregon,
    zip code 97201. I want 4 of those BLUE-WIDGET things at $12.50 each.
  expected_tool: create_order
  expected_args:
    customer:
      name: "Mike Johnson"
      email: "mike.j@gmail.com"
      phone: null
    items:
      - { product_id: "BLUE-WIDGET", quantity: 4, unit_price: 12.50 }
    shipping:
      street: "42 Elm Street"
      city: "Portland"
      state: "Oregon"
      zip_code: "97201"
      country: "USA"
```

### Results

| Model | Success | Tool Acc | Arg Score | Latency | Thinking |
|-------|---------|----------|-----------|---------|----------|
| **Nemotron** | 100% | 100% | **0.93** | 9,748ms | 11,803 (46%) |
| Qwen 80B | 100% | 100% | 0.84 | 4,375ms | 0 |
| Granite Tiny | 100% | 100% | 0.71 | 4,764ms | 0 |
| Qwen 30B | 100% | 100% | 0.68 | 3,487ms | 0 |

**Finding**: Thinking provides **+9-25% arg score** on nested objects vs non-thinking models.

### Why Thinking Helps

Nested structures have 20+ fields to populate correctly. Common errors from non-thinking models:
- Missing optional nested fields (`room.location: null`)
- Incomplete list items (missing `required` field in participants)
- Format variations (`2025-02-03T14:00` vs `2025-02-03T14:00:00`)
- State abbreviation vs full name ("Oregon" vs "OR")

Nemotron's explicit reasoning about each field catches these errors. The 46% thinking overhead pays off at this complexity level.

---

## 5. Tier 4: Polymorphic/Union Types (18 tests)

Discriminated unions with `anyOf` and `const` discriminators.

**Tools**:
- `execute_action(action: Create|Update|Delete)` — CRUD discriminated union
- `build_query(filters: Text|Numeric|Date[])` — mixed filter types
- `send_notification(notification: Email|SMS|Push)` — channel variants

### Sample Test Cases

```yaml
# Create variant
- prompt: "Create a new user named 'Alice Johnson'"
  expected_tool: execute_action
  expected_args:
    action:
      action_type: "create"
      resource_type: "user"
      name: "Alice Johnson"
      metadata: null

# Delete variant with soft_delete flag
- prompt: "Soft delete the comment with ID cmt_55555 - we might need to restore it later"
  expected_tool: execute_action
  expected_args:
    action:
      action_type: "delete"
      resource_id: "cmt_55555"
      soft_delete: true

# Mixed filter types
- prompt: |
    Search for active users whose email starts with "admin" and who signed up
    between 2024-06-01 and 2024-12-31. Sort by signup date ascending, show 50 per page.
  expected_tool: build_query
  expected_args:
    filters:
      - { filter_type: "text", field: "status", operator: "equals", value: "active" }
      - { filter_type: "text", field: "email", operator: "starts_with", value: "admin" }
      - { filter_type: "date", field: "signup_date", operator: "between", value: "2024-06-01", value2: "2024-12-31" }
    sort: { field: "signup_date", direction: "asc" }
    pagination: { page: 1, page_size: 50 }

# Notification variant selection
- prompt: "Text +1-555-123-4567: 'Your order has shipped!'"
  expected_tool: send_notification
  expected_args:
    notification:
      channel: "sms"
      phone_number: "+1-555-123-4567"
      message: "Your order has shipped!"
    priority: "normal"
```

### Results

| Model | Success | Tool Acc | Arg Score | Latency | Thinking |
|-------|---------|----------|-----------|---------|----------|
| Granite Tiny | **72.2%** | 72.2% | 0.57 | 3,804ms | 0 |
| Qwen 30B | 94.4% | 94.4% | 0.86 | 3,256ms | 0 |
| **Nemotron** | 100% | 100% | 0.88 | 5,450ms | 6,443 (45%) |
| **Qwen 80B** | 100% | 100% | **0.92** | 3,111ms | 0 |

**Finding**: Tier 4 reveals **reliability degradation**, not capability limits.

### Failure Analysis

Running Granite on the same Update action 10 times: **80% success rate**. The model CAN handle unions, but inconsistently.

| Test Category | Granite Reliability |
|---------------|---------------------|
| `build_query` (Text\|Numeric\|Date filters) | **100%** |
| `send_notification` (Email\|SMS\|Push) | **~95%** |
| `execute_action` Create variant | **100%** |
| `execute_action` Update/Delete variants | **~50%** |

The failure isn't union types generally—Granite handles query filters and notifications. The specific failure is on CRUD Update/Delete:
- Create has clear noun signals: "Create a new user named..."
- Update/Delete require parsing IDs and understanding modification semantics
- The model sometimes outputs text instead of calling the tool

---

## 6. Tier 5: Multi-Tool Selection (16 tests)

13 similar tools presented simultaneously. Tests tool selection accuracy with distractors.

**Tool categories**:
- 5 search tools: `search_users`, `search_documents`, `search_calendar`, `search_files`, `search_inventory`
- 4 send tools: `send_email`, `send_slack`, `send_sms`, `send_webhook`
- 4 create tools: `create_task`, `create_event`, `create_note`, `create_reminder`

### Results

| Model | Success | Tool Acc | Arg Score | Latency | Notes |
|-------|---------|----------|-----------|---------|-------|
| **Qwen 30B** | **100%** | **100%** | 0.81 | 3,053ms | Picks decisively |
| Granite Tiny | 93.8% | 93.8% | 0.77 | 3,022ms | Failed webhook |
| Nemotron | 93.8% | 93.8% | 0.78 | 5,140ms | Refused ambiguous |
| Qwen 80B | 93.8% | 93.8% | 0.80 | 3,734ms | Refused ambiguous |

**Finding**: Tier 5 (13 distractors) was EASIER than Tier 4 (3-way union).

**Why distractors are easier than unions**:
- Tool selection = pattern matching on descriptions ("send email" vs "send slack")
- Union discrimination = schema comprehension (which variant schema applies?)
- Models are trained heavily on tool selection; union types are rarer

**Thinking didn't help**—Nemotron matched Granite's 93.8%. Tool selection is fast pattern matching, not deliberate reasoning.

**Larger models refuse ambiguity**: On "Message the team about the release" (could be Slack or email), Qwen 80B and Nemotron returned nothing. Qwen 30B picked Slack. This reflects a caution vs. decisiveness tradeoff.

---

## 7. Tier 6: Strategic Tool Selection (20 tests)

Tests strategic reasoning: given multiple valid tools, does the model choose the optimal research strategy? Modeled on a real agronomic research agent.

**Tools** (~8KB total schema):
- `product_first_search` — Catalog search → trial enrichment (discovery, brand lookup)
- `trial_first_search` — Performance data → top products (analytics, condition-specific)
- `compare_products` — Head-to-head comparison

**Key feature**: Required `rationale` field forces model to explain reasoning.

### Sample Test Cases

```
Discovery: "What corn hybrids are available for my farm near Ames, Iowa?"
→ product_first_search (catalog lookup first)

Performance: "What's been winning in trials around Story County?"
→ trial_first_search (analytics query)

Condition-specific: "Best soybeans for heavy clay ground"
→ trial_first_search (filter by soil condition)

Comparison: "I'm torn between Pioneer P1185 and DeKalb 52-59"
→ compare_products (head-to-head)
```

### Results

| Model | Strategy Acc | Arg Score | Latency | Notes |
|-------|--------------|-----------|---------|-------|
| **Qwen 30B** | **95%** | 0.21 | 3,673ms | |
| **Qwen 80B** | **95%** | **0.37** | 5,328ms | Better schema construction |
| Nemotron | 90% | 0.30 | 16,780ms | 1 timeout |
| Granite Tiny | 70% | 0.21 | 6,235ms | Defaults to product_first |

*Note: Low arg scores reflect scoring artifact—expected_args didn't include required `rationale` field. Strategy accuracy is the meaningful metric.*

### Failure Analysis

**Granite defaults to `product_first_search`** for everything, missing:

| Missed Signal | Example | Correct Strategy |
|---------------|---------|------------------|
| Performance language | "What's been winning..." | trial_first |
| Condition filters | "Best for clay soil" | trial_first |
| Reliability signals | "Won't let me down" | trial_first (consistency) |
| Comparison requests | "I'm torn between..." | compare_products |

**One "failure" was correct reasoning**:
- Prompt: "How does DeKalb 52-59 stack up against similar maturity corn?"
- Expected: `compare_products`
- Actual: `product_first_search`
- Model rationale: "Requires first identifying available products with comparable maturity ranges before direct comparison"

This is correct—you can't compare without knowing what to compare. The test case was wrong.

### Rationale Quality

The `rationale` field revealed reasoning differences:

**Qwen 30B** (analytical):
> "User is asking about available corn hybrids near their farm. This is a discovery query where the user wants to know what products are available..."

**Granite** (terse):
> "First step to retrieve a list of corn products and then evaluate trial data if needed."

**Nemotron** (explanatory):
> "User wants to know which corn hybrids are available for their farm near Ames, IA; need to search the product catalog..."

---

## 8. Tier 7: Text-to-SQL (24 tests)

SQL generation against SQLite Sakila database (DVD rentals: films, actors, customers, rentals, payments).

**Tool**: `execute_sql(sql, rationale)`

**Complexity levels**:
- **Simple** (4): COUNT, WHERE, AVG, ORDER BY
- **Medium** (4): 2-table joins
- **Hard** (4): Multi-table joins with aggregation
- **Expert** (4): Subqueries, NOT EXISTS, geographic joins
- **Master** (8): CTEs, window functions (RANK, DENSE_RANK, NTILE, LAG), self-joins

### Results

| Model | Tool Selection | SQL Valid | Semantic Correct | Notes |
|-------|---------------|-----------|------------------|-------|
| Qwen 30B v1 | 100% | 96% | 92% | Used DATE_FORMAT (MySQL) |
| **Qwen 30B v2** | **100%** | **100%** | **100%** | Dialect hint fixed it |
| Nemotron v1 | 100% | 100% | ~69% | Used 'Penelope' (lowercase) |
| **Nemotron v2** | **100%** | **100%** | **~100%** | UPPERCASE hint fixed it |
| Granite | 83% | 50% | varies | Selected wrong tool |

**v2 dialect hints**:
```
IMPORTANT - SQLite dialect:
- Use strftime('%Y-%m', date_col) for month extraction
- String values are UPPERCASE (e.g., first_name='PENELOPE')
- Use || for string concatenation, not CONCAT()
```

### Key Findings

1. **Dialect matters more than capability**: Models know CTEs, window functions, self-joins—but default to MySQL/PostgreSQL syntax. Simple hints fix this.

2. **Different failure modes**: Nemotron produced syntactically valid SQL every time but made semantic errors (case sensitivity). Non-thinking models made syntax errors but got semantics right.

3. **Small models have tool selection issues**: Granite frequently called `grep` instead of `execute_sql`. When it did call SQL, it could write CTEs and window functions.

### Implication for Agents

A specialist SQL agent has dialect knowledge in its system prompt. The failures aren't capability gaps—they're **knowledge gaps** that disappear with specialization.

This validates the "specialist agent" architecture: smaller models with domain-specific prompts can match larger generalist models.

---

## 9. Summary of Findings

### Thinking Models: Value Scales with Complexity

| Tier | Thinking Benefit | Notes |
|------|------------------|-------|
| T1 (primitives) | None | All models saturate at 100% |
| T2 (structured) | +3% arg score | 6x tokens for marginal gain |
| T3 (nested) | +9-25% arg score | Substantial, worth the cost |
| T4 (unions) | 100% vs 72% | Critical for reliability |
| T5 (distractors) | None | Pattern matching, not reasoning |
| T6 (strategy) | 90% vs 70% | Helps with intent comprehension |
| T7 (SQL) | Different mode | Valid syntax, wrong semantics |

**Thinking overhead stays constant (~45%)** but accuracy gains increase with complexity.

### Model Size vs Performance

| Tier | Finding |
|------|---------|
| T2 | All models ~100%, Granite trails by 4% |
| T3 | Qwen 80B > Granite > Qwen 30B |
| T4 | Granite ~70% (stochastic), Qwen 30B ~94%, larger 100% |
| T6 | Granite 70% vs 95% for Qwen models |

Small models don't lack **capability**—they lack **reliability** and **intent comprehension**.

### Prompt Robustness

All models handled:
- Natural language variations ("Add 5 and 3" vs "sum of 5 and 3")
- Contextual extraction ("I have 42 apples and friend gives 18 more")
- Enum inference ("ASAP" → priority=high)

Challenges:
- Abbreviations: "NYC" not expanded to "New York City"
- Relative dates: Models can't compute "tomorrow" without date context

### Schema Compatibility (LMStudio)

- `/v1/responses` API rejects `anyOf` schemas (500 error)
- Pydantic `$ref` / `$defs` must be resolved to inline definitions
- `default: null` causes server errors—omit optional defaults
- Nested object schemas work when properly inlined (~1.5-2KB per tool)

---

## 10. Recommendations

### Model Selection by Task

| Task Type | Recommended Model |
|-----------|-------------------|
| Simple tools (T1-T2) | Any model; prefer Qwen 30B for speed |
| Nested structures (T3) | Thinking model (+25% accuracy) |
| Union types (T4) | Qwen 80B+ or add retries |
| Strategic selection (T6) | Qwen 30B+ for intent comprehension |
| Text-to-SQL (T7) | Include dialect hints; specialist prompts |

### Production Considerations

1. **Consider reliability, not just capability**. A 70% reliable model needs retry logic.
2. **Add a `rationale` field** to tool schemas for diagnostic insight.
3. **Schema design**: Inline nested objects, keep union variant descriptions, avoid `$ref`.
4. **Specialist agents**: Domain knowledge in prompts can close the gap between small and large models.

---

## 11. Future Work

### Multi-Agent Orchestration

The finding that small models are 100% reliable on simple tasks but fail on complex reasoning suggests orchestration patterns:

**Router Architecture**
```
User Query → Router (small, fast) → Simple | Medium | Complex
                                      ↓        ↓         ↓
                                   Granite  Qwen30B  Qwen80B
```

**Failure Detection & Escalation**
- No tool call when expected → escalate
- Repeated tool calls → stuck in loop
- Low confidence language → escalate
- Schema validation failures → retry with larger model

### Open Questions

1. **When is orchestration worth it?** Models have similar latency (~5s). Orchestration overhead may not pay off unless there's a 10x latency gap or API pricing difference.

2. **Can small models be reliable workers?** Granite at 70% on complex tasks isn't production-ready. But 100% on simple tasks means decomposition could work.

3. **Is specialization better than scale?** Few-shot prompting vs larger models for domain tasks?

---

## Appendix: Harness

```
tool-test/
├── src/tool_eval/
│   ├── tools/          # Pydantic tool definitions
│   ├── harness/        # Runner, metrics, scoring
│   └── client.py       # LMStudio API wrapper
├── tests/              # YAML test cases (125 total)
└── results/            # JSONL output files
```

```bash
# Run tier tests
uv run tool-eval --model "qwen/qwen3-30b" run --tier 2

# Compare results
uv run tool-eval compare results/model1.jsonl results/model2.jsonl
```
