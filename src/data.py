"""
Data layer: reads discovery data for one IP Fabric snapshot.

Two sources, never mixed silently:
  * live      -> IP Fabric REST API via the official Python SDK (ipfabric>=8.0)
  * recorded  -> a JSON export of the same bundle, previously recorded from a live snapshot
                 (demo_data/recorded/<snapshot_id>.json). Used by the hosted app.

Everything the UI and the LLM see comes from `load_bundle()`. Every bundle carries
`meta.source` ("live" or "recorded") so the UI can label it.

Definitions used for coverage metrics are documented in COVERAGE_RULES and shown in the UI.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
RECORDED_DIR = ROOT / "demo_data" / "recorded"
ILLUSTRATIVE_BACKLOG = ROOT / "demo_data" / "illustrative_vendor_backlog.json"


class DataSourceError(RuntimeError):
    """Raised when the configured data source cannot be read. Never swallowed silently."""


# ---------------------------------------------------------------------------
# Technology tables used to measure per-device data coverage
# ---------------------------------------------------------------------------
TECH_TABLES: dict[str, dict[str, str]] = {
    "l2": {
        "vlans": "tables/vlan/device",
        "mac_entries": "tables/addressing/mac",
        "stp_instances": "tables/spanning-tree/instances",
    },
    "l3": {
        "routes": "tables/networks/routes",
        "arp_entries": "tables/addressing/arp",
        "vrf_interfaces": "tables/vrf/interfaces",
        "ospf_neighbors": "tables/routing/protocols/ospf/neighbors",
        "bgp_neighbors": "tables/routing/protocols/bgp/neighbors",
    },
    "sec": {
        "acl_rules": "tables/security/acl",
        "zone_fw_policies": "tables/security/zone-firewall/policies",
        "aaa_servers": "tables/security/aaa/servers",
    },
}

COVERAGE_RULES = {
    "l2": {
        "label": "L2 data present",
        "applies_to": ["switch", "l3switch"],
        "rule": "Switching devices (devType switch / l3switch) with at least one row in VLAN, MAC or STP tables.",
    },
    "l3": {
        "label": "L3 data present",
        "applies_to": ["router", "l3switch", "fw"],
        "rule": "Routing-capable devices (router / l3switch / fw) with at least one row in the routing table.",
    },
    "sec": {
        "label": "Security data present",
        "applies_to": ["fw"],
        "rule": "Firewalls (devType fw) with at least one ACL or zone-firewall policy row.",
    },
}

SOURCE_LABELS = {
    "seed": "Seed IP",
    "xdp": "CDP/LLDP neighbour",
    "routes": "Routing table next-hop",
    "arp": "ARP entry",
    "trace": "Traceroute hop",
    "previouslyDiscovered": "Discovery history",
    "azure": "Azure API",
    "aws": "AWS API",
    "gcp": "GCP API",
}

# ---------------------------------------------------------------------------
# IP Fabric client
# ---------------------------------------------------------------------------
_client = None
_client_error: str | None = None


def _get_client():
    """Return a connected IPFClient, or raise DataSourceError with the reason."""
    global _client, _client_error
    if _client is not None:
        return _client
    try:
        from ipfabric import IPFClient

        _client = IPFClient(
            base_url=settings.ipf_url,
            auth=settings.ipf_token,
            verify=settings.ipf_verify,
            timeout=30,
        )
        _client_error = None
        return _client
    except Exception as e:  # connection, auth, TLS, missing SDK
        _client_error = f"{type(e).__name__}: {e}"
        raise DataSourceError(f"Could not connect to IP Fabric at {settings.ipf_url} ({_client_error})") from e


def reset_client():
    global _client, _client_error
    _client = None
    _client_error = None


def ipf_version() -> str | None:
    try:
        c = _get_client()
        return str(getattr(c, "os_version", None) or getattr(c, "api_version", ""))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Snapshot list
# ---------------------------------------------------------------------------
def list_snapshots() -> list[dict]:
    """Snapshots available from the configured source (newest first)."""
    if settings.is_live:
        ipf = _get_client()
        out = []
        for sid, snap in ipf.snapshots.items():
            if sid.startswith("$"):
                continue
            out.append({
                "id": sid,
                "name": snap.name or sid[:8],
                "status": snap.status,
                "device_count": snap.total_dev_count,
                "start": snap.start.isoformat() if snap.start else None,
            })
        if not out:
            raise DataSourceError("Connected to IP Fabric, but no loaded snapshots were found.")
        return sorted(out, key=lambda s: s["start"] or "", reverse=True)
    return list_recorded_snapshots()


def list_recorded_snapshots() -> list[dict]:
    idx = RECORDED_DIR / "index.json"
    if not idx.exists():
        raise DataSourceError(
            "No recorded snapshot export found (demo_data/recorded/index.json). "
            "Run the app once in live mode and use 'Record this snapshot' in the sidebar."
        )
    return json.loads(idx.read_text())


# ---------------------------------------------------------------------------
# Bundle builder (live)
# ---------------------------------------------------------------------------
def _ts(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, tz=timezone.utc).isoformat()
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _rows_per_sn(ipf, table: str, sid: str, sn_col: str = "sn") -> Counter:
    rows = ipf.fetch_all(table, snapshot_id=sid, columns=[sn_col])
    return Counter(r.get(sn_col) for r in rows)


def _classify_task(t: dict) -> str:
    status = t.get("status")
    if status == "ok":
        return "Discovered"
    if status == "deviceAlreadyInQueue":
        return "Duplicate path (already queued)"
    if status == "notInIncludeList":
        return "Outside discovery scope"
    if status == "found":
        return "Found, not attempted"
    if status != "error":
        return status or "Unknown"
    etype = t.get("errorType") or ""
    msgs = " ".join((r.get("msg") or "") for r in (t.get("errorReasons") or []))
    if etype == "ABWorkerAuthError" or "authentication" in msgs.lower():
        return "Authentication failed"
    if "ETIMEDOUT" in msgs or "timed out" in msgs.lower():
        return "Connection timed out"
    if "ECONNREFUSED" in msgs:
        return "Connection refused"
    if etype:
        return etype
    return status or "Unknown"


FAILURE_CATEGORIES = ("Authentication failed", "Connection timed out", "Connection refused")

OWNED_NOTE = ("This address is an interface of {owner}, which IP Fabric already discovered through another address. "
              "It is not a coverage gap. The failed attempt is noise in the report and costs discovery time.")

NEXT_CHECK = {
    "Authentication failed": "Every configured credential was rejected. Check which credential set should match this IP range and whether the account exists on the device's AAA server.",
    "Connection timed out": "No TCP answer on SSH (22) or Telnet (23) from the IP Fabric appliance. Check routing and any firewall/ACL between the appliance (or jumphost) and this address, or whether it is a non-manageable address.",
    "Connection refused": "The host answered but refused SSH and Telnet. Management access is disabled or restricted by a management ACL on the device.",
    "Outside discovery scope": "Address was learned but is not in the include list. Decide whether this range should be in scope.",
}


def _build_live_bundle(sid: str) -> dict:
    ipf = _get_client()
    snap = ipf.snapshots.get(sid)
    if snap is None:
        raise DataSourceError(f"Snapshot {sid} not found on the IP Fabric instance.")

    # --- inventory -------------------------------------------------------
    inv = ipf.fetch_all(
        "tables/inventory/devices", snapshot_id=sid,
        columns=["hostname", "siteName", "vendor", "family", "platform", "model", "version", "devType",
                 "loginType", "loginIp", "sn", "uptime", "memoryUtilization"],
    )
    sdev = {r["sn"]: r for r in ipf.fetch_all(
        "tables/snapshot-devices", snapshot_id=sid, columns=["sn", "source", "settingsStates", "isApiTask"])}

    counts: dict[str, dict[str, Counter]] = {dom: {} for dom in TECH_TABLES}
    for dom, tables in TECH_TABLES.items():
        for key, table in tables.items():
            try:
                counts[dom][key] = _rows_per_sn(ipf, table, sid)
            except Exception as e:
                logger.warning("Table %s unavailable: %s", table, e)
                counts[dom][key] = Counter()

    derrs = ipf.fetch_all("tables/reports/discovery-errors", snapshot_id=sid)
    ip_to_host = {d.get("loginIp"): d.get("hostname") for d in inv if d.get("loginIp")}
    issues_by_ip = Counter(e.get("loginIp") for e in derrs)

    devices = []
    for d in inv:
        sn = d.get("sn")
        row = {k: d.get(k) for k in ["hostname", "siteName", "vendor", "family", "platform", "model", "version",
                                      "devType", "loginType", "loginIp", "sn", "uptime", "memoryUtilization"]}
        row["discovery_source"] = (sdev.get(sn) or {}).get("source")
        row["api_discovered"] = bool((sdev.get(sn) or {}).get("isApiTask")) or d.get("loginType") == "api"
        for dom, tables in counts.items():
            for key, ctr in tables.items():
                row[key] = int(ctr.get(sn, 0))
        row["discovery_issues"] = int(issues_by_ip.get(d.get("loginIp"), 0))
        devices.append(row)

    # --- which IPs belong to devices already in the model -----------------
    try:
        managed = ipf.fetch_all("tables/addressing/managed-devs", snapshot_id=sid, columns=["hostname", "intName", "ip"])
    except Exception as e:
        logger.warning("managed-devs unavailable: %s", e)
        managed = []
    ip_owner = {m.get("ip"): f'{m.get("hostname")} {m.get("intName") or ""}'.strip() for m in managed if m.get("ip")}

    # --- connectivity report (discovery tasks) ---------------------------
    raw_tasks = ipf.fetch_all("tables/reports/discovery-tasks", snapshot_id=sid)
    tasks = []
    for t in raw_tasks:
        reasons = sorted(t.get("errorReasons") or [], key=lambda r: r.get("ts") or 0)
        tasks.append({
            "ip": t.get("ip"),
            "dnsName": t.get("dnsName"),
            "source": t.get("source"),
            "status": t.get("status"),
            "errorType": t.get("errorType"),
            "category": _classify_task(t),
            "attempts": t.get("attemptCount") or 0,
            "vendor": t.get("vendor"),
            "hostname": ip_to_host.get(t.get("ip")),
            "owned_by": ip_owner.get(t.get("ip")),
            "reasons": [
                {"ts": _ts(r.get("ts")), "protocol": r.get("source"), "msg": r.get("msg"), "type": r.get("errType")}
                for r in reasons
            ],
        })

    discovery_errors = [{
        "loginIp": e.get("loginIp"),
        "hostname": ip_to_host.get(e.get("loginIp")),
        "loginType": e.get("loginType"),
        "taskId": e.get("taskId"),
        "errorType": e.get("errorType"),
        "errorText": e.get("errorText"),
        "version": e.get("version"),
    } for e in derrs]

    # --- neighbours not managed by IP Fabric ------------------------------
    unmanaged_proto = ipf.fetch_all("tables/interfaces/connectivity-matrix/unmanaged-neighbors/summary", snapshot_id=sid)
    unmanaged_proto = [{
        "hostname": u.get("hostname"), "siteName": u.get("siteName"), "neighbor_ip": u.get("ip"),
        "bgp": u.get("bgpNeiCount") or 0, "bgp_asn": u.get("bgpNeiAsn"), "ospf": u.get("ospfNeiCount") or 0,
        "eigrp": u.get("eigrpNeiCount") or 0, "cdp_lldp": u.get("xdpNeiCount") or 0, "ldp": u.get("ldpNeiCount") or 0,
    } for u in unmanaged_proto]
    unmanaged_xdp = ipf.fetch_all("tables/neighbors/unmanaged", snapshot_id=sid)
    unmanaged_xdp = [{k: u.get(k) for k in ["localHost", "localInt", "siteName", "remoteHost", "remoteIp",
                                             "remoteInt", "protocols", "capabilities"]} for u in unmanaged_xdp]

    # --- endpoint MAC vendors (OUI) seen on user ports --------------------
    macs = ipf.fetch_all("tables/addressing/mac", snapshot_id=sid, columns=["user", "vendor", "mac"])
    mac_vendors = Counter((m.get("vendor") or "Unknown OUI") for m in macs if m.get("user"))

    # --- run / settings --------------------------------------------------
    runs = ipf.fetch_all("tables/management/discovery-runs", snapshot=False)
    run = next((r for r in runs if r.get("id") == sid), {})
    try:
        s = ipf.get(f"snapshots/{sid}/settings").json()
    except Exception as e:
        logger.warning("Snapshot settings unavailable: %s", e)
        s = {}
    settings_summary = {
        "seed_list": s.get("seedList", []),
        "include_networks": (s.get("networks") or {}).get("include", []),
        "exclude_networks": (s.get("networks") or {}).get("exclude", []),
        "task_sources": (s.get("limitDiscoveryTasks") or {}).get("sourceOfTasks", []),
        "allow_telnet": s.get("allowTelnet"),
        "cli_retry_limit": s.get("cliRetryLimit"),
        "discovery_history_seeds": (s.get("discoveryHistorySeeds") or {}).get("enabled"),
        "disabled_tasks": [d.get("label") for d in s.get("discoveryTasks", [])],
        "credential_sets": len(s.get("credentials", []) or []),
        "vendor_api_types": sorted({v.get("type") for v in (s.get("vendorApi") or []) if v.get("type")}),
    }

    start, end = snap.start, snap.end
    meta = {
        "snapshot_id": sid,
        "name": snap.name,
        "status": snap.status,
        "start": _ts(start),
        "end": _ts(end),
        "duration_sec": (end - start).total_seconds() if start and end else None,
        "device_count": snap.total_dev_count,
        "snapshot_errors": [{"type": e.error_type, "count": e.count} for e in (snap.errors or [])],
        "ipf_version": ipf_version(),
        "source": "live",
        "read_at": datetime.now(timezone.utc).isoformat(),
        "ipf_url": settings.ipf_url,
    }
    run_summary = {k: run.get(k) for k in ["deviceCount", "connectionCount", "interfaceCount",
                                           "interfaceActiveCount", "interfaceEdgeCount", "managedIpCount",
                                           "userCount"]}
    return {
        "meta": meta,
        "run": run_summary,
        "settings": settings_summary,
        "devices": devices,
        "tasks": tasks,
        "discovery_errors": discovery_errors,
        "unmanaged_protocol_neighbors": unmanaged_proto,
        "unmanaged_cdp_lldp_neighbors": unmanaged_xdp,
        "endpoint_mac_vendors": dict(mac_vendors.most_common(15)),
    }


# ---------------------------------------------------------------------------
# Public: load / record
# ---------------------------------------------------------------------------
def load_bundle(snapshot_id: str) -> dict:
    if settings.is_live:
        return _build_live_bundle(snapshot_id)
    path = RECORDED_DIR / f"{snapshot_id}.json"
    if not path.exists():
        raise DataSourceError(f"No recorded export for snapshot {snapshot_id}.")
    b = json.loads(path.read_text())
    b["meta"]["source"] = "recorded"
    return b


def record_bundle(bundle: dict) -> Path:
    """Write a live bundle to demo_data/recorded so the hosted app can show real (recorded) data."""
    RECORDED_DIR.mkdir(parents=True, exist_ok=True)
    b = json.loads(json.dumps(bundle, default=str))
    b["meta"]["recorded_at"] = datetime.now(timezone.utc).isoformat()
    b["meta"].pop("ipf_url", None)
    sid = b["meta"]["snapshot_id"]
    path = RECORDED_DIR / f"{sid}.json"
    path.write_text(json.dumps(b, indent=1))
    idx_path = RECORDED_DIR / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [i for i in idx if i["id"] != sid]
    idx.append({"id": sid, "name": b["meta"]["name"], "status": b["meta"]["status"],
                "device_count": b["meta"]["device_count"], "start": b["meta"]["start"],
                "recorded_at": b["meta"]["recorded_at"]})
    idx.sort(key=lambda s: s["start"] or "", reverse=True)
    idx_path.write_text(json.dumps(idx, indent=1))
    return path


# ---------------------------------------------------------------------------
# Derived metrics (pure functions over a bundle)
# ---------------------------------------------------------------------------
def coverage(bundle: dict) -> dict:
    """Per-domain coverage using COVERAGE_RULES. Returns rates and the device lists behind them."""
    out = {}
    for dom, rule in COVERAGE_RULES.items():
        keys = list(TECH_TABLES[dom].keys())
        if dom == "sec":
            keys = ["acl_rules", "zone_fw_policies"]
        if dom == "l3":
            keys = ["routes"]
        applicable = [d for d in bundle["devices"] if d.get("devType") in rule["applies_to"]]
        present = [d for d in applicable if any(d.get(k, 0) > 0 for k in keys)]
        missing = [d for d in applicable if d not in present]
        out[dom] = {
            "label": rule["label"],
            "rule": rule["rule"],
            "applicable": len(applicable),
            "present": len(present),
            "rate": round(100 * len(present) / len(applicable), 1) if applicable else None,
            "missing": [{"hostname": d["hostname"], "siteName": d["siteName"], "devType": d["devType"],
                         "platform": f'{d["vendor"]} {d.get("family") or ""} {d.get("platform") or ""} {d.get("version") or ""}'.strip()}
                        for d in missing],
        }
    return out


def task_summary(bundle: dict) -> dict:
    tasks = bundle["tasks"]
    by_cat = Counter(t["category"] for t in tasks)
    by_source = Counter(t["source"] for t in tasks)
    matrix = defaultdict(Counter)
    for t in tasks:
        matrix[SOURCE_LABELS.get(t["source"], t["source"])][t["category"]] += 1
    failures = [t for t in tasks if t["category"] in FAILURE_CATEGORIES or t.get("status") == "error"]
    known = [t for t in failures if t.get("owned_by")]
    seeds = bundle["settings"].get("seed_list", [])
    seed_tasks = [t for t in tasks if t["source"] == "seed" or t["ip"] in seeds]
    return {
        "total_tasks": len(tasks),
        "by_category": dict(by_cat),
        "by_source": {SOURCE_LABELS.get(k, k): v for k, v in by_source.items()},
        "source_outcome_matrix": {k: dict(v) for k, v in matrix.items()},
        "failures": failures,
        "failures_on_discovered_devices": len(known),
        "failures_not_in_model": len(failures) - len(known),
        "total_attempts": sum(t["attempts"] for t in tasks),
        "seeds": seeds,
        "seeds_ok": sum(1 for t in seed_tasks if t["status"] == "ok"),
    }


def out_of_scope_ranges(bundle: dict, prefix: int = 16) -> list[dict]:
    """Group addresses that were learned but excluded by the include list."""
    groups: dict[str, dict] = {}
    for t in bundle["tasks"]:
        if t["category"] != "Outside discovery scope" or not t.get("ip"):
            continue
        try:
            net = str(ipaddress.ip_network(f'{t["ip"]}/{prefix}', strict=False))
        except ValueError:
            continue
        g = groups.setdefault(net, {"range": net, "addresses": 0, "learned_from": Counter()})
        g["addresses"] += 1
        g["learned_from"][SOURCE_LABELS.get(t["source"], t["source"])] += 1
    out = []
    for g in sorted(groups.values(), key=lambda x: -x["addresses"]):
        out.append({"range": g["range"], "addresses": g["addresses"],
                    "learned_from": ", ".join(f"{k} ({v})" for k, v in g["learned_from"].most_common())})
    return out


def platform_matrix(bundle: dict) -> list[dict]:
    """Vendor / platform / version rows with device counts, issues and coverage per platform."""
    groups: dict[tuple, list] = defaultdict(list)
    for d in bundle["devices"]:
        groups[(d["vendor"], d.get("family") or "", d.get("platform") or "", d.get("version") or "")].append(d)
    rows = []
    for (vendor, family, platform, version), devs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rows.append({
            "vendor": vendor, "family": family, "platform": platform, "version": version,
            "devices": len(devs),
            "devTypes": ", ".join(sorted({d["devType"] for d in devs if d.get("devType")})),
            "access": ", ".join(sorted({d["loginType"] for d in devs if d.get("loginType")})),
            "discovery_issues": sum(d["discovery_issues"] for d in devs),
            "routes": sum(d.get("routes", 0) for d in devs),
            "acl_rules": sum(d.get("acl_rules", 0) for d in devs),
            "vlans": sum(d.get("vlans", 0) for d in devs),
        })
    return rows


def access_summary(bundle: dict) -> dict:
    devs = bundle["devices"]
    return {
        "by_login_type": dict(Counter(d.get("loginType") or "unknown" for d in devs)),
        "telnet_devices": [d["hostname"] for d in devs if d.get("loginType") == "telnet"],
        "auth_failures": sum(1 for t in bundle["tasks"] if t["category"] == "Authentication failed"),
        "credential_sets": bundle["settings"].get("credential_sets"),
        "allow_telnet": bundle["settings"].get("allow_telnet"),
    }


def site_summary(bundle: dict) -> list[dict]:
    by = defaultdict(list)
    for d in bundle["devices"]:
        by[d.get("siteName") or "unknown"].append(d)
    return [{"site": s, "devices": len(v), "devTypes": dict(Counter(d["devType"] for d in v))}
            for s, v in sorted(by.items(), key=lambda kv: -len(kv[1]))]


def llm_context(bundle: dict, max_failures: int = 40) -> dict:
    """Compact, fully-sourced context for the LLM. Only facts from the bundle."""
    ts = task_summary(bundle)
    cov = coverage(bundle)
    return {
        "data_provenance": {
            "source": bundle["meta"]["source"],
            "snapshot": bundle["meta"]["name"],
            "snapshot_id": bundle["meta"]["snapshot_id"],
            "snapshot_taken": bundle["meta"]["start"],
            "note": "All values below were read from IP Fabric tables for this snapshot. No synthetic data.",
        },
        "snapshot": {k: bundle["meta"][k] for k in ["device_count", "duration_sec", "snapshot_errors"]},
        "run": bundle["run"],
        "discovery_settings": bundle["settings"],
        "coverage": {k: {kk: vv for kk, vv in v.items()} for k, v in cov.items()},
        "discovery_tasks": {k: v for k, v in ts.items() if k != "failures"},
        "failed_tasks": [{k: t.get(k) for k in ["ip", "dnsName", "hostname", "owned_by", "source", "category", "attempts"]}
                         | {"last_errors": [r["msg"] for r in t["reasons"][-2:]],
                            "coverage_gap": not t.get("owned_by"),
                            "interpretation": (OWNED_NOTE.format(owner=t["owned_by"]) if t.get("owned_by")
                                               else NEXT_CHECK.get(t["category"], ""))}
                         for t in ts["failures"][:max_failures]],
        "discovery_errors": bundle["discovery_errors"],
        "out_of_scope_ranges": out_of_scope_ranges(bundle),
        "unmanaged_protocol_neighbors_total": len(bundle["unmanaged_protocol_neighbors"]),
        "unmanaged_protocol_neighbors_sample": bundle["unmanaged_protocol_neighbors"][:40],
        "unmanaged_cdp_lldp_neighbors": bundle["unmanaged_cdp_lldp_neighbors"][:40],
        "access": access_summary(bundle),
        "sites": site_summary(bundle),
        "platforms": platform_matrix(bundle),
        "endpoint_mac_vendors": bundle["endpoint_mac_vendors"],
    }


def illustrative_backlog() -> list[dict]:
    if ILLUSTRATIVE_BACKLOG.exists():
        return json.loads(ILLUSTRATIVE_BACKLOG.read_text())
    return []
