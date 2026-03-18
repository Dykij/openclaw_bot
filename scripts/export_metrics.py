import asyncio
import logging
from pathlib import Path
import aiohttp

logger = logging.getLogger("MetricsExporter")
logger.setLevel(logging.INFO)

PROMETHEUS_URL = "http://127.0.0.1:9090"

async def query_prometheus(session: aiohttp.ClientSession, query: str) -> str:
    """Execute a PromQL query against the local Prometheus TSDB."""
    try:
        async with session.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("data", {}).get("result", [])
                if results and len(results) > 0:
                    try:
                        value_str = results[0].get("value", [0, "0"])[1]
                        return f"{float(value_str):.2f}"
                    except ValueError:
                        return results[0].get("value", [0, "0"])[1]
            return "0.00"
    except Exception as e:
        logger.error(f"PromQL query failed: {query} -> {e}")
        return "ERROR"

async def export_2hour_report():
    """
    Extracts structural test metrics from the 2-Hour Window.
    Outputs a consolidated markdown report.
    """
    logger.info("Connecting to Prometheus TSDB for 2-Hour Aggregation...")
    
    async with aiohttp.ClientSession() as session:
        # Aggregation Queries spanning the 2h window
        total_trades = await query_prometheus(session, 'sum(increase(openclaw_trades_executed_total[2h]))')
        avg_slippage = await query_prometheus(session, 'avg_over_time(openclaw_slippage_penalty_active[2h])')
        hmm_shifts = await query_prometheus(session, 'sum(changes(openclaw_hmm_current_regime_state[2h]))')
        min_vram = await query_prometheus(session, 'min_over_time(openclaw_vram_free_mb[2h])')
        
        report_md = f"""# Phase 19: 2-Hour Chaos & Paper Trading Report

## Telemetry Aggregation (Prometheus Extract)
- **Total Simulated Trades (2h):** {total_trades}
- **Average Slippage Penalty Extracted:** {avg_slippage}
- **HMM Regime Transitions Detected:** {hmm_shifts}
- **Minimum VRAM Floor Reached (Spike Peak):** {min_vram} MB

*Generated automatically via Prometheus PromQL extraction post-chaos-test.*
"""
        out_path = Path("reports/phase_19_telemetry_report.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_md)
        logger.info(f"✅ Phase 19 Analytics Report exported successfully to {out_path.absolute()}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(export_2hour_report())
