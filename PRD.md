# Discovery Insight Engine — Product Requirements

| | |
|---|---|
| Author | Ranaji Deb, candidate for Senior Product Manager – Network Discovery, IP Fabric |
| Status | Working prototype, tested against IP Fabric's three downloadable demo snapshots on a local IP Fabric 8.0 appliance |
| Purpose | Show how I would reason about the Network Discovery product area. Not an IP Fabric document. |

Figures marked **(demo snapshot)** were read from IP Fabric. Figures marked **(hypothesis)** are assumptions to validate; they are not IP Fabric or customer data.

---

## 1. Problem

Network Discovery is the upstream step for everything IP Fabric does: path lookup, intent checks, compliance and now AI use through the MCP server all depend on what discovery collected and modelled. When discovery misses something, the rest of the product is wrong without saying so.

After a run, a discovery admin needs to answer three questions quickly:

1. **Is the model complete enough to trust?** Which devices and which kinds of data are missing?
2. **Why was an address not discovered, and who has to act?** A timeout, a refused connection and a rejected credential each have a different owner.
3. **Is the discovery boundary right?** Which learned addresses sit outside the include list, and which neighbours are not managed?

IP Fabric already has the raw material: the Discovery Connectivity Report, Discovery Issues, managed IP tables, unmanaged neighbour tables and snapshot settings. The prototype tests whether joining them answers the three questions better than reading each table separately.

## 2. What the demo snapshots showed

**NFD - Day 0 pre-acquisition** (67 devices) (demo snapshot):

- 519 addresses processed: 72 discovered, 175 duplicates already queued, 226 outside the include list across 19 /16 ranges, 35 failed, 11 found but not attempted.
- **14 of the 35 failed addresses belong to devices already in the model** (for example 10.21.19.11 is L21C11 Et2/1). Only 21 are possible coverage gaps. The connectivity report shows all 35 as failures.
- 27 of 67 devices collected over Telnet; no site separation configured (all devices in site "unknown").
- One parser issue caused by a vendor bug: ASA L35FW1 reporting more than 100% memory use.

**S02 - Day 2 / Day 3 - Azure** (85 devices, 9 via the Azure API) (demo snapshot):

- Failed SSH/Telnet attempts on the gateway IPs of Azure VNet gateways that the Azure API had already discovered (10.193.0.62, 10.193.32.62).
- Day 3 adds an API task error on an Azure VPN gateway: "Cannot find the remote IP of the Local Network Gateway".

What this suggests (hypothesis, to validate with customers and Engineering):

- A large share of "failures" in the connectivity report are noise for the admin. Separating gaps from redundant attempts would shorten triage.
- CLI and API discovery do not yet share one view of what is already known.
- The addresses learned outside scope are a ready-made input for boundary suggestions.

## 3. Users

| User | Job | Pain today |
|---|---|---|
| Discovery / platform admin at a customer | Get a complete snapshot before change windows and audits | Reads several reports to work out why something is missing |
| IP Fabric solution architect in a PoC or onboarding | Show a new customer a complete model quickly | Triage of credentials, ACLs and scope takes the first days |
| Network Discovery PM and engineers | Decide what to build next in discovery | Evidence is spread across support tickets, field feedback and snapshots |

## 4. Scope of the prototype

### Built

| ID | Capability | Acceptance |
|---|---|---|
| DH-1 | Coverage by domain | For each device type that should have L2, L3 or security data, show the share of devices with at least one row in the relevant tables, and list the devices without. Rules are visible in the UI. |
| DH-2 | Discovery sources and outcomes | Addresses by how they were found (seed, CDP/LLDP, routes, ARP, traceroute, cloud API, discovery history) and what happened to them. |
| DH-3 | Access and run metrics | SSH / Telnet / API split, credential sets, duration, attempts, links, managed IPs. |
| DH-4 | Snapshot comparison | Devices added or removed, change in failure categories, new and resolved failures. |
| CT-1 | Failed-address triage | Each failed address with its full error chain, a category and a next check. |
| CT-2 | Gap vs redundant attempt | Join failed addresses to `tables/addressing/managed-devs`; label those that belong to a discovered device as "not a gap". |
| CT-3 | Boundary view | Learned addresses outside the include list grouped by /16 with how they were learned; unmanaged protocol neighbours. |
| VS-1 | Platform view | Platforms with device counts, access method and discovery issues; CLI attempts on API-discovered objects. |
| AI-1 | Grounded assessments | LLM receives only the snapshot JSON, must quote exact hostnames and IPs, and must separate gaps from redundant attempts. Failures of the LLM are shown, with a rule-based summary of the same data. |
| AI-2 | Drafting at development time | Draft commands, parser approach, table mapping and test fixture from a real discovery issue or pasted vendor output, for engineers to review. |
| OPS-1 | Record and replay | Record a live snapshot to JSON so a hosted copy can show real data without access to the appliance, clearly labelled. |

### Deliberately not built

1. **No configuration changes or remediation from the tool.** IP Fabric's value depends on being an independent, read-only source of truth. The tool produces checks and a follow-up checklist for people to act on.
2. **No LLM in the discovery path.** Parsing at runtime has to be deterministic and repeatable across tens of thousands of devices. AI is used for synthesis and for drafting parser material that engineers validate.
3. **No streaming telemetry or ping sweeps.** Discovery in IP Fabric is authenticated state collection; an address that does not authenticate is reported as a gap, not added as an unverified device.

## 5. Trade-offs I would expect to make in the role

**Core scale versus one-off legacy parsers.** A request to support end-of-life hardware for one account competes with queue and collection work that affects every large customer. My default would be to fix the shared foundation first and offer basic inventory for the legacy platform, unless the data (install base, renewal risk, cost to maintain) says otherwise. (hypothesis)

**Canonical model versus vendor-specific fields.** New vendor fields go into extensible attributes unless they change topology or policy analysis, to keep the model vendor-neutral.

**Vendor-support prioritisation.** A starting model to validate with Field and Engineering (hypothesis):

`Priority = 0.40 × reach in target accounts + 0.30 × impact on the network model + 0.20 × collection stability + 0.10 × customer requests`

Customer requests carry a low weight on purpose: the loudest request is not always the most common need. The weights themselves would be tested against past decisions.

## 6. Success measures (to baseline in the role)

| Measure | Baseline source | Direction |
|---|---|---|
| Share of failed addresses that are real gaps | Connectivity report joined with managed IPs (NFD demo: 21 of 35) | Report only real gaps to admins |
| Time from snapshot to a complete model in new deployments | PoC and onboarding data (not available to me) | Down |
| Discovery issues per 1,000 devices by platform | Discovery Issues report | Down, with vendor bugs tracked separately |
| CLI attempts on API-discovered objects | Connectivity report joined with inventory (S02 demo: 2) | Zero |
| New vendor/OS support lead time | Engineering data (not available to me) | Down, with AI-drafted parser material reviewed by engineers |

## 7. Next steps if this were a real project

1. Validate the three themes with 5–8 discovery admins and 2–3 solution architects: which of the three questions costs them the most time?
2. Check with Engineering whether redundant attempts on known devices are already filtered in newer releases, and what the cost of each attempt is.
3. Test boundary suggestions on real customer snapshots before designing UI.
4. Put the assistant on IP Fabric's MCP server instead of a JSON export.
