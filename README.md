# Discovery Insight Engine

A proof of concept built by **Ranaji Deb** as part of an application for the **Senior Product Manager – Network Discovery** role at IP Fabric. It is not an IP Fabric product.

It reads one IP Fabric snapshot through the public Python SDK and answers the questions a Network Discovery PM asks after every run: how complete is the model, why were addresses not discovered, which failures are real gaps, and what does this say about vendor and platform support.

**Data:** everything shown comes from IP Fabric tables for the selected snapshot. It was built and tested against the three demo snapshots IP Fabric provides for download (NFD - Day 0 pre-acquisition, S02 - Day 2 - Azure, S02 - Day 3 - Azure via backup), loaded into a local IP Fabric 8.0 appliance. The only non-IP Fabric content is a vendor-support scoring example, labelled "illustrative" in the app.

## What it does

| Tab | What it shows | IP Fabric sources |
|---|---|---|
| Discovery Health | Devices in the model; L2 / L3 / security data coverage by device type; how addresses were found (seed, CDP/LLDP, routes, ARP, traceroute, cloud API, discovery history) and what happened to them; management access (SSH / Telnet / API); run metrics; site coverage; snapshot-to-snapshot comparison; AI assessment | `tables/inventory/devices`, `tables/snapshot-devices`, technology tables (VLAN, MAC, STP, routes, ARP, VRF, OSPF, BGP, ACL, zone firewall, AAA), `tables/reports/discovery-tasks`, `tables/management/discovery-runs`, snapshot settings |
| Connectivity Triage | Every failed address with its error chain, split into **coverage gaps** and **extra interfaces of devices already discovered through another IP**; discovery issues on reached devices; learned addresses outside the include list; unmanaged protocol neighbours; AI triage; downloadable follow-up checklist | `tables/reports/discovery-tasks`, `tables/reports/discovery-errors`, `tables/addressing/managed-devs`, `tables/interfaces/connectivity-matrix/unmanaged-neighbors/summary`, `tables/neighbors/unmanaged` |
| Vendor & Platform Support | Platforms in the snapshot with issues per platform; CLI attempts on cloud objects already discovered by API; illustrative scoring model; AI drafting of commands, parser approach and test fixtures (from a real discovery issue or pasted vendor output) | Inventory, discovery issues |
| PM Copilot | Evidence log tying roadmap themes to what the snapshot shows; AI drafting of an epic from a raw request | Derived from the above |
| Assistant | Questions about the snapshot, answered only from its data | Derived from the above |

Design choices:

- **No silent fallbacks.** If IP Fabric or the LLM cannot be reached, the app says so. The LLM fallback is a labelled rule-based summary of the same data.
- **Grounded AI.** The model receives only a JSON context built from the snapshot (`data.llm_context`) and is told not to invent devices, IPs or numbers. The "What the model sees" popover shows the exact input.
- **Read-only.** The app recommends checks; it has no buttons that claim to change anything.
- **AI at development time, not at discovery time.** The vendor tool drafts parser material for engineers to review. Discovery itself stays deterministic.

## Findings from the demo snapshots

From NFD - Day 0 pre-acquisition (67 devices):

- 519 addresses in the connectivity report: 72 discovered, 175 duplicates already in the queue, 226 outside the include list (19 /16 ranges), 35 failed, 11 found but not attempted.
- 14 of the 35 failed addresses are other interfaces of devices already in the model (for example 10.21.19.11 on L21C11 Et2/1). Only 21 are possible coverage gaps. The report does not separate the two.
- 27 of 67 devices were collected over Telnet. No site separation was configured, so every device sits in site "unknown".
- One vendor-bug parse error: ASA L35FW1, `commands/cisco/memory`, "Vendor bug - ASA with more than 100% memory usage".

From S02 - Day 2 / Day 3 - Azure (85 devices, 9 through the Azure API):

- 2 failed SSH/Telnet attempts targeted the gateway IPs of Azure VNet gateways that IP Fabric had already discovered through the API (10.193.0.62, 10.193.32.62).
- Day 3 adds an API task error: "Cannot find the remote IP of the Local Network Gateway".

## Running it

Requirements: Python 3.10+, an IP Fabric appliance with an API token for live mode, and an OpenRouter key for the AI features (optional).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env      # set IPF_URL, IPF_TOKEN, OPENROUTER_API_KEY
streamlit run app.py
```

### Data modes

- `DATA_MODE=live` reads the snapshots on the appliance at `IPF_URL`.
- `DATA_MODE=recorded` reads `demo_data/recorded/`, a JSON export of the same data recorded from a live snapshot with the **Record this snapshot** button. The hosted version uses this mode because it cannot reach a local appliance, and it labels the data as a recorded export.

Environment variables and Streamlit secrets take precedence over `.env`.

## Files

```
app.py                      Streamlit UI
src/data.py                 IP Fabric reads, bundle builder, coverage rules, derived metrics
src/insights.py             LLM prompts (grounded) and rule-based summaries
src/compare.py              snapshot-to-snapshot comparison
src/config.py               settings
demo_data/recorded/         recorded exports of the IP Fabric demo snapshots
demo_data/illustrative_vendor_backlog.json   illustrative scoring example (not IP Fabric data)
demo_data/synthetic_legacy/ earlier synthetic fixtures, no longer used
PRD.md                      product thinking behind the prototype
```

## Roadmap themes this points to

1. **Explain every undiscovered address.** Separate real gaps from redundant attempts on known devices, and route timeouts, refusals and authentication failures to the right owner.
2. **Boundary suggestions.** Use the addresses learned outside the include list to suggest scope changes, with the risk of each.
3. **One discovery model for CLI and API.** Stop queueing CLI attempts for objects already discovered through a cloud or controller API, and treat API task errors with the same visibility as CLI errors.

---
Ranaji Deb · candidate for Senior Product Manager – Network Discovery, IP Fabric
