# 🔍 Discovery Insight Engine

> **Proof of Concept & Working Prototype**  
> Built by **Ranaji Deb** for the **Senior Product Manager — Network Discovery** role at **IP Fabric**.

---

## Why I Built This

When applying for the **Senior Product Manager – Network Discovery** role, I didn't want to just talk about product frameworks or review requirements on slides. 

Network discovery is where IP Fabric earns customer trust: collecting, normalising, and modelling complex network states across vendors. As a PM in this area, the core challenge isn't just pulling raw data—it's **turning technical discovery signals into crisp product decisions and customer value**.

So I decided to get hands-on:
1. Spun up an **IP Fabric appliance VM** on GCP and ran discovery snapshots across hybrid topologies.
2. Hooked into IP Fabric’s official **Python SDK (`python-ipfabric` v8.x)** to ingest live discovery data.
3. Built an **AI-driven decision support prototype** that translates low-level discovery tables into high-level product insights, drift detection, and interactive network reasoning.

---

## What the Prototype Explores

The prototype is organized around three practical product problems a Network Discovery PM faces every day:

### 1. 🏥 Discovery Health Score (`Tab 1`)
* **The Customer Problem:** "Did my discovery actually work, or do I have blind spots I don't know about?"
* **What I built:** A live health scorecard tracking device coverage, vendor distribution, platform diversity, and discovery task failures.
* **The AI Layer:** Generates an executive-level health summary evaluating discovery completeness, highlighting risk patterns (e.g., single-vendor exposure or unreached subnets), and framing concrete next steps.

### 2. 📊 Snapshot Drift Detector (`Tab 2`)
* **The Customer Problem:** "What changed between snapshot A and snapshot B, and what broke our intent?"
* **What I built:** A deterministic diffing engine between any two discovery snapshots (e.g., comparing a baseline pre-acquisition snapshot against a post-merger cloud rollout).
* **The AI Layer:** Evaluates new vs. removed vs. modified devices, assesses whether the discovery pipeline captured the change accurately, and provides a product verdict on discovery quality.

### 3. 💬 Ask Your Network (`Tab 3`)
* **The Customer Problem:** Network engineers and infrastructure leaders shouldn't have to write complex table queries to get answers about risk, coverage, or drift.
* **What I built:** An interactive, multi-turn chat interface backed by live snapshot data.
* **The Product Framing:** Unlike generic chat interfaces, the system prompt frames answers around **business risk, vendor concentration, intent compliance, and roadmap trade-offs**—and supports conversational follow-ups.

---

## 📋 Product Requirements Document (PRD Summary)

> 📖 **[Read the Full Enterprise PRD Document (PRD.md)](./PRD.md)**

### 1. The Conceptualization Journey
* **Initial Concept:** An external tool ranking vendor priorities using scraped public reviews (G2, Reddit).
* **Domain Pivot:** Realized customer trust is rooted in their *own* network data. Pivoted to ingesting live discovery snapshots via IP Fabric's official Python SDK (`python-ipfabric` v8.x).
* **MCP & AIOps Positioning:** Rather than re-building IP Fabric's built-in MCP server, positioned this as the **decision-support & product-framing layer** that transforms raw telemetry into customer ROI.
* **Working Software:** Delivered a dual-mode Streamlit prototype running against a live GCP IP Fabric VM instance.

### 2. Product Requirements Matrix

| Area | Feature ID | Core Requirement | Impact on Customer |
|---|---|---|---|
| **Discovery Health** | `FR-DH-01` | Ingest live inventory & task states via SDK | Instant visibility into discovery blind spots & unreached subnets |
| **Health Synthesis** | `FR-DH-03` | AI executive summary & risk ranking | Converts technical failure codes into prioritized engineering actions |
| **Drift Engine** | `FR-SD-02` | Deterministic cross-snapshot device & attribute diffing | Slashes change-window validation time from 1 hour to < 2 minutes |
| **AIOps Chat** | `FR-NL-02` | Multi-turn conversational network reasoning | Enables non-CLI stakeholders (CISOs, VPs) to query infrastructure intent |
| **Data Resiliency** | `FR-DL-01` | Dual-mode architecture (Live SDK + Offline Demo) | Evaluators & customers can explore the product without infrastructure overhead |

