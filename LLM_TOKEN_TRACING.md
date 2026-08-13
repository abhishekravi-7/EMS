# LLM Token Tracing Integration

JavaAPEX-Backend now includes **automatic token usage tracking and cost estimation** for all LLM API calls.

## Quick Start

### 1. Token Tracing is Auto-Initialized

When the server starts, token tracing is automatically initialized:

```python
# In main.py startup event
init_llm_tracer(
    log_file="logs/llm_usage.jsonl",
    provider="openai",
)
```

Records are automatically persisted to `logs/llm_usage.jsonl`.

### 2. Track an LLM API Call

After each LLM provider call, record it:

```python
from services.llm_tracer import record_llm_call
import time

# Time your API call
start_time = time.time()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
)
duration_ms = (time.time() - start_time) * 1000

# Record the call
record = record_llm_call(
    model="gpt-4o-mini",
    response=response,
    endpoint="code_analysis",  # Your task name
    duration_ms=duration_ms,
)

print(f"Cost: ${record.get('estimated_cost_usd')}")
```

### 3. View Analytics

#### Option A: FastAPI Endpoints

The dashboard is exposed at `/api/llm/` with these endpoints:

- `GET /api/llm/summary` — Aggregated stats (cost, tokens, breakdowns by model/endpoint)
- `GET /api/llm/records?model=gpt-4o&limit=50` — Recent call records with filtering
- `GET /api/llm/health` — Check if token tracing is active
- `GET /api/llm/dashboard` — Standalone HTML dashboard with real-time charts

Example:

```bash
# Get summary stats
curl http://localhost:8000/api/llm/summary

# Get recent records
curl http://localhost:8000/api/llm/records?limit=10

# View dashboard
open http://localhost:8000/api/llm/dashboard
```

#### Option B: Command-Line Dashboard (Standalone)

```bash
# Run the built-in dashboard server
python -m token_tracing.dashboard \
    --jsonl logs/llm_usage.jsonl \
    --port 8765

# Open browser to http://127.0.0.1:8765/
```

## API Reference

### Recording Functions

#### `record_llm_call()`

Record an LLM call from an OpenAI SDK response object.

```python
from services.llm_tracer import record_llm_call

record = record_llm_call(
    model="gpt-4o",                   # Model name
    response=response,                 # OpenAI response object
    endpoint="migration_task",         # Task label
    role="java_analysis",              # Category (optional, default "chat")
    call_type="chat",                  # Call type (optional, default "chat")
    duration_ms=1234.5,                # Duration in ms
    attempt=1,                         # Attempt number (default 1)
    is_retry=False,                    # Is this a retry? (default False)
    error=None,                        # Error message (if call failed)
    max_tokens=2000,                   # Requested output limit (optional)
)
```

**Returns:** Dict with recorded data:
```python
{
    "timestamp": "2026-08-13T13:08:45.437Z",
    "provider": "openai",
    "model": "gpt-4o",
    "endpoint": "migration_task",
    "input_tokens": 150,
    "output_tokens": 500,
    "total_tokens": 650,
    "estimated_cost_usd": 0.0025,
    "duration_ms": 1234.5,
    # ... more fields
}
```

#### `record_llm_call_manual()`

Record token counts manually (when response object is unavailable).

```python
from services.llm_tracer import record_llm_call_manual

record = record_llm_call_manual(
    model="gpt-4o",
    input_tokens=100,
    output_tokens=250,
    endpoint="analysis_task",
    role="analysis",
    cached_tokens=50,  # Optional: cached prompt tokens
)
```

#### `record_http_api_call()`

Record HTTP API calls (Hugging Face, Groq, custom providers).

```python
from services.llm_tracer import record_http_api_call

record = record_http_api_call(
    provider="huggingface",                    # Provider name
    model="mistralai/Mistral-7B-Instruct",
    endpoint="code_review",
    input_tokens=200,
    output_tokens=500,                        # Optional (estimated from response_text if None)
    response_text="Generated analysis...",    # Used for token estimation
    duration_ms=2500,
)
```

### Timing Helper

Use `LLMCallTimer` context manager to automatically time calls:

```python
from services.llm_tracer import LLMCallTimer, record_http_api_call

with LLMCallTimer(model="gpt-4o", endpoint="task") as timer:
    # Your API call here
    response = api_call()

# timer.duration_ms is automatically set
record = record_http_api_call(
    provider="openai",
    model="gpt-4o",
    endpoint="task",
    response_text=response.text,
    duration_ms=timer.duration_ms,
)
```

