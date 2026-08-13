# Quick Start - LLM Token Tracing

## 30-Second Setup

Token tracing is **already initialized** when the server starts. That's it! ✓

## Track Your First LLM Call

```python
from services.llm_tracer import record_llm_call
import time

# Time your API call
start = time.time()
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Analyze this Java code..."}],
)
duration_ms = (time.time() - start) * 1000

# Record it (one line!)
record_llm_call(
    model="gpt-4o",
    response=response,
    endpoint="code_analysis",
    duration_ms=duration_ms,
)
```

## View Dashboard

Just open: **http://localhost:8000/api/llm/dashboard**

The dashboard auto-refreshes and shows:
- Total cost (USD)
- Token counts
- Cost by model
- Cost by endpoint
- Recent calls table
- Real-time filters

## Query API

```bash
# Get summary stats
curl http://localhost:8000/api/llm/summary

# Filter by model
curl "http://localhost:8000/api/llm/summary?model=gpt-4o"

# Get recent calls
curl http://localhost:8000/api/llm/records?limit=10

# Only errors
curl http://localhost:8000/api/llm/records?error_only=true

# Health check
curl http://localhost:8000/api/llm/health
```

## Key Integration Points

| Provider | Function | Example |
|----------|----------|---------|
| **OpenAI SDK** | `record_llm_call()` | Pass `response` object |
| **Manual counts** | `record_llm_call_manual()` | Pass token counts directly |
| **HTTP APIs** | `record_http_api_call()` | For Hugging Face, Groq, etc. |
| **Auto-timing** | `LLMCallTimer` | Context manager |

## File Locations

```
services/llm_tracer.py              # Main wrapper (use this)
services/token_tracing/             # Core library (auto-imported)
routers/llm_tracing_router.py       # API endpoints (auto-registered)
logs/llm_usage.jsonl                # Your data (auto-created)
LLM_TOKEN_TRACING.md                # Full documentation
services/llm_tracing_examples.py    # 9 complete examples
```

## Common Tasks

### Get total spending
```python
import requests
summary = requests.get("http://localhost:8000/api/llm/summary").json()
print(f"Total cost: ${summary['total_cost_usd']}")
```

### Alert on budget overspend
```python
if summary['total_cost_usd'] > DAILY_BUDGET:
    send_alert(f"Exceeded ${DAILY_BUDGET}: ${summary['total_cost_usd']}")
```

### Track specific endpoint
```bash
curl "http://localhost:8000/api/llm/summary?endpoint=code_analysis"
```

### Find failed calls
```bash
curl "http://localhost:8000/api/llm/records?error_only=true&limit=50"
```

## Supported Models

### Built-in pricing for 50+ models:
- **OpenAI**: gpt-4, gpt-4o, gpt-4o-mini, gpt-3.5-turbo
- **Groq**: llama-3.1-8b, llama-3.1-70b, mixtral-8x7b
- **Hugging Face**: Mistral, Llama, Zephyr, etc.
- **Anthropic**: Claude-3, Claude-2, etc.
- **More**: Azure, Cohere, Together, Replicate, etc.

Unknown models: Cost estimated to $0 (override with custom pricing)

## Zero Overhead

- ✓ No new dependencies
- ✓ < 1ms per call
- ✓ Thread-safe
- ✓ Async-safe
- ✓ Non-intrusive

## Detailed Documentation

- **Full guide**: Read `LLM_TOKEN_TRACING.md`
- **Code examples**: Check `services/llm_tracing_examples.py`
- **Integration test**: Run `python test_integration.py`

---

**That's it! Start tracking LLM costs today.**
