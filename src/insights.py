"""
Insight layer: turns the snapshot bundle (see data.py) into written assessments via an LLM (OpenRouter).

Rules:
  * The model only receives facts read from IP Fabric for the selected snapshot (data.llm_context()).
  * Every prompt forbids inventing hostnames, sites, IPs or numbers.
  * If the LLM call fails, the caller gets an explicit error plus a deterministic summary of the same data.
    There is no silent fallback.
  * AI is used for synthesis and drafting. Discovery itself stays deterministic.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from src.config import settings

logger = logging.getLogger(__name__)

_llm: OpenAI | None = None


class LLMError(RuntimeError):
    pass


def _get_llm() -> OpenAI:
    global _llm
    if _llm is None:
        if not settings.has_llm:
            raise LLMError("OPENROUTER_API_KEY is not configured")
        _llm = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key)
    return _llm


def _complete(messages: list[dict], temperature: float = 0.2) -> str:
    try:
        resp = _get_llm().chat.completions.create(
            model=settings.openrouter_model, messages=messages, temperature=temperature, max_tokens=3000,
        )
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("The model returned an empty response")
    return text


GROUNDING = """
Grounding rules (mandatory):
- Use only facts present in the JSON you are given. It was read from IP Fabric tables for one snapshot.
- Quote hostnames, IP addresses, sites, platforms and counts exactly as they appear. Never invent a device, site, IP, percentage or command.
- If the data does not contain something you would need, say "not in this snapshot's data" instead of guessing.
- Discovery tasks are addresses, not devices. A failed address with a non-null "owned_by" is an interface of a device that IP Fabric already discovered through another address: it is not a coverage gap. Say "addresses" and separate these from addresses not in the model.
- IP Fabric is read-only. Recommend checks and configuration changes for people to make; never describe actions as already done.
- Write plainly. No marketing language.
"""

_SYSTEM_HEALTH = """You are a product manager for IP Fabric's Network Discovery area reviewing one discovery snapshot.
Assess how complete and trustworthy this snapshot is as the basis for IP Fabric's network model.

Use this structure (markdown):
### Verdict
One or two sentences: is this snapshot complete enough for path analysis and compliance checks? Cite the numbers.
### Top findings (max 4)
For each: **title**, what the data shows (with counts, hostnames or IPs), why it matters for the network model, and the check a discovery admin should do next.
### Coverage by domain
One line each for L2, L3 and Security, using the coverage rules provided, and name the devices with no data if any.
### Product signals
Two or three observations a Discovery PM should take from this snapshot (patterns that would recur across customers), each tied to evidence in the data.
""" + GROUNDING

_SYSTEM_TRIAGE = """You are a discovery engineer triaging the Discovery Connectivity Report and Discovery Issues of one IP Fabric snapshot.

Use this structure (markdown):
### Summary
Totals by category with counts and share of attempted addresses.
### Failure clusters
Group failed addresses into clusters (by error type, subnet, discovery source, protocol). For each cluster: addresses not in the model (list them), addresses that are interfaces of already-discovered devices (list them with the owner from "owned_by"), a count for each that matches the lists, evidence (quote the error messages), likely cause, next check. Be explicit when a cause is a hypothesis.
### Parser / command issues
Explain each Discovery Issue row (device, command/task, error text) and what it means for the data from that device.
### Scope and boundary
What the out-of-scope ranges and unmanaged neighbours say about the discovery boundary.
### Is this snapshot good enough?
Two sentences.
""" + GROUNDING

_SYSTEM_VENDOR = """You help IP Fabric's Network Discovery team scope support for a vendor/OS or a failing command.
From the input (vendor docs, CLI output, or a discovery issue from a real snapshot), draft material for engineers to review:

### Scope
Vendor / platform / version, the capability in question, and what the data model needs from it.
### Commands or API calls to collect
Numbered list with the purpose of each. Mark anything you are unsure of.
### Draft parsing approach
A draft regex (Python, named groups) or TextFSM template for the sample provided. State that it is a draft to be validated against real device output.
### Mapping to IP Fabric tables
Which existing IP Fabric table each field would populate (use table names like tables/networks/routes when known; otherwise say "to confirm").
### Edge cases and risks
Version differences, pagination, large outputs, vendor bugs.
### Test fixture
A JSON test case: raw sample + expected parsed output.
""" + GROUNDING.replace("for one snapshot", "for one snapshot or pasted by the user")

_SYSTEM_PM = """You turn a raw customer request, escalation or vendor API note into a Network Discovery epic for IP Fabric.