### Query Functions

#### `get_tracer()`

Get the global TokenTracer instance.

```python
from services.llm_tracer import get_tracer

tracer = get_tracer()
```

#### `get_usage_stats()`

Get aggregated usage statistics.

```python
from services.llm_tracer import get_usage_stats

stats = get_usage_stats()
# {
#   "total_cost_usd": 12.34,
#   "total_tokens": 50000,
#   "num_records": 150,
#   "records": [...],
# }
```

## Integration Examples

See `services/llm_tracing_examples.py` for complete code examples:

1. **OpenAI SDK** — Token tracking with OpenAI Python SDK
2. **Hugging Face** — HTTP API integration with token estimation
3. **Groq** — OpenAI-compatible endpoint tracking
4. **Manual Counts** — Recording pre-calculated token counts
5. **Context Manager** — Automatic timing with `LLMCallTimer`
6. **FastAPI Endpoints** — Integration in request handlers
7. **Batch Processing** — Aggregating costs across multiple calls
8. **Error Handling** — Tracking failed calls and retries
9. **Custom Pricing** — Organization-specific rate tables

## Dashboard Features

The web dashboard (`GET /api/llm/dashboard`) provides:

- **Summary Cards** — Total cost, tokens, API calls
- **Model Breakdown** — Cost and usage by LLM model
- **Endpoint Breakdown** — Cost and usage by task/endpoint
- **Recent Calls Table** — Latest LLM calls with filtering
- **Real-Time Updates** — Auto-refresh every 5 seconds
- **CORS Enabled** — Call from any origin

### API Endpoints

```bash
# Get summary stats with optional filtering
GET /api/llm/summary
  ?model=gpt-4o
  &endpoint=code_analysis
  &error_only=false

# Response:
{
  "total_cost_usd": 12.34,
  "total_tokens": 50000,
  "total_input_tokens": 20000,
  "total_output_tokens": 30000,
  "num_records": 150,
  "by_model": {
    "gpt-4o": { "cost": 5.0, "calls": 50, ... },
    "gpt-4o-mini": { "cost": 7.34, "calls": 100, ... }
  },
  "by_endpoint": {
    "code_analysis": { "cost": 8.0, "calls": 60, ... },
    "migration_task": { "cost": 4.34, "calls": 90, ... }
  }
}

# Get recent call records
GET /api/llm/records
  ?model=gpt-4o
  &endpoint=code_analysis
  &error_only=false
  &limit=50

# Response: Array of LLMCallRecord objects

# Check health
GET /api/llm/health

# Response:
{
  "status": "active",
  "provider": "openai",
  "sink": "JsonlTraceSink"
}
```

## Data Storage

### Default: JSONL File

By default, records are persisted to `logs/llm_usage.jsonl` (one JSON object per line):

```jsonl
{"timestamp": "2026-08-13T13:08:45Z", "model": "gpt-4o", "input_tokens": 150, "output_tokens": 500, "estimated_cost_usd": 0.0025, ...}
{"timestamp": "2026-08-13T13:09:12Z", "model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 250, "estimated_cost_usd": 0.0005, ...}
```

File is rotated by your deployment/logging infrastructure.

### Custom: Database Storage

To store in a database instead, implement a custom `TraceSink`:

```python
import token_tracing as tt

class DatabaseSink(tt.TraceSink):
    def write(self, record: tt.LLMCallRecord) -> None:
        # Insert into your database
        db.llm_usage.insert(record.to_dict())

# Use it
from services.llm_tracer import init_llm_tracer
init_llm_tracer(
    sink=DatabaseSink(),
    provider="openai",
)
```

## Pricing Configuration

### Built-In Pricing

The package includes pricing tables for:

- OpenAI (all models)
- Groq (llama, mixtral)
- Hugging Face (Mistral, Llama, Zephyr)
- Anthropic (Claude)
- Many other models

Pricing is estimated as USD per 1M tokens.

### Custom Pricing

Define organization-specific rates:

