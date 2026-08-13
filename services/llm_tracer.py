"""
LLM tracer integration for JavaAPEX-Backend.
Wraps OpenAI/LLM calls and records token usage + cost estimates.

Provides a simple interface to record all LLM API calls for cost tracking,
usage analytics, and dynamic pricing integration.

Supports multiple LLM providers:
  - OpenAI (via SDK or direct API)
  - Groq (OpenAI-compatible endpoint)
  - Hugging Face (via HTTP API)
  - Any OpenAI-compatible provider
"""

import time
from typing import Optional, Any, Dict, Union
from services import token_tracing as tt
import logging

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[tt.TokenTracer] = None


def init_llm_tracer(
    log_file: str = "logs/llm_usage.jsonl",
    provider: str = "openai",
    custom_pricing_provider: Optional[tt.PricingProvider] = None,
) -> None:
    """
    Initialize the global token tracer at application startup.
    
    Parameters
    ----------
    log_file : str
        Path to JSONL file for storing LLM call records (default: logs/llm_usage.jsonl)
    provider : str
        Default provider label (default: "openai")
    custom_pricing_provider : PricingProvider, optional
        Custom pricing provider (e.g., database-backed rates).
        If provided, it will be tried before the built-in static rates.
    """
    global _tracer
    
    # Create sink for persistence
    try:
        sink = tt.JsonlTraceSink(log_file)
        logger.info(f"✓ LLM tracer sink initialized: {log_file}")
    except Exception as e:
        logger.warning(f"Failed to initialize JsonlTraceSink at {log_file}: {e}")
        sink = tt.ListTraceSink()  # Fallback to in-memory
    
    # Chain pricing providers
    if custom_pricing_provider:
        pricing = tt.ChainedPricingProvider(
            custom_pricing_provider,
            tt.StaticPricingProvider(),  # Built-in fallback
        )
        logger.info("✓ Custom pricing provider registered (with static fallback)")
    else:
        pricing = tt.StaticPricingProvider()
        logger.info("✓ Using built-in static pricing")
    
    # Create tracer
    _tracer = tt.TokenTracer(
        sink=sink,
        pricing_provider=pricing,
        provider=provider,
    )
    
    logger.info(f"✓ Token tracing initialized (provider={provider})")