### 3. Integration & Evolution Blueprint

| Phase | Milestone | Focus Area |
|---|---|---|
| **Phase 1 (Done)** | **Working Proof of Concept** | Streamlit dashboard with live SDK ingestion, drift detection, and multi-turn AI reasoning. |
| **Phase 2 (Q4)** | **IP Fabric Native Extension** | Package as a containerized app inside IP Fabric’s **Extensions runtime (`/extensions-apps/`)**, correlating with Intent Verification Rules. |
| **Phase 3 (Q1-Q2)** | **Agentic Self-Healing Discovery** | Proactive credential suggestion for failed discovery tasks, automated webhook-triggered drift digests, and bidirectional NetBox/ServiceNow sync. |

---

## How This Fits Into IP Fabric’s Product Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Discovery Insight Engine                    │
│   🏥 Health Score   │   📊 Snapshot Drift   │   💬 Chat     │
└───────────────┬─────────────────────┬───────────────────────┘
                │                     │
    ┌───────────┴──────────┐   ┌──────┴──────────────┐
    │  Product Framing &   │   │  OpenRouter LLM     │
    │  Prompt Orchestration│   │  (Gemini / Claude)  │
    └───────────┬──────────┘   └─────────────────────┘
                │
    ┌───────────┴─────────────────────────────────────┐
    │            IP Fabric Data Layer                 │
    │  • Live Mode: python-ipfabric SDK (v8.x)        │
    │  • Demo Mode: Bundled snapshot fixtures         │
    │  • Drop-in IP Fabric Extension (/extensions-apps)│
    └─────────────────────────────────────────────────┘
```

### Complementing (not duplicating) IP Fabric's MCP Server
IP Fabric recently released a built-in MCP server (`/mcp` endpoint) that provides AI assistants with access to raw discovery tools (path lookups, BGP state, device tables).

This POC sits **one abstraction layer higher**:
- **MCP Server:** *"Here is the raw BGP table and list of 67 Cisco devices."*
- **Discovery Insight Engine:** *"100% of your access layer is concentrated on a single legacy Cisco IOS platform. Here is the operational risk, the blind spots in your branch sites, and what we should prioritise in the next discovery release."*

---

## Running It Locally

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- (Optional) IP Fabric instance + API token (for Live mode)
- (Optional) OpenRouter API key (for LLM reasoning)

### 1. Clone & Setup
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/discovery-insight-engine.git
cd discovery-insight-engine

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```env
# IP Fabric Live Connection (leave as demo if testing without a VM)
IPF_URL=https://127.0.0.1:8443
IPF_TOKEN=your-token-here
IPF_VERIFY=false

# AI Reasoning Layer
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=google/gemini-2.5-flash

# Data Mode: "live" (connects to IPF) or "demo" (uses bundled test snapshots)
DATA_MODE=live
```

### 3. Launch Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Key Product Takeaways & What I'd Build Next

If I were leading the Network Discovery product area at IP Fabric tomorrow, here are three high-conviction roadmap themes this POC reinforced for me:

1. **Self-Healing Discovery & Credential Life-cycle:** Most discovery failures aren't protocol bugs—they are stale credentials, jumphost timeouts, or unmapped subnets. Giving users proactive "Discovery Health" prompts can increase discovery completion rates significantly.
2. **Intent Drift as a First-Class Citizen:** Snapshot comparison shouldn't just be visual diagram diffs. Surfacing *intent deviations* with automated PM/executive summaries makes IP Fabric indispensable to compliance and NetOps teams.
3. **Natural-Language Discovery Querying (AIOps):** Combining IP Fabric’s structured digital twin with conversational AI transforms how cross-functional teams (SecOps, Cloud Architects, Leadership) interact with infrastructure data without needing deep CLI knowledge.

---

**Ranaji Deb**  
*Senior Product Manager & UX Leader*  
*Candidate for Senior Product Manager – Network Discovery, IP Fabric*
