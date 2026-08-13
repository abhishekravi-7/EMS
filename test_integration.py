#!/usr/bin/env python3
"""
Quick test to verify token tracing integration is working.

Run with: python test_integration.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test all key imports."""
    print("Testing imports...\n")
    
    try:
        # Test token_tracing module
        from services import token_tracing as tt
        print(f"[OK] token_tracing module ({tt.__version__})")
        
        # Test key components
        assert hasattr(tt, 'TokenTracer')
        assert hasattr(tt, 'JsonlTraceSink')
        assert hasattr(tt, 'StaticPricingProvider')
        print("[OK] token_tracing components (TokenTracer, JsonlTraceSink, StaticPricingProvider)")
        
        # Test llm_tracer wrapper
        from services.llm_tracer import (
            init_llm_tracer,
            record_llm_call,
            record_llm_call_manual,
            record_http_api_call,
            LLMCallTimer,
            get_tracer,
            get_usage_stats,
        )
        print("[OK] services.llm_tracer wrapper (all functions)")
        
        # Test FastAPI router
        from routers.llm_tracing_router import router as llm_router
        print("[OK] routers.llm_tracing_router (FastAPI integration)")
        
        # Test examples
        from services.llm_tracing_examples import (
            example_manual_token_recording,
            example_huggingface_integration,
            example_custom_pricing,
        )
        print("[OK] services.llm_tracing_examples (integration examples)")
        
        print("\n" + "="*50)
        print("SUCCESS: All imports working!")
        print("="*50)
        return True
        
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        return False
    except AssertionError as e:
        print(f"\n[ERROR] Assertion error: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_functionality():
    """Test basic token tracing functionality."""
    print("\nTesting basic functionality...\n")
    
    try:
        from services.llm_tracer import record_llm_call_manual, get_tracer
        
        # Create a test record
        record = record_llm_call_manual(
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=200,
            endpoint="test_endpoint",
            role="test",
            duration_ms=500,
        )
        
        if record:
            print(f"[OK] Created test record:")
            print(f"  - Model: {record.get('model')}")
            print(f"  - Tokens: {record.get('input_tokens')} input, {record.get('output_tokens')} output")
            print(f"  - Cost: ${record.get('estimated_cost_usd'):.6f}")
            print(f"  - Timestamp: {record.get('timestamp')}")
        else:
            print("[WARN] Record was empty (tracer may not be initialized)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("LLM Token Tracing Integration Test")
    print("="*50 + "\n")
    
    # Test imports
    if not test_imports():
        return 1
    
    # Test basic functionality
    if not test_basic_functionality():
        return 1
    
    print("\n" + "="*50)
    print("All tests passed!")
    print("="*50)
    print("\nNext steps:")
    print("  1. Review LLM_TOKEN_TRACING.md for usage")
    print("  2. Check services/llm_tracing_examples.py for code examples")
    print("  3. Start FastAPI server and visit http://localhost:8000/api/llm/dashboard")
    print("  4. Add record_llm_call() to your LLM call sites")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