def record_llm_call(
    model: str,
    response: Any,
    endpoint: str,
    role: str = "chat",
    call_type: str = "chat",
    duration_ms: float = 0.0,
    attempt: int = 1,
    is_retry: bool = False,
    error: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Record an LLM API call.
    
    Call this immediately after each LLM provider call to log token usage,
    estimate costs, and persist the record.
    
    Parameters
    ----------
    model : str
        Model name (e.g., "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo")
    response : Any
        OpenAI response object with .usage attribute containing:
        - .prompt_tokens (input token count)
        - .completion_tokens (output token count)
        - .total_tokens (sum)
    endpoint : str
        Task label/endpoint name (e.g., "code_analysis", "test_generation", 
        "java7_migration", "dependency_detection")
    role : str, optional
        Call category (default "chat"). Use custom values to tag call types
        (e.g., "code_analysis", "test_gen", "refactor_check")
    call_type : str, optional
        Type of call (default "chat"). Options: "chat", "chat_stream", etc.
    duration_ms : float, optional
        Call duration in milliseconds (default 0.0)
    attempt : int, optional
        Retry attempt number, 1-based (default 1)
    is_retry : bool, optional
        Whether this is a retry of a previous failed call (default False)
    error : str, optional
        Error message if the call failed (default None)
    max_tokens : int, optional
        Maximum tokens requested (default None)
    
    Returns
    -------
    dict
        The recorded LLMCallRecord as a dict (also persisted to sink).
        Contains: timestamp, model, endpoint, input_tokens, output_tokens,
                  total_tokens, estimated_cost_usd, and more.
    
    Examples
    --------
    >>> import time
    >>> from openai import OpenAI
    >>> from services.llm_tracer import record_llm_call, init_llm_tracer
    >>> 
    >>> init_llm_tracer()
    >>> client = OpenAI()
    >>> 
    >>> start = time.time()
    >>> response = client.chat.completions.create(
    ...     model="gpt-4o-mini",
    ...     messages=[{"role": "user", "content": "Analyze this Java code..."}],
    ... )
    >>> duration_ms = (time.time() - start) * 1000
    >>> 
    >>> record = record_llm_call(
    ...     model="gpt-4o-mini",
    ...     response=response,
    ...     endpoint="code_analysis",
    ...     role="java_migration",
    ...     duration_ms=duration_ms,
    ... )
    >>> print(f"Cost: ${record.get('estimated_cost_usd', 'N/A')}")
    """
    global _tracer
    if _tracer is None:
        init_llm_tracer()
    
    try:
        record = _tracer.record_from_response(
            resp=response,
            role=role,
            model=model,
            call_type=call_type,
            duration_ms=duration_ms,
            attempt=attempt,
            is_retry=is_retry,
            endpoint=endpoint,
            error=error,
            max_tokens=max_tokens,
        )
        result = record.to_dict()
        
        # Log the call
        logger.debug(
            f"Recorded LLM call: model={model} endpoint={endpoint} "
            f"tokens=({result.get('input_tokens')}/{result.get('output_tokens')}) "
            f"cost=${result.get('estimated_cost_usd', 'N/A')}"
        )
        return result
    except Exception as e:
        logger.exception(f"Failed to record LLM call for {model}/{endpoint}: {e}")
        return {}


def record_llm_call_manual(
    model: str,
    input_tokens: int,
    output_tokens: int,
    endpoint: str,
    role: str = "chat",
    call_type: str = "chat",
    duration_ms: float = 0.0,
    attempt: int = 1,
    is_retry: bool = False,
    error: Optional[str] = None,
    cached_tokens: int = 0,
) -> Dict[str, Any]:
    """
    Record an LLM call with manual token counts (when response object is unavailable).
    
    Parameters
    ----------
    model : str
        Model name
    input_tokens : int
        Number of input tokens
    output_tokens : int
        Number of output tokens
    endpoint : str
        Task label
    role : str, optional
        Call category (default "chat")
    call_type : str, optional
        Type of call (default "chat")
    duration_ms : float, optional
        Duration in milliseconds
    attempt : int, optional
        Attempt number (default 1)
    is_retry : bool, optional
        Is this a retry (default False)
    error : str, optional
        Error message (default None)
    cached_tokens : int, optional
        Cached prompt tokens (default 0)
    
    Returns
    -------
    dict
        The recorded LLMCallRecord as a dict
    """
    global _tracer
    if _tracer is None:
        init_llm_tracer()
    
    try:
        total_tokens = input_tokens + output_tokens
        usage = tt.TokenUsage(input_tokens, output_tokens, total_tokens, cached_tokens)
        
        record = _tracer.record(
            role=role,
            model=model,
            call_type=call_type,
            duration_ms=duration_ms,
            usage=usage,
            attempt=attempt,
            is_retry=is_retry,
            endpoint=endpoint,
            error=error,
        )
        result = record.to_dict()
        
        logger.debug(
            f"Recorded LLM call (manual): model={model} endpoint={endpoint} "
            f"tokens=({input_tokens}/{output_tokens}) "
            f"cost=${result.get('estimated_cost_usd', 'N/A')}"
        )
        return result
    except Exception as e:
        logger.exception(f"Failed to record LLM call (manual) for {model}/{endpoint}: {e}")
        return {}


def get_tracer() -> Optional[tt.TokenTracer]:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        init_llm_tracer()
    return _tracer


def get_usage_stats() -> Dict[str, Any]:
    """
    Get current usage statistics from the tracer.
    
    Returns
    -------
    dict
        Statistics including total_cost, total_tokens, by_model, by_endpoint, etc.
        Returns empty dict if tracer is not initialized or sink doesn't support it.
    """
    tracer = get_tracer()
    if not tracer:
        return {}
    
    # Try to extract stats from sink if it's a ListTraceSink
    if isinstance(tracer.sink, tt.ListTraceSink):
        records = tracer.sink.records
        if not records:
            return {"total_cost_usd": 0.0, "total_tokens": 0, "records": []}
        
        total_cost = sum(r.get("estimated_cost_usd") or 0.0 for r in records)
        total_tokens = sum((r.get("input_tokens") or 0) + (r.get("output_tokens") or 0) 
                          for r in records)
        
        return {
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "num_records": len(records),
            "records": records,
        }
    
    # For JsonlTraceSink, stats should be fetched from the dashboard API
    return {"note": "Use dashboard API at /api/summary for JsonlTraceSink stats"}


# ── HTTP API Integration (Hugging Face, Groq, etc.) ──────────────────────────

def record_http_api_call(
    provider: str,
    model: str,
    endpoint: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cached_tokens: int = 0,
    duration_ms: float = 0.0,
    attempt: int = 1,
    is_retry: bool = False,
    error: Optional[str] = None,
    role: str = "chat",
    call_type: str = "chat",
    response_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record an LLM HTTP API call (e.g., Hugging Face, Groq).
    
    For HTTP-based providers that don't return standard token counts,
    you can estimate tokens from the response text and prompt.
    
    Parameters
    ----------
    provider : str
        Provider name (e.g., "huggingface", "groq", "anthropic")
    model : str
        Model name
    endpoint : str
        Task label/endpoint name
    input_tokens : int, optional
        Number of input tokens (will be estimated if None)
    output_tokens : int, optional
        Number of output tokens (will be estimated if None)
    total_tokens : int, optional
        Total tokens (will be computed if None)
    cached_tokens : int, optional
        Cached tokens (default 0)
    duration_ms : float, optional
        Duration in milliseconds
    attempt : int, optional
        Attempt number (default 1)
    is_retry : bool, optional
        Is this a retry (default False)
    error : str, optional
        Error message (default None)
    role : str, optional
        Call category (default "chat")
    call_type : str, optional
        Type of call (default "chat")
    response_text : str, optional
        Response text for token estimation
    
    Returns
    -------
    dict
        The recorded LLMCallRecord as a dict
    """
    global _tracer
    if _tracer is None:
        init_llm_tracer()
    
    try:
        # Ensure we have token counts
        if input_tokens is None:
            input_tokens = 0
        if output_tokens is None and response_text:
            # Rough estimate: ~4 chars per token
            output_tokens = len(response_text) // 4
        elif output_tokens is None:
            output_tokens = 0
        
        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        
        usage = tt.TokenUsage(input_tokens, output_tokens, total_tokens, cached_tokens)
        
        record = _tracer.record(
            role=role,
            model=model,
            call_type=call_type,
            duration_ms=duration_ms,
            usage=usage,
            attempt=attempt,
            is_retry=is_retry,
            endpoint=endpoint,
            error=error,
            provider=provider,
        )
        result = record.to_dict()
        
        logger.debug(
            f"Recorded HTTP LLM call: provider={provider} model={model} endpoint={endpoint} "
            f"tokens=({input_tokens}/{output_tokens}) "
            f"cost=${result.get('estimated_cost_usd', 'N/A')}"
        )
        return result
    except Exception as e:
        logger.exception(f"Failed to record HTTP LLM call: {e}")
        return {}


class LLMCallTimer:
    """Context manager for timing and tracing LLM calls."""
    
    def __init__(
        self,
        model: str,
        endpoint: str,
        role: str = "chat",
        call_type: str = "chat",
        provider: str = "openai",
    ):
        self.model = model
        self.endpoint = endpoint
        self.role = role
        self.call_type = call_type
        self.provider = provider
        self.start_time = None
        self.duration_ms = 0.0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        # Log any exception
        error = None
        if exc_type is not None:
            error = f"{exc_type.__name__}: {exc_val}"
        
        return False  # Don't suppress exceptions
