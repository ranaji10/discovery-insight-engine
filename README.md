# 🔍 Discovery Insight Engine

**AI-powered product decision support for IP Fabric Network Discovery**

> Built as a proof of concept for the **Senior Product Manager — Network Discovery** role at IP Fabric.

---

## What This Demonstrates

This POC shows how a PM for Network Discovery would use IP Fabric's own tools — the **Python SDK** and **MCP-era thinking** — to turn raw network data into **product-framed insights** that drive better decisions.

| Capability | What it shows | JD alignment |
|---|---|---|
| **Discovery Health Score** | Visual dashboard of discovery coverage, vendor diversity, and failure rates | "Drive measurable customer outcomes by improving reliability, coverage, speed" |
| **Snapshot Drift Detector** | Compare two snapshots to detect device changes, config drift, and intent violations | "Improve data quality, scalability, and related platform foundations" |
| **NL Insight Generator** | Ask natural-language questions → get product-framed answers with priorities | "Use AI practically to improve product discovery, vendor support analysis" |

## Architecture

```
┌──────────────────────────────────────────┐
│            Streamlit Dashboard            │
│  Health Score │ Drift Diff │ NL Insights  │
└──────────┬───────────┬──────────┬────────┘
           │           │          │
    ┌──────┴───────────┴──────────┴──────┐
    │      Insight Engine (Python)        │
    │  • Product-framed LLM prompts      │
    │  • Snapshot comparison logic        │
    │  • Prioritisation rules            │
    └──────────┬──────────────────────────┘
               │
    ┌──────────┴──────────────────────────┐
    │         Data Layer                   │
    │  Mode A: IP Fabric SDK (live)       │
    │  Mode B: Demo JSON fixtures         │
    └─────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- (Optional) Access to an IP Fabric instance with an API token
- (Optional) [OpenRouter](https://openrouter.ai) API key for AI insights

### Setup

```bash
cd discovery-insight-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run
streamlit run app.py
```

### Data Modes

- **Demo mode** (`DATA_MODE=demo`): Uses bundled sample data. No IP Fabric instance needed.
- **Live mode** (`DATA_MODE=live`): Connects to your IP Fabric instance via the Python SDK.

## Key Product Decisions Demonstrated

1. **Dual-mode architecture**: The dashboard works without a live instance (demo mode), showing respect for evaluator time — they don't need to spin up infrastructure to see the POC.

2. **Product framing over raw data**: Every insight is framed in terms of customer impact, risk, and PM recommendations. Raw tables are available but secondary.

3. **MCP-aligned design**: The NL query layer mirrors IP Fabric's own MCP server philosophy — natural language → structured data → actionable insight.

4. **SDK-first integration**: Uses `python-ipfabric` SDK directly rather than raw API calls, demonstrating familiarity with IP Fabric's developer ecosystem.

## How This Relates to IP Fabric's MCP Server

IP Fabric ships a built-in MCP server (`/mcp` endpoint) that exposes tools like `ipf_network_health_assess`, path lookups, and `api_invoke`. This POC doesn't duplicate that server — instead, it demonstrates the **product layer** that sits above it:

- The MCP server provides *data access* ("here are your BGP neighbors")
- This POC provides *product framing* ("your BGP coverage has gaps in 3 branch sites — here's why that matters and what to prioritise")

This is exactly the kind of thinking a PM for Network Discovery would bring: **not just shipping features, but shaping how customers extract value from them.**

## Technologies

- [IP Fabric Python SDK](https://gitlab.com/ip-fabric/integrations/python-ipfabric) (`ipfabric` v8.x)
- [Streamlit](https://streamlit.io) for rapid dashboard prototyping
- [Plotly](https://plotly.com) for interactive charts
- [OpenRouter](https://openrouter.ai) (OpenAI-compatible) for LLM insights
- [Pandas](https://pandas.pydata.org) for data manipulation

## Author

**Ranaji Deb** — Product + UX leader applying for IP Fabric's Senior Product Manager, Network Discovery role.

This POC demonstrates the intersection of:
- **Domain learning speed** — understanding IP Fabric's data model, SDK, and MCP strategy
- **Product judgement** — framing raw network data as customer value
- **AI fluency** — practical LLM integration for product work
- **Hands-on execution** — shipping a working prototype, not just slides
