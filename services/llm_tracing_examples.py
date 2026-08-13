"""
Integration examples for LLM token tracing in JavaAPEX-Backend.

This module shows how to integrate token tracing with various LLM providers
used in the JavaAPEX backend.
"""

import time
import logging
from typing import Dict, Any, Optional
from services.llm_tracer import (
    record_llm_call,
    record_llm_call_manual,
    record_http_api_call,
    LLMCallTimer,
)

logger = logging.getLogger(__name__)


# ── Example 1: OpenAI SDK Integration ──────────────────────────────────────

def example_openai_integration():
    """
    Example: Using token tracing with OpenAI SDK.
    
    This shows how to wrap OpenAI API calls with automatic token tracking.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OpenAI SDK not installed. Install with: pip install openai")
        return
    
    client = OpenAI()
    
    # Time the API call
    start_time = time.time()
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Analyze this Java method for performance issues...",
            }
        ],
        max_tokens=1000,
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Record the call for cost tracking
    record = record_llm_call(
        model="gpt-4o-mini",
        response=response,
        endpoint="code_quality_analysis",  # Your task name
        role="java_analysis",              # Your category
        call_type="chat",
        duration_ms=duration_ms,
        attempt=1,
        is_retry=False,
    )
    
    print(f"✓ Call tracked: ${record.get('estimated_cost_usd', 'N/A')}")


# ── Example 2: Hugging Face Integration ────────────────────────────────────

def example_huggingface_integration():
    """
    Example: Tracking Hugging Face API calls.
    
    Hugging Face uses HTTP APIs without built-in token counts,
    so we estimate tokens from the response text.
    """
    import httpx
    
    api_key = "your-huggingface-api-key"
    model = "mistralai/Mistral-7B-Instruct-v0.2"
    endpoint = "code-analysis"
    prompt = "Analyze this Java code for security issues..."
    
    start_time = time.time()
    
    try:
        # Make HTTP request to Hugging Face
        response = httpx.post(
            "https://api-inference.huggingface.co/models/" + model,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 500}},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        response_text = result[0].get("generated_text", "")
    except Exception as e:
        logger.error(f"Hugging Face API error: {e}")
        response_text = ""
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Record the call (tokens will be estimated from response)
    record = record_http_api_call(
        provider="huggingface",
        model=model,
        endpoint=endpoint,
        response_text=response_text,  # Used for token estimation
        duration_ms=duration_ms,
    )
    
    print(f"✓ Hugging Face call tracked: ${record.get('estimated_cost_usd', 'N/A')}")


# ── Example 3: Groq Integration ────────────────────────────────────────────

def example_groq_integration():
    """
    Example: Tracking Groq API calls.
    
    Groq uses OpenAI-compatible API endpoint.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("OpenAI SDK not installed")
        return
    
    # Groq uses OpenAI-compatible endpoint
    client = OpenAI(
        api_key="your-groq-api-key",
        base_url="https://api.groq.com/openai/v1",
    )
    
    start_time = time.time()
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": "Generate Java 18 compatible code...",
            }
        ],
        max_tokens=2000,
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Record the call
    record = record_llm_call(
        model="llama-3.1-8b-instant",
        response=response,
        endpoint="code_generation",
        role="java_migration",
        duration_ms=duration_ms,
    )
    
    print(f"✓ Groq call tracked: ${record.get('estimated_cost_usd', 'N/A')}")


# ── Example 4: Manual Token Count Recording ────────────────────────────────

def example_manual_token_recording():
    """
    Example: Recording token counts manually.
    
    Use this when you have token counts from another source.
    """
    # Your custom LLM call (e.g., custom implementation, cached response, etc.)
    input_tokens = 150
    output_tokens = 250
    model = "gpt-4o"
    
    record = record_llm_call_manual(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        endpoint="custom_task",
        role="analysis",
        duration_ms=1234.5,
    )
    
    print(f"✓ Manual call recorded: {input_tokens + output_tokens} tokens, ${record.get('estimated_cost_usd')}")


# ── Example 5: Context Manager for Automatic Timing ──────────────────────

def example_context_manager():
    """
    Example: Using LLMCallTimer context manager.
    
    Automatically times the call and records it.
    """
    from services.llm_tracer import LLMCallTimer
    
    with LLMCallTimer(
        model="gpt-4o-mini",
        endpoint="test_generation",
        role="test_analysis",
    ) as timer:
        # Your LLM call here
        time.sleep(0.5)  # Simulated API call
        response_text = "Generated test code..."
    
    # After context exit, duration is automatically recorded
    record = record_http_api_call(
        provider="openai",
        model="gpt-4o-mini",
        endpoint="test_generation",
        response_text=response_text,
        duration_ms=timer.duration_ms,
    )
    
    print(f"✓ Timed call recorded in {timer.duration_ms:.1f}ms")


# ── Example 6: Integration with FastAPI Endpoint ──────────────────────────

