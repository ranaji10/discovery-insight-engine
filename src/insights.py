"""
Insight Engine — turns raw IP Fabric data into product-framed insights
using an LLM via OpenRouter.

Each function accepts structured data and returns a product-manager-quality
narrative with priorities and recommendations.
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
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""


def _chat_history(messages: list[dict], temperature: float = 0.3) -> str:
    """Send a full message list and return the assistant message."""
    client = _get_llm()
    resp = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        temperature=temperature,
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_DISCOVERY_HEALTH = """\
You are the AI Insight Engine for Network Discovery at IP Fabric.
You receive structured network inventory data and produce an executive Discovery Health Assessment.

Your output format MUST strictly follow this structure:

### 🎯 Discovery Health Score
**Status:** [Good / Needs Attention / Critical] — [1-sentence rationale with specific counts]

### 🔍 Top Discovery Findings & Impact
For each of the top 2-3 findings:
- **Finding [N]: [Clear, descriptive title]**
  - **What Happened:** [Specific data observation with device names, sites, or counts]
  - **Why It Matters:** [Operational, security, or compliance impact for the customer]
  - **Insight Engine Recommendation:** [Concrete product or architectural recommendation]
  - **⚡ Immediate Operational Actions:**
    - [Action 1: e.g., Check device credentials in Settings ➔ Device Credentials for `hostname`]
    - [Action 2: e.g., Test SNMP/SSH reachability or verify ACL rules for subnet]

### 🛠️ Strategic & Process Actions
- **[Strategic Action 1]:** [Long-term process or architectural initiative, e.g. Credential lifecycle integration]
- **[Strategic Action 2]:** [Policy or alerting initiative, e.g. Configure Webhook alert rule for failed WAN devices]

### 📌 Executive Summary
[A concise 2-sentence summary providing the bottom-line takeaway for the VP of Infrastructure or CISO.]

Keep formatting clean, professional, and grounded in the provided numbers.
"""

_SYSTEM_DRIFT = """\
You are the AI Insight Engine for Network Discovery at IP Fabric.
You receive a structured diff between two network snapshots and produce a Drift Analysis Report.

Your output format MUST strictly follow this structure:

### 📊 Mutation & Drift Overview
[Summary of added, removed, and modified devices/attributes between snapshots.]

### 🚨 Prioritized Drift Findings
For each key finding (up to 3):
- **Drift Item [N]: [Title]**
  - **Observed Mutation:** [What changed, appeared, or disappeared]
  - **Risk & Intent Impact:** [How this impacts routing, security segmentation, or intent verification]
  - **Insight Engine Recommendation:** [Recommended next step]
  - **⚡ Immediate Operational Actions:**
    - [Action: e.g., Validate change ticket against discovered mutation]

### 🛠️ Strategic & Process Actions
- **[Strategic Action]:** [e.g., Automate pre/post change window snapshot comparisons via CI/CD Webhooks]

### 📌 Executive Summary
[2-sentence bottom-line takeaway on network stability, intent adherence, and discovery quality verdict.]

Keep formatting clean, professional, and grounded in the provided numbers.
"""

_SYSTEM_NL_QUERY = """\
You are the AI Insight Engine for Network Discovery at IP Fabric.
You have access to structured network inventory and topology data provided in the context.
Answer the user's question with deep domain insight and clear product framing.

Rules:
- Be specific with numbers, hostnames, platforms, and sites from the data.
- Include an "Insight Engine Recommendation" where relevant.
- Suggest "⚡ Immediate Operational Actions" when troubleshooting or risk remediation is needed.
- Frame answers around customer ROI, risk reduction, and operational stability.
- Keep answers concise, direct, and well-formatted in markdown.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_discovery_health(summary: dict[str, Any]) -> str:
    """
    Generate a product-framed Discovery Health Assessment.

    Args:
        summary: dict with keys like device_count, vendor_breakdown,
                 site_count, failed_devices, interface_stats, etc.
    """
    if not settings.has_llm:
        return _fallback_health(summary)
    try:
        return _chat(
            _SYSTEM_DISCOVERY_HEALTH,
            f"Here is the current discovery data summary:\n```json\n{json.dumps(summary, indent=2, default=str)}\n```",
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_health(summary)


def analyse_drift(diff: dict[str, Any]) -> str:
    """
    Generate a Drift Analysis from snapshot comparison data.

    Args:
        diff: dict with keys like added_devices, removed_devices,
              changed_devices, snapshot_a, snapshot_b, etc.
    """
    if not settings.has_llm:
        return _fallback_drift(diff)
    try:
        return _chat(
            _SYSTEM_DRIFT,
            f"Here is the snapshot diff:\n```json\n{json.dumps(diff, indent=2, default=str)}\n```",
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _fallback_drift(diff)


def answer_question(question: str, context_data: dict[str, Any]) -> str:
    """
    Answer a natural-language question using structured data as context.

    Args:
        question: user's question in natural language
        context_data: relevant data extracted from IP Fabric
    """
    return answer_conversation([{"role": "user", "content": question}], context_data)


def answer_conversation(
    messages: list[dict[str, str]],
    context_data: dict[str, Any],
) -> str:
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
