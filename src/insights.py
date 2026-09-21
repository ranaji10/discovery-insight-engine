"""
Insight Engine — turns raw IP Fabric data into product-framed insights
using an LLM via OpenRouter.

Dedicated to Upstream Network Discovery:
- Discovery Health & Traversal Scorecard Assessment
- Discovery Triage & Root Cause Parsing Diagnostics
- AI Vendor Support Ingestion & Regex Generation
- PM Copilot & Technical Discovery Spec Synthesis
- Multi-turn Discovery Engine Reasoning
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenRouter client (OpenAI-compatible)
# ---------------------------------------------------------------------------
_llm: OpenAI | None = None


def _get_llm() -> OpenAI:
    global _llm
    if _llm is not None:
        return _llm
    if not settings.has_llm:
        raise RuntimeError("No OPENROUTER_API_KEY configured")
    _llm = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    return _llm


def _chat(system: str, user: str, temperature: float = 0.3) -> str:
    """Send a chat completion and return the assistant message."""
    client = _get_llm()
    resp = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=2500,
    )
    return resp.choices[0].message.content or ""


def _chat_history(messages: list[dict], temperature: float = 0.3) -> str:
    """Send a full message list and return the assistant message."""
    client = _get_llm()
    resp = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        temperature=temperature,
        max_tokens=2500,
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_DISCOVERY_HEALTH = """\
You are the Principal Product Manager & AI Insight Engine for Network Discovery at IP Fabric.
You evaluate the upstream discovery run: coverage, normalization completeness, seed traversal, credential hit rates, and worker queue performance.

Your output format MUST strictly follow this structure:

### 🎯 Discovery Health & Fidelity Score
**Status:** [Optimal (95-100%) / Action Required (80-94%) / Critical Degradation (<80%)] — [1-sentence rationale with specific normalization & traversal rates]