async def example_fastapi_endpoint():
    """
    Example: Token tracing in a FastAPI endpoint.
    
    Shows how to integrate tracing into request handlers.
    """
    from fastapi import APIRouter, Request
    
    router = APIRouter()
    
    @router.post("/analyze-java-code")
    async def analyze_code(code_snippet: str, request: Request):
        """
        Analyze Java code using LLM and track the cost.
        """
        start_time = time.time()
        
        try:
            # Call your LLM (example with OpenAI)
            from openai import OpenAI
            client = OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Java expert. Analyze the code and suggest improvements.",
                    },
                    {"role": "user", "content": code_snippet},
                ],
                max_tokens=1000,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Record the LLM call
            record = record_llm_call(
                model="gpt-4o",
                response=response,
                endpoint="analyze_java_code",
                role="code_analysis",
                duration_ms=duration_ms,
                error=None,
            )
            
            return {
                "analysis": response.choices[0].message.content,
                "cost": record.get("estimated_cost_usd"),
                "tokens": {
                    "input": record.get("input_tokens"),
                    "output": record.get("output_tokens"),
                },
            }
        
        except Exception as e:
            # Record failed calls too
            duration_ms = (time.time() - start_time) * 1000
            
            record = record_llm_call_manual(
                model="gpt-4o",
                input_tokens=0,
                output_tokens=0,
                endpoint="analyze_java_code",
                duration_ms=duration_ms,
                error=str(e),
            )
            
            return {"error": str(e), "cost": None}
    
    return router


# ── Example 7: Batch Processing with Token Tracking ──────────────────────

async def example_batch_processing():
    """
    Example: Tracking token usage for batch LLM processing.
    
    Shows how to aggregate costs across multiple calls.
    """
    from services.llm_tracer import get_usage_stats
    
    files_to_analyze = [
        "file1.java",
        "file2.java",
        "file3.java",
    ]
    
    total_cost = 0.0
    total_tokens = 0
    
    for file_path in files_to_analyze:
        # Simulate LLM call
        record = record_llm_call_manual(
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=200,
            endpoint="batch_analysis",
            role="file_processor",
        )
        
        if record:
            total_cost += record.get("estimated_cost_usd", 0.0)
            total_tokens += (
                record.get("input_tokens", 0) + record.get("output_tokens", 0)
            )
    
    # Get aggregated stats
    stats = get_usage_stats()
    print(f"✓ Batch processing complete: {total_tokens} tokens, ${total_cost:.6f}")


# ── Example 8: Error Handling and Retries ────────────────────────────────

async def example_error_handling():
    """
    Example: Tracking errors and retry attempts.
    
    Shows how to record failed LLM calls for debugging and cost attribution.
    """
    import asyncio
    
    model = "gpt-4o"
    endpoint = "migration_task"
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            start_time = time.time()
            
            # Simulate LLM call
            if attempt == 3:  # Succeed on 3rd attempt
                response_tokens = 500
                duration_ms = (time.time() - start_time) * 1000
                
                record = record_llm_call_manual(
                    model=model,
                    input_tokens=200,
                    output_tokens=response_tokens,
                    endpoint=endpoint,
                    attempt=attempt,
                    is_retry=(attempt > 1),
                )
                
                print(f"✓ Success on attempt {attempt}")
                break
            else:
                raise TimeoutError("API timeout")
        
        except TimeoutError as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record the failed attempt
            record = record_llm_call_manual(
                model=model,
                input_tokens=200,
                output_tokens=0,
                endpoint=endpoint,
                attempt=attempt,
                is_retry=(attempt > 1),
                error=str(e),
                duration_ms=duration_ms,
            )
            
            if attempt < max_retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Attempt {attempt} failed, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} attempts")
                raise


# ── Example 9: Custom Pricing Provider ────────────────────────────────────

def example_custom_pricing():
    """
    Example: Integrating custom pricing for your organization.
    
    Shows how to define custom per-model rates.
    """
    import token_tracing as tt
    
    class JavaAPEXPricingProvider(tt.PricingProvider):
        """Custom pricing for JavaAPEX organization."""
        
        RATES = {
            "gpt-4o": (0.005, 0.015),           # Negotiated rates (input, output)
            "gpt-4o-mini": (0.00015, 0.0006),
            "llama-3.1-8b-instant": (0.05, 0.08),  # Groq rates per 1M tokens
            "mistral-7b": (0.00014, 0.00042),
        }
        
        def rates_for(self, model: str) -> Optional[tt.ModelRates]:
            key = (model or "").lower()
            if key not in self.RATES:
                return None
            
            input_rate, output_rate = self.RATES[key]
            return tt.ModelRates(
                input_per_1m=input_rate,
                output_per_1m=output_rate,
                cached_input_per_1m=None,  # Optional: cached prompt rate
            )
    
    # Use it
    custom_pricing = JavaAPEXPricingProvider()
    rate = custom_pricing.rates_for("gpt-4o")
    print(f"Custom rate for gpt-4o: ${rate.input_per_1m:.6f}/${rate.output_per_1m:.6f} per 1M")


if __name__ == "__main__":
    # Run examples (with appropriate imports/setup)
    print("LLM Token Tracing Integration Examples")
    print("=" * 50)
    
    # example_manual_token_recording()
    # example_context_manager()
    print("\nRun individual examples by uncommenting the calls above")
    print("\nFor FastAPI integration, see example_fastapi_endpoint()")
    print("For async batch processing, see example_batch_processing()")