### Problem statement
Who is affected, what they cannot do today, and the evidence in the input. Separate stated facts from assumptions.
### Scope
In scope / deliberately deferred / not doing, each with a one-line reason.
### Discovery approach
CLI or API, tables affected, scale considerations.
### Acceptance criteria
Gherkin scenarios.
### Open questions to validate with customers or engineering
### Priority recommendation
P0/P1/P2 with the reasoning. Do not invent revenue figures; if value is unknown, say what data would decide it.
""" + GROUNDING.replace("for one snapshot", "or pasted by the user")

_SYSTEM_CHAT = """You are an assistant for a Network Discovery product manager, answering questions about one IP Fabric snapshot.
Answer concisely in markdown, citing the exact hostnames, IPs, categories and counts from the data.
In production this assistant would sit on top of IP Fabric's MCP server rather than a JSON export.
""" + GROUNDING


def _payload(obj: Any) -> str:
    return "```json\n" + json.dumps(obj, indent=1, default=str) + "\n```"


def assess_discovery_health(context: dict) -> str:
    return _complete([{"role": "system", "content": _SYSTEM_HEALTH},
                      {"role": "user", "content": "Snapshot data:\n" + _payload(context)}])


def diagnose_discovery_failures(context: dict) -> str:
    return _complete([{"role": "system", "content": _SYSTEM_TRIAGE},
                      {"role": "user", "content": "Connectivity report and discovery issues:\n" + _payload(context)}])


def generate_vendor_parser(vendor: str, os_version: str, raw_input: str) -> str:
    prompt = f"Vendor: {vendor}\nOS / version: {os_version}\n\nInput:\n```text\n{raw_input}\n```"
    return _complete([{"role": "system", "content": _SYSTEM_VENDOR}, {"role": "user", "content": prompt}], 0.2)


def synthesize_pm_spec(raw_text: str) -> str:
    return _complete([{"role": "system", "content": _SYSTEM_PM},
                      {"role": "user", "content": f"Input:\n```text\n{raw_text}\n```"}], 0.3)


def answer_conversation(messages: list[dict[str, str]], context: dict) -> str:
    system = _SYSTEM_CHAT + "\n\nSnapshot data:\n" + _payload(context)
    return _complete([{"role": "system", "content": system}] + messages, 0.2)


# ---------------------------------------------------------------------------
# Deterministic summaries (shown when the LLM is unavailable, clearly labelled)
# ---------------------------------------------------------------------------
def rule_based_health(context: dict) -> str:
    cov = context["coverage"]
    ts = context["discovery_tasks"]
    lines = [
        "### Rule-based summary (no LLM)",
        f"- Snapshot **{context['data_provenance']['snapshot']}**: {context['snapshot']['device_count']} devices.",
        f"- Discovery tasks: {ts['total_tasks']} addresses — " + ", ".join(f"{k}: {v}" for k, v in ts["by_category"].items()),
    ]
    for dom, c in cov.items():
        if c["applicable"]:
            lines.append(f"- {c['label']}: {c['present']}/{c['applicable']} ({c['rate']}%)"
                         + (f"; no data: {', '.join(m['hostname'] for m in c['missing'])}" if c["missing"] else ""))
    if context["discovery_errors"]:
        for e in context["discovery_errors"]:
            lines.append(f"- Discovery issue on {e['hostname'] or e['loginIp']}: {e['errorType']} — {e['errorText']}")
    return "\n".join(lines)


def rule_based_triage(context: dict) -> str:
    lines = ["### Rule-based summary (no LLM)"]
    for t in context["failed_tasks"]:
        lines.append(f"- `{t['ip']}` ({t['category']}, source: {t['source']}, attempts: {t['attempts']}): "
                     + "; ".join(t["last_errors"]))
    return "\n".join(lines)