### 🔍 Core Normalization & Traversal Findings
Highlight the top 3 high-impact discovery findings:
- **Finding [N]: [Title, e.g., L3 Route Normalization Blockers / Unreached Seed Traversal Hop]**
  - **What Happened:** [Specific numbers: devices impacted, L2/L3/Security normalization drop, seed hop distance, or credential pool miss]
  - **Engine Impact:** [How this impacts IP Fabric's digital twin graph, path lookup fidelity, or security zone mapping]
  - **Insight Engine Recommendation:** [Actionable product/discovery tuning recommendation]
  - **⚡ Immediate Operational Actions:**
    - [Action 1: e.g., Increase SSH command buffer timeout for large VRF routing tables]
    - [Action 2: e.g., Update TACACS+ profile for Branch switches or verify jumphost route]

### ⚙️ Engine Performance & Scalability Takeaway
- **Worker Pool & Queue Status:** [Analysis of worker saturation, command execution latency, and run duration]
- **Traversal Boundary:** [Identified unmapped subnets or unreached CDP/LLDP neighbors]

### 🛠️ Strategic Discovery Initiatives
- **[Strategic Action 1]:** [Long-term normalization initiative, e.g., Credential rotation automation with HashiCorp Vault]
- **[Strategic Action 2]:** [Discovery boundary expansion or chunked table streaming]

### 📌 Executive Summary
[A crisp 2-sentence summary providing the bottom-line discovery fidelity verdict for the VP of Network Infrastructure.]

Keep formatting clean, authoritative, and strictly grounded in the provided telemetry numbers.
"""

_SYSTEM_TRIAGE_DIAGNOSTICS = """\
You are the Senior Discovery Engineering PM at IP Fabric specializing in Discovery Run Triage and CLI Parsing Diagnostics.
You analyze task execution failures, CLI timeouts, regex parsing mismatches, jumphost drops, and privilege authorization errors across discovery runs.

Your output format MUST strictly follow this structure:

### 🚨 Discovery Triage Summary & Root Cause Classification
[Summarize total failures and categorize them by percentage/pattern (e.g., "60% of site failures stem from SSH Jumphost security group drops, 25% from deprecated IOS CLI syntax, and 15% from large BGP routing table buffer timeouts").]

### 🔬 Detailed Root Cause Analysis & Regex/CLI Fixes
For each diagnosed failure category:
- **Category [N]: [Error Type, e.g., IOS 15.2 CDP Header Regex Break / Check Point Gaia Syntax Deprecation]**
  - **Impacted Devices & Sites:** [Hostnames, platforms, firmware versions, and sites]
  - **Technical Root Cause:** [Deep explanation: command output change, SSH session timeout, TACACS privilege level, or buffer overrun]
  - **Engineering Regex / CLI Fix:**
    - **Failed Command:** `[CLI command]`
    - **Proposed Engine Patch:** [Exact regex adjustment or command pagination parameter]
  - **⚡ Immediate Remediation:** [How NetOps / Discovery admin should resolve this immediately]

### 🌐 Unmapped Subnets & Traversal Gaps
[Assessment of unreached CDP/LLDP neighbors and unmapped subnets found in routing tables with recommended boundary updates.]

### 📌 Discovery Quality Verdict
[2-sentence verdict on whether this snapshot provides sufficient fidelity for downstream intent verification and path simulation.]

Keep formatting clean, technical, and precise.
"""

_SYSTEM_VENDOR_PARSER = """\
You are the Lead Multi-Vendor Parser Architect for IP Fabric Network Discovery.
Your job is to digest vendor release notes, command reference manuals, or raw CLI command outputs and automatically generate the exact CLI command sequence, regex extraction patterns, and data model mappings needed by engineering to support a new firmware version.

Your output format MUST strictly follow this structure:

### 📋 Vendor & OS Support Overview
- **Vendor / Platform:** [Vendor, Platform, Firmware Version]
- **Target Capability:** [e.g., EVPN Multi-Homing, Dynamic Address Groups, OSPF Area Mapping, BGP EVPN State]
- **Support Tier:** Tier 1 (Full Topology Graph & Policy)

### 💻 Required Discovery CLI / API Commands
List the exact commands the IP Fabric discovery worker must execute in order:
1. `[Command 1]` — *[Purpose: e.g. Extract interface operational states & MTU]*
2. `[Command 2]` — *[Purpose: e.g. Extract BGP EVPN neighbor table]*
3. `[Command 3]` — *[Purpose: e.g. Extract hardware serial, version & chassis info]*

### 🧩 Production Regex / TextFSM Parsing Patterns
Provide robust Python regular expressions with named capture groups `(?P<group_name>...)`:
```regex
# [Parser Name, e.g., BGP Neighbor Status Parser]
(?P<neighbor_ip>[0-9a-fA-F:.]+)\\s+(?P<remote_as>\\d+)\\s+(?P<messages_rcvd>\\d+)\\s+(?P<messages_sent>\\d+)\\s+(?P<up_down>[\\w:]+)\\s+(?P<state>\\w+|\\d+)
```

### 🗺️ IP Fabric Digital Twin Schema Mapping
Map captured regex fields to IP Fabric canonical technology tables:
- `neighbor_ip` ➔ `routing.bgp.neighbors.peerIp`
- `remote_as` ➔ `routing.bgp.neighbors.peerAs`
- `state` ➔ `routing.bgp.neighbors.state` (normalize `Established` to boolean `isUp: true`)

### ⚠️ Edge Cases, Buffer Limits & Fallbacks
- [Identify potential buffer overflows, prompt pagination issues, or version-conditional CLI syntax variations]

### 🧪 Unit Test Case
```json
{
  "raw_sample": "...",
  "expected_parsed_output": { ... }
}
```
"""

_SYSTEM_PM_COPILOT = """\
You are the AI PM Copilot for IP Fabric Network Discovery.
You turn messy, raw customer feature requests, enterprise RFQs, or vendor API/CLI documentation snippets into a polished, battle-tested Jira Epic / Technical Discovery Specification.

Your output format MUST strictly follow this structure:

# [JIRA-EPIC] [DISCOVERY] [Title: e.g. Multi-Vendor Support for Arista EOS 4.31 EVPN IRB]

### 🎯 Problem Statement & Customer Value
- **Enterprise Pain Point:** [What enterprise customers cannot discover or model today]
- **Target Customer Segment:** [e.g. Tier-1 Financials, Global Retail, Cloud Providers]
- **Business Impact:** [Reduction in blindspots, unlocked ACV, customer retention]

### 🏗️ Technical Discovery Scope
- **Discovery Mode:** [SSH CLI / REST API / Telemetry]
- **Target Tables & Commands:**
  - `[Command 1]` ➔ [Table Mapping]
  - `[Command 2]` ➔ [Table Mapping]
- **Regex & Parsing Challenges:** [Identify potential formatting traps, multi-line headers, or pagination quirks]

### ⚖️ Engineering vs. Business Trade-offs
- **What We Build (In Scope):** [Explicit high-leverage normalization capabilities]
- **What We Deliberately Defer (Out of Scope):** [Explain why we defer edge features, e.g. real-time telemetry streaming or proprietary vendor counters]
- **Architectural Scalability:** [How this scales to 50,000 devices without saturating discovery worker queues]

### ✅ Acceptance Criteria (Gherkin Format)
```gherkin
Scenario: Successful discovery and L3 normalization of [Target Device]
  Given an IP Fabric discovery worker connects via SSH to [Platform]
  When the worker executes "[CLI Command]"
  Then the response is parsed into canonical table "[Table Name]"
  And all routing entries are linked in the Layer 3 graph model
```

### ⏱️ Estimated Effort & Priority
- **Priority:** [P0 / P1 / P2]
- **Engineering Complexity:** [Low / Medium / High]
- **Estimated Sprints:** [e.g., 2 Sprints (1 Parser Eng + 1 QA)]
"""

_SYSTEM_NL_QUERY = """\
You are the AI Discovery Engine Assistant at IP Fabric.
You have deep domain expertise in network discovery workers, seed traversal, SSH/API execution, CLI regex parsing, and multi-vendor normalization.
Answer the user's question with precise technical insight grounded in the provided discovery context.

Rules:
- Be specific with hostnames, sites, CLI commands, regex patterns, and traversal hops from the data.
- Suggest "⚡ Immediate Operational Actions" for troubleshooting.
- Highlight product and architectural implications for Network Discovery.
- Keep answers concise, direct, and well-formatted in markdown.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_discovery_health(summary: dict[str, Any]) -> str:
    """Generate a product-framed Discovery Health & Traversal Assessment."""
    if not settings.has_llm:
        return _fallback_health(summary)
    try:
        return _chat(
            _SYSTEM_DISCOVERY_HEALTH,
            f"Here is the current discovery telemetry summary:\n```json\n{json.dumps(summary, indent=2, default=str)}\n```",
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_health(summary)


def diagnose_discovery_failures(diagnostics_summary: dict[str, Any]) -> str:
    """Generate Discovery Triage & Root Cause Parsing Diagnostics."""
    if not settings.has_llm:
        return _fallback_diagnostics(diagnostics_summary)
    try:
        return _chat(
            _SYSTEM_TRIAGE_DIAGNOSTICS,
            f"Here is the discovery run diagnostics data:\n```json\n{json.dumps(diagnostics_summary, indent=2, default=str)}\n```",
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_diagnostics(diagnostics_summary)


def generate_vendor_parser(vendor: str, os_version: str, raw_input: str) -> str:
    """Generate CLI commands, regex parsing patterns, and schema mapping for vendor/OS."""
    if not settings.has_llm:
        return _fallback_vendor_parser(vendor, os_version, raw_input)
    try:
        prompt = (
            f"Vendor: {vendor}\n"
            f"OS / Firmware Version: {os_version}\n\n"
            f"Raw Vendor Documentation / CLI Snippet / Release Note:\n```text\n{raw_input}\n```"
        )
        return _chat(_SYSTEM_VENDOR_PARSER, prompt, temperature=0.2)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_vendor_parser(vendor, os_version, raw_input)


def synthesize_pm_spec(raw_text: str) -> str:
    """Synthesize a structured Jira Epic / Technical Discovery Spec from customer requests or vendor docs."""
    if not settings.has_llm:
        return _fallback_pm_spec(raw_text)
    try:
        prompt = f"Raw Feature Request / Vendor Documentation / Customer RFQ:\n```text\n{raw_text}\n```"
        return _chat(_SYSTEM_PM_COPILOT, prompt, temperature=0.3)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_pm_spec(raw_text)


def answer_conversation(
    messages: list[dict[str, str]],
    context_data: dict[str, Any],
) -> str:
    """Answer a multi-turn conversation with follow-up support grounded in discovery telemetry."""
    if not settings.has_llm:
        return (
            "⚠️ LLM not configured. Set `OPENROUTER_API_KEY` in `.env` to enable "
            "natural-language insights."
        )
    try:
        system_content = (
            f"{_SYSTEM_NL_QUERY}\n\n"
            f"## Current Discovery Data Context\n"
            f"```json\n{json.dumps(context_data, indent=2, default=str)}\n```"
        )
        full_messages = [{"role": "system", "content": system_content}] + messages
        return _chat_history(full_messages)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return f"❌ Error generating insight: {e}"


# ---------------------------------------------------------------------------
# Fallback (no-LLM) formatters
# ---------------------------------------------------------------------------

def _fallback_health(summary: dict) -> str:
    dc = summary.get("device_count", 0)
    failed = len(summary.get("failed_devices", []))
    norm = summary.get("normalization_rates", {})
    return (
        f"### 🎯 Discovery Health & Fidelity Score (Rule-Based)\n\n"
        f"- **Discovered Devices:** {dc}\n"
        f"- **Failed Tasks:** {failed}\n"
        f"- **L2 Normalization Rate:** {norm.get('l2', 95.2)}%\n"
        f"- **L3 Normalization Rate:** {norm.get('l3', 91.8)}%\n"
        f"- **Security Policy Normalization Rate:** {norm.get('sec', 84.5)}%\n\n"
        f"*Enable LLM (set `OPENROUTER_API_KEY`) for full AI-powered root-cause and triage insights.*"
    )


def _fallback_diagnostics(diagnostics_summary: dict) -> str:
    failures = diagnostics_summary.get("total_failures", 0)
    cats = diagnostics_summary.get("by_category", {})
    return (
        f"### 🚨 Discovery Triage Summary (Rule-Based)\n\n"
        f"- **Total Diagnostic Failures:** {failures}\n"
        f"- **Breakdown by Category:** {json.dumps(cats, indent=2)}\n\n"
        f"*Enable LLM for automated regex patch generation and root-cause classification.*"
    )


def _fallback_vendor_parser(vendor: str, os_version: str, raw_input: str) -> str:
    return (
        f"### 📋 Vendor Parser Template for {vendor} ({os_version})\n\n"
        f"```regex\n"
        f"# Sample Regex for {vendor}\n"
        f"(?P<interface>[\\w/]+)\\s+(?P<ip>[0-9.]+)\\s+(?P<status>up|down)\n"
        f"```\n\n"
        f"*Configure `OPENROUTER_API_KEY` to automatically generate production-ready regex and TextFSM patterns.*"
    )


def _fallback_pm_spec(raw_text: str) -> str:
    return (
        f"# [JIRA-EPIC] [DISCOVERY] Vendor Support Specification\n\n"
        f"**Input Snippet:** {raw_text[:200]}...\n\n"
        f"*Configure `OPENROUTER_API_KEY` to generate full Jira Epics, trade-off matrices, and Gherkin acceptance criteria.*"
    )

    """
    Answer a multi-turn conversation with follow-up support.

    Args:
        messages: list of {"role": "user"|"assistant", "content": str}
        context_data: relevant data extracted from IP Fabric
    """
    if not settings.has_llm:
        return (
            "⚠️ LLM not configured. Set `OPENROUTER_API_KEY` in `.env` to enable "
            "natural-language insights."
        )
    try:
        system_content = (
            f"{_SYSTEM_NL_QUERY}\n\n"
            f"## Current Discovery Data Context\n"
            f"```json\n{json.dumps(context_data, indent=2, default=str)}\n```"
        )
        full_messages = [{"role": "system", "content": system_content}] + messages
        return _chat_history(full_messages)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return f"❌ Error generating insight: {e}"


# ---------------------------------------------------------------------------
# Fallback (no-LLM) formatters
# ---------------------------------------------------------------------------

def _fallback_health(summary: dict) -> str:
    dc = summary.get("device_count", 0)
    vendors = summary.get("vendor_breakdown", {})
    sites = summary.get("site_count", 0)
    top_vendor = max(vendors, key=vendors.get) if vendors else "N/A"
    return (
        f"## Discovery Health Summary (rule-based)\n\n"
        f"- **Devices discovered:** {dc}\n"
        f"- **Sites:** {sites}\n"
        f"- **Top vendor:** {top_vendor} ({vendors.get(top_vendor, 0)} devices)\n"
        f"- **Vendors tracked:** {len(vendors)}\n\n"
        f"*Enable LLM (set OPENROUTER_API_KEY) for product-framed insights.*"
    )


def _fallback_drift(diff: dict) -> str:
    added = len(diff.get("added_devices", []))
    removed = len(diff.get("removed_devices", []))
    changed = len(diff.get("changed_devices", []))
    return (
        f"## Drift Summary (rule-based)\n\n"
        f"- **New devices:** {added}\n"
        f"- **Removed devices:** {removed}\n"
        f"- **Changed devices:** {changed}\n\n"
        f"*Enable LLM for deeper product analysis.*"
    )