```python
import token_tracing as tt

class JavaAPEXPricingProvider(tt.PricingProvider):
    """Custom pricing for negotiated rates."""
    
    def rates_for(self, model: str) -> tt.ModelRates | None:
        rates = {
            "gpt-4o": (0.005, 0.015),        # Custom negotiated rates
            "gpt-4o-mini": (0.00015, 0.0006),
            "llama-3-70b": (0.59, 0.79),
        }
        if model.lower() not in rates:
            return None
        input_rate, output_rate = rates[model.lower()]
        return tt.ModelRates(input_rate, output_rate)

# Use it
from services.llm_tracer import init_llm_tracer
init_llm_tracer(
    sink=tt.JsonlTraceSink("logs/llm_usage.jsonl"),
    pricing_provider=tt.ChainedPricingProvider(
        JavaAPEXPricingProvider(),      # Try custom rates first
        tt.StaticPricingProvider(),     # Fall back to built-in
    ),
    provider="openai",
)
```

## Monitoring & Alerting

### Query the Dashboard API

```python
import requests

# Get current spending
response = requests.get("http://localhost:8000/api/llm/summary")
summary = response.json()
print(f"Total cost: ${summary['total_cost_usd']}")

# Alert if spending exceeds threshold
DAILY_BUDGET = 100.00
if summary['total_cost_usd'] > DAILY_BUDGET:
    send_alert(f"LLM costs exceeded ${DAILY_BUDGET}: ${summary['total_cost_usd']}")

# Check for errors
errors = requests.get("http://localhost:8000/api/llm/records?error_only=true").json()
if errors:
    print(f"⚠️ {len(errors)} LLM errors detected")
```

### Periodic Reporting

```python
# scheduled_job.py
import requests
from datetime import datetime, timedelta

def daily_llm_cost_report():
    """Generate and send daily LLM cost report."""
    response = requests.get("http://localhost:8000/api/llm/summary")
    summary = response.json()
    
    report = f"""
    Daily LLM Cost Report ({datetime.now().date()})
    ================================================
    Total Cost: ${summary['total_cost_usd']:.2f}
    Total Tokens: {summary['total_tokens']:,}
    API Calls: {summary['num_records']}
    
    By Model:
    {format_by_model(summary['by_model'])}
    
    By Endpoint:
    {format_by_endpoint(summary['by_endpoint'])}
    """
    
    send_email(to="devops@company.com", subject="Daily LLM Report", body=report)

# Run daily at 9 AM
schedule.every().day.at("09:00").do(daily_llm_cost_report)
```

## Troubleshooting

### No Records in Dashboard

1. Check that token tracing initialized at startup (look for `✓ LLM token tracing initialized` in logs)
2. Verify `logs/llm_usage.jsonl` exists and is writable
3. Ensure you're calling `record_llm_call()` after each LLM API call
4. Check API response has `.usage` attribute (OpenAI SDK responses)

### Cost Estimates are $0 or None

1. Model may not be in pricing tables — check if it's a custom/new model
2. Token counts may be missing from the response — verify `.usage` has `prompt_tokens` and `completion_tokens`
3. For Hugging Face/HTTP APIs, `record_http_api_call()` estimates tokens from response text

### Dashboard API Returns Empty

1. If using JSONL sink: file may not exist yet (create first LLM call to initialize)
2. For embedded dashboard: ListTraceSink only available in testing; use standalone dashboard for production
3. CORS may be blocking requests from frontend — verify `/api/llm/*` endpoints are included in CORS policy

## Performance Notes

- **Zero overhead** when sink is `NullTraceSink` (default in production if not initialized)
- **Thread-safe** — `JsonlTraceSink` uses locks for concurrent writes
- **Async-safe** — can call from both sync and async code
- **No SDK monkey-patching** — fully non-intrusive

## Next Steps

1. **Add tracing to LLM call sites** — See `services/llm_tracing_examples.py`
2. **Configure custom pricing** — Set organization-specific rates
3. **Set up alerts** — Monitor spending and error rates
4. **Route dashboard** — Expose `/api/llm/dashboard` to team
5. **Daily reports** — Generate cost summaries for finance/ops

## Support

For issues or questions:

1. Check `logs/llm_usage.jsonl` for recorded calls
2. Review examples in `services/llm_tracing_examples.py`
3. Run `/api/llm/health` endpoint to verify tracer status
4. Check FastAPI logs for initialization messages

---

**Token Tracing Integration**: Zero dependencies, pluggable design, production-ready.
