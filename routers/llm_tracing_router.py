"""
FastAPI router for LLM token tracing dashboard and API.

Exposes endpoints:
  - GET /api/llm/summary — aggregated usage statistics
  - GET /api/llm/records — recent LLM call records with filtering
  - GET /api/llm/dashboard — standalone HTML dashboard
"""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from typing import Optional, List, Dict, Any
from services.llm_tracer import get_tracer
from services import token_tracing as tt
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm-tracing"])


@router.get("/summary", tags=["analytics"])
async def get_llm_summary(
    model: Optional[str] = Query(None, description="Filter by model name"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    error_only: bool = Query(False, description="Only show errors"),
) -> Dict[str, Any]:
    """
    Get aggregated LLM usage statistics.
    
    Returns total costs, token counts, and breakdowns by model/endpoint.
    """
    tracer = get_tracer()
    if not tracer:
        return {"error": "Tracer not initialized"}
    
    # For JsonlTraceSink, we'd need to parse the JSONL file
    # For testing with ListTraceSink, we can extract from the sink directly
    if isinstance(tracer.sink, tt.ListTraceSink):
        records = tracer.sink.records
        
        # Filter records
        filtered = records
        if model:
            filtered = [r for r in filtered if r.get("model") == model]
        if endpoint:
            filtered = [r for r in filtered if r.get("endpoint") == endpoint]
        if error_only:
            filtered = [r for r in filtered if r.get("error")]
        
        # Compute stats
        total_cost = sum(r.get("estimated_cost_usd") or 0.0 for r in filtered)
        total_tokens = sum((r.get("input_tokens") or 0) + (r.get("output_tokens") or 0) 
                          for r in filtered)
        total_input_tokens = sum(r.get("input_tokens") or 0 for r in filtered)
        total_output_tokens = sum(r.get("output_tokens") or 0 for r in filtered)
        
        # Per-model breakdown
        by_model = {}
        for record in filtered:
            model_name = record.get("model", "unknown")
            if model_name not in by_model:
                by_model[model_name] = {
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                }
            by_model[model_name]["cost"] += record.get("estimated_cost_usd") or 0.0
            by_model[model_name]["input_tokens"] += record.get("input_tokens") or 0
            by_model[model_name]["output_tokens"] += record.get("output_tokens") or 0
            by_model[model_name]["calls"] += 1
        
        # Per-endpoint breakdown
        by_endpoint = {}
        for record in filtered:
            endpoint_name = record.get("endpoint", "unknown")
            if endpoint_name not in by_endpoint:
                by_endpoint[endpoint_name] = {
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                }
            by_endpoint[endpoint_name]["cost"] += record.get("estimated_cost_usd") or 0.0
            by_endpoint[endpoint_name]["input_tokens"] += record.get("input_tokens") or 0
            by_endpoint[endpoint_name]["output_tokens"] += record.get("output_tokens") or 0
            by_endpoint[endpoint_name]["calls"] += 1
        
        return {
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "num_records": len(filtered),
            "by_model": by_model,
            "by_endpoint": by_endpoint,
        }
    
    return {
        "error": "JsonlTraceSink requires direct file parsing (run dashboard server for full API)"
    }


@router.get("/records", tags=["analytics"])
async def get_llm_records(
    model: Optional[str] = Query(None, description="Filter by model"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    error_only: bool = Query(False, description="Only show errors"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
) -> List[Dict[str, Any]]:
    """
    Get recent LLM call records.
    
    Supports filtering by model, endpoint, and error status.
    Newest records first.
    """
    tracer = get_tracer()
    if not tracer:
        return []
    
    if isinstance(tracer.sink, tt.ListTraceSink):
        records = tracer.sink.records
        
        # Filter records
        filtered = records
        if model:
            filtered = [r for r in filtered if r.get("model") == model]
        if endpoint:
            filtered = [r for r in filtered if r.get("endpoint") == endpoint]
        if error_only:
            filtered = [r for r in filtered if r.get("error")]
        
        # Sort by timestamp descending (newest first)
        # Note: This is a simple sort; real timestamp comparison may be needed
        filtered = sorted(filtered, key=lambda r: r.get("timestamp", ""), reverse=True)
        
        # Limit results
        return filtered[:limit]
    
    return []


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """Check if token tracing is active."""
    tracer = get_tracer()
    if not tracer:
        return {"status": "inactive"}
    
    sink_type = type(tracer.sink).__name__
    provider = tracer.provider or "unknown"
    
    return {
        "status": "active",
        "provider": provider,
        "sink": sink_type,
    }


@router.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
async def get_dashboard() -> str:
    """
    Serve a simple HTML dashboard for LLM usage analytics.
    
    Includes charts, tables, and real-time filtering.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM Token Tracing Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
            h1 { margin: 0 0 10px; font-size: 32px; }
            .subtitle { opacity: 0.9; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .card h3 { font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
            .card .value { font-size: 32px; font-weight: bold; color: #333; }
            .card .unit { font-size: 14px; color: #999; margin-left: 5px; }
            .section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .section h2 { font-size: 18px; margin-bottom: 20px; color: #333; }
            table { width: 100%; border-collapse: collapse; }
            th { text-align: left; padding: 12px; background: #f5f5f5; border-bottom: 1px solid #ddd; font-weight: 600; color: #666; font-size: 12px; text-transform: uppercase; }
            td { padding: 12px; border-bottom: 1px solid #eee; }
            tr:hover { background: #fafafa; }
            .loading { text-align: center; color: #999; padding: 40px; }
            .error { background: #fee; color: #c33; padding: 15px; border-radius: 4px; border-left: 4px solid #c33; }
            .button-group { margin-bottom: 20px; display: flex; gap: 10px; }
            button { padding: 8px 16px; border: none; border-radius: 4px; background: #667eea; color: white; cursor: pointer; font-size: 14px; }
            button:hover { background: #5568d3; }
            input, select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
            .label { display: block; font-weight: 600; margin-bottom: 5px; color: #333; }
            .filter-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>💰 LLM Token Tracing</h1>
                <p class="subtitle">Real-time usage analytics and cost tracking</p>
            </header>
            
            <div id="stats" class="grid">
                <div class="card">
                    <h3>Total Cost</h3>
                    <div class="value">$<span id="totalCost">0.00</span></div>
                </div>
                <div class="card">
                    <h3>Total Tokens</h3>
                    <div class="value"><span id="totalTokens">0</span><span class="unit">tokens</span></div>
                </div>
                <div class="card">
                    <h3>Input Tokens</h3>
                    <div class="value"><span id="inputTokens">0</span></div>
                </div>
                <div class="card">
                    <h3>Output Tokens</h3>
                    <div class="value"><span id="outputTokens">0</span></div>
                </div>
                <div class="card">
                    <h3>API Calls</h3>
                    <div class="value"><span id="numRecords">0</span></div>
                </div>
            </div>
            
            <div class="section">
                <h2>📊 Breakdown by Model</h2>
                <div id="byModelContainer" class="loading">Loading...</div>
            </div>
            
            <div class="section">
                <h2>📍 Breakdown by Endpoint</h2>
                <div id="byEndpointContainer" class="loading">Loading...</div>
            </div>
            
            <div class="section">
                <h2>📋 Recent Calls</h2>
                <div class="button-group">
                    <button onclick="loadRecords()">Refresh</button>
                </div>
                <div class="filter-row">
                    <div>
                        <label class="label">Model</label>
                        <input type="text" id="filterModel" placeholder="Filter by model">
                    </div>
                    <div>
                        <label class="label">Endpoint</label>
                        <input type="text" id="filterEndpoint" placeholder="Filter by endpoint">
                    </div>
                    <div>
                        <label class="label">Errors Only</label>
                        <input type="checkbox" id="filterErrors">
                    </div>
                </div>
                <div id="recordsContainer" class="loading">Loading...</div>
            </div>
        </div>
        
        <script>
            const API_BASE = "/api/llm";
            let autoRefresh = true;
            
            async function loadSummary() {
                try {
                    const response = await fetch(`${API_BASE}/summary`);
                    const data = await response.json();
                    
                    document.getElementById("totalCost").textContent = data.total_cost_usd.toFixed(6);
                    document.getElementById("totalTokens").textContent = data.total_tokens.toLocaleString();
                    document.getElementById("inputTokens").textContent = (data.total_input_tokens || 0).toLocaleString();
                    document.getElementById("outputTokens").textContent = (data.total_output_tokens || 0).toLocaleString();
                    document.getElementById("numRecords").textContent = data.num_records;
                    
                    // By model
                    const byModelHtml = Object.entries(data.by_model || {})
                        .map(([model, stats]) => `
                            <tr>
                                <td>${model}</td>
                                <td>${stats.calls}</td>
                                <td>${(stats.input_tokens || 0).toLocaleString()}</td>
                                <td>${(stats.output_tokens || 0).toLocaleString()}</td>
                                <td>$${(stats.cost || 0).toFixed(6)}</td>
                            </tr>
                        `)
                        .join("");
                    document.getElementById("byModelContainer").innerHTML = byModelHtml ? 
                        `<table><thead><tr><th>Model</th><th>Calls</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead><tbody>${byModelHtml}</tbody></table>` :
                        '<p style="color: #999;">No data yet</p>';
                    
                    // By endpoint
                    const byEndpointHtml = Object.entries(data.by_endpoint || {})
                        .map(([endpoint, stats]) => `
                            <tr>
                                <td>${endpoint}</td>
                                <td>${stats.calls}</td>
                                <td>${(stats.input_tokens || 0).toLocaleString()}</td>
                                <td>${(stats.output_tokens || 0).toLocaleString()}</td>
                                <td>$${(stats.cost || 0).toFixed(6)}</td>
                            </tr>
                        `)
                        .join("");
                    document.getElementById("byEndpointContainer").innerHTML = byEndpointHtml ?
                        `<table><thead><tr><th>Endpoint</th><th>Calls</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead><tbody>${byEndpointHtml}</tbody></table>` :
                        '<p style="color: #999;">No data yet</p>';
                } catch (error) {
                    console.error("Failed to load summary:", error);
                }
            }
            
            async function loadRecords() {
                try {
                    const model = document.getElementById("filterModel").value;
                    const endpoint = document.getElementById("filterEndpoint").value;
                    const errorOnly = document.getElementById("filterErrors").checked;
                    
                    const params = new URLSearchParams();
                    if (model) params.append("model", model);
                    if (endpoint) params.append("endpoint", endpoint);
                    if (errorOnly) params.append("error_only", "true");
                    params.append("limit", "50");
                    
                    const response = await fetch(`${API_BASE}/records?${params}`);
                    const records = await response.json();
                    
                    const html = records.map(r => `
                        <tr style="${r.error ? 'background: #fff3cd;' : ''}">
                            <td style="font-size: 12px;">${r.timestamp || ''}</td>
                            <td><strong>${r.model}</strong></td>
                            <td>${r.endpoint}</td>
                            <td>${(r.input_tokens || 0).toLocaleString()}</td>
                            <td>${(r.output_tokens || 0).toLocaleString()}</td>
                            <td>$${(r.estimated_cost_usd || 0).toFixed(6)}</td>
                            <td>${r.duration_ms ? (r.duration_ms.toFixed(1) + 'ms') : '-'}</td>
                            <td>${r.error ? '❌ ' + r.error.substring(0, 30) : '✓'}</td>
                        </tr>
                    `).join("");
                    
                    document.getElementById("recordsContainer").innerHTML = html ?
                        `<table><thead><tr><th>Timestamp</th><th>Model</th><th>Endpoint</th><th>Input</th><th>Output</th><th>Cost</th><th>Duration</th><th>Status</th></tr></thead><tbody>${html}</tbody></table>` :
                        '<p style="color: #999;">No records found</p>';
                } catch (error) {
                    console.error("Failed to load records:", error);
                }
            }
            
            // Initial load
            loadSummary();
            loadRecords();
            
            // Auto-refresh every 5 seconds
            setInterval(() => {
                if (autoRefresh) {
                    loadSummary();
                    loadRecords();
                }
            }, 5000);
        </script>
    </body>
    </html>
    """
