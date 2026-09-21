# 🔍 Discovery Insight Engine

> **Proof of Concept & Working Prototype**  
> Built by **Ranaji Deb** for the **Senior Product Manager — Network Discovery** role at **IP Fabric**.

---

## Why I Built This: Upstream Collection & Parser Diagnostics

When applying for the **Senior Product Manager – Network Discovery** role, I wanted to anchor my work in the core upstream mandate of IP Fabric:

Network discovery is where IP Fabric earns customer trust: **worker queue scaling, seed traversal, SSH/API command execution, CLI regex parsing, and multi-vendor normalization**. Downstream features (intent verification, drift compliance, conversational network queries) all depend entirely on the fidelity of this upstream collection foundation.

So I built a working decision-support prototype that tackles the daily challenges of a Network Discovery PM:
1. **Discovery Health & Traversal Scorecard (`Tab 1`):** Ingests live device inventories and tracks normalization completeness across Layer 2, Layer 3, and Security tables, alongside seed reachability and worker queue saturation.
2. **Discovery Triage & Parsing Diagnostics (`Tab 2`):** Replaces simple task counts with CLI-level root-cause diagnostics (SSH timeouts vs. regex pattern breaks vs. jumphost drops).
3. **Vendor Support & AI Ingestion Engine (`Tab 3`):** Matches unmanaged MAC OUIs and unparsed `sysDescr` strings against IP Fabric's supported matrix, using AI to digest vendor release notes and generate production CLI commands and named-group regex patterns.
4. **PM Copilot & Spec Synthesizer (`Tab 4`):** Practical AI for internal product management velocity—synthesizing raw customer requests and vendor API docs into structured Jira Epics with explicit engineering vs. business trade-offs.
5. **Discovery Engine Assistant (`Tab 5`):** Conversational assistant grounded in discovery telemetry, CLI logs, and regex parser architectures.

---

## What the Prototype Explores

### 1. 🏥 Discovery Health & Traversal Scorecard (`Tab 1`)
* **The Problem:** "Did our discovery run with 100% normalization fidelity, or do we have partial table reads and unreached neighbor hops?"
* **What I built:** Tracks Layer 2 (STP/VLAN), Layer 3 (Routing/VRF), and Security Policy normalization rates, seed IP hop distribution, credential pool hit rates, and async worker queue saturation.
* **The AI Layer:** Evaluates normalization completion, identifies bottlenecks, and suggests immediate operational actions (buffer timeouts, credential assignments).

### 2. 🔍 Discovery Triage & Parsing Diagnostics (`Tab 2`)
* **The Problem:** "Which specific CLI commands failed during discovery, why did they fail, and what regex/timeout patch is required?"
* **What I built:** A diagnostic inspector displaying failed CLI commands (`show ip route vrf *`, `show cdp neighbors detail`), raw CLI buffer snippets, and root-cause classification.
* **The AI Layer:** Synthesizes failure patterns across sites (e.g., Jumphost security group drops in Site A vs. Cisco IOS 15.2 regex breaks in Site B) and proposes exact regex and command pagination fixes.

### 3. 🧩 Vendor Support & AI Ingestion Engine (`Tab 3`)
* **The Problem:** "How do we rapidly support new firmware releases like Arista EOS 4.31, PAN-OS 11.1, or FortiOS 7.4 without weeks of reverse-engineering?"
* **What I built:** A Vendor & OS Gap Analyzer matching unmanaged OUIs and unparsed `sysDescr` strings against support tiers, paired with an AI Ingestion Engine.
* **The AI Layer:** Digests vendor release notes and command references to generate:
  - Required CLI Discovery Command Sequences
  - Production Regex / TextFSM with named capture groups `(?P<group_name>...)`
  - Canonical IP Fabric Digital Twin schema mappings
  - Parser Unit Test mock fixtures

### 4. 🛠️ PM Copilot & Discovery Spec Synthesizer (`Tab 4`)
* **The Problem:** "How can a Discovery PM turn messy customer feature requests and vendor API docs into crisp technical specifications in minutes?"
* **What I built:** An AI PM Copilot that synthesizes Jira Epics, technical discovery scopes, and explicit **Product Trade-off Memos (What We Build vs. What We Deliberately Defer)**.

---

## 📋 Product Requirements Document (PRD Summary)

> 📖 **[Read the Full Enterprise PRD Document (PRD.md)](./PRD.md)**

### Key Highlights from `PRD.md`:
- **Product Trade-off Memo & Anti-Roadmap:** Explicitly explains why we deferred real-time streaming telemetry and shallow ping sweeps in favor of deterministic snapshot assurance and deep authenticated state extraction.
- **50,000-Node Scalability vs. Edge Legacy Hardware:** Framework for prioritizing core queue scalability over bespoke one-off legacy hardware parsers.
- **Vendor Support Scoring Model:** Multi-factor matrix (40% TAM, 30% Graph Impact, 20% API/CLI Stability, 10% Customer Concentration) for roadmap decisions.

---

## Running It Locally

### Prerequisites
- Python 3.10+
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
OPENROUTER_MODEL=antigravity/gemini-3.7-flash-tiered

# Data Mode: "live" (connects to IPF) or "demo" (uses bundled test snapshots)
DATA_MODE=demo
```

### 3. Launch Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.


If I were leading the Network Discovery product area at IP Fabric tomorrow, here are three high-conviction roadmap themes this POC reinforced for me:

1. **Self-Healing Discovery & Credential Life-cycle:** Most discovery failures aren't protocol bugs—they are stale credentials, jumphost timeouts, or unmapped subnets. Giving users proactive "Discovery Health" prompts can increase discovery completion rates significantly.
2. **Intent Drift as a First-Class Citizen:** Snapshot comparison shouldn't just be visual diagram diffs. Surfacing *intent deviations* with automated PM/executive summaries makes IP Fabric indispensable to compliance and NetOps teams.
3. **Natural-Language Discovery Querying (AIOps):** Combining IP Fabric’s structured digital twin with conversational AI transforms how cross-functional teams (SecOps, Cloud Architects, Leadership) interact with infrastructure data without needing deep CLI knowledge.

---

**Ranaji Deb**  
*Senior Product Manager & UX Leader*  
*Candidate for Senior Product Manager – Network Discovery, IP Fabric*
