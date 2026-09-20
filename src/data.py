"""
Data layer — connects to IP Fabric via the Python SDK (live mode)
or loads bundled JSON fixtures (demo mode).

Every public function returns plain dicts / lists so the rest of the app
never touches the SDK directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import settings

logger = logging.getLogger(__name__)

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_data"

# ---------------------------------------------------------------------------
# IP Fabric SDK client (lazy singleton)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    """Return a cached IPFClient instance (live mode only)."""
    global _client
    if _client is not None:
        return _client

    if not settings.is_live:
        raise RuntimeError("Cannot create IPFClient in demo mode")

    from ipfabric import IPFClient  # imported lazily so demo mode works without SDK

    try:
        _client = IPFClient(
            base_url=settings.ipf_url,
            auth=settings.ipf_token,
            verify=settings.ipf_verify,
            timeout=5,
        )
        logger.info("Connected to IP Fabric %s (API %s)", _client.hostname, _client.api_version)
        return _client
    except Exception as e:
        logger.warning("Failed to connect to IP Fabric at %s (%s) — falling back to demo mode", settings.ipf_url, e)
        return None


# ---------------------------------------------------------------------------
# Helper: load demo JSON
# ---------------------------------------------------------------------------
def _load_demo(name: str) -> list[dict]:
    path = DEMO_DIR / f"{name}.json"
    if not path.exists():
        logger.warning("Demo file %s not found — returning empty list", path)
        return []
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reset_client():
    """Clear client cache to force fresh connection & snapshot fetch."""
    global _client
    _client = None


def get_snapshots() -> list[dict]:
    """Return list of snapshot metadata."""
    if settings.is_live:
        try:
            ipf = _get_client()
            if ipf is not None:
                # If supported, trigger snapshot refresh in SDK
                if hasattr(ipf.snapshots, "update"):
                    try:
                        ipf.snapshots.update()
                    except Exception:
                        pass
                res = []
                for k, v in ipf.snapshots.items():
                    # Skip alias keys like $last, $prev
                    if k.startswith("$"):
                        continue
                    sid = getattr(v, "snapshot_id", k)
                    sname = getattr(v, "name", None) or k[:8]
                    res.append({
                        "id": str(sid),
                        "name": str(sname),
                        "state": getattr(v, "state", "loaded"),
                        "device_count": getattr(v, "total_dev_count", 0),
                        "licensed_count": getattr(v, "licensed_dev_count", 0),
                    })
                if res:
                    return res
        except Exception as e:
            logger.warning("Error fetching snapshots from live instance: %s", e)
    return _load_demo("snapshots")


def get_devices(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return device inventory as a DataFrame."""
    if settings.is_live:
        try:
            ipf = _get_client()
            if ipf is not None:
                columns = [
                    "hostname", "vendor", "platform", "model", "siteName",
                    "loginIpv4", "uptime", "version", "sn", "taskKey",
                ]
                kwargs: dict[str, Any] = {"columns": columns}
                if snapshot_id:
                    kwargs["snapshot_id"] = snapshot_id
                rows = ipf.inventory.devices.all(**kwargs)
                return pd.DataFrame(rows)
        except Exception as e:
            logger.warning("Error fetching devices from live instance: %s", e)

    return pd.DataFrame(_load_demo("devices"))


def get_sites(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return sites table."""
    if settings.is_live:
        ipf = _get_client()
        kwargs: dict[str, Any] = {}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.inventory.sites.all(**kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("sites"))


def get_interfaces(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return interface inventory."""
    if settings.is_live:
        ipf = _get_client()
        columns = [
            "hostname", "intName", "siteName", "l1", "l2",
            "reason", "mac", "dscr", "speed", "duplex",
        ]
        kwargs: dict[str, Any] = {"columns": columns}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.inventory.interfaces.all(**kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("interfaces"))


def get_os_versions(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return OS version consistency data."""
    if settings.is_live:
        ipf = _get_client()
        kwargs: dict[str, Any] = {}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.inventory.os_version_consistency.all(**kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("os_versions"))


def get_eol_summary(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return end-of-life summary."""
    if settings.is_live:
        ipf = _get_client()
        kwargs: dict[str, Any] = {}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.inventory.eol_summary.all(**kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("eol_summary"))


def get_bgp_neighbors(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return BGP neighbors table."""
    if settings.is_live:
        ipf = _get_client()
        columns = [
            "hostname", "localAs", "srcInt", "srcIp",
            "neiAddress", "neiAs", "state", "siteName", "vrf",
        ]
        kwargs: dict[str, Any] = {"columns": columns}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        try:
            rows = ipf.technology.routing.bgp_neighbors.all(**kwargs)
        except Exception:
            rows = ipf.fetch_all("tables/routing/protocols/bgp/neighbors", **kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("bgp_neighbors"))


def get_part_numbers(snapshot_id: str | None = None) -> pd.DataFrame:
    """Return hardware part numbers (for EoL/EoS analysis)."""
    if settings.is_live:
        ipf = _get_client()
        kwargs: dict[str, Any] = {}
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.inventory.pn.all(**kwargs)
        return pd.DataFrame(rows)

    return pd.DataFrame(_load_demo("part_numbers"))


def fetch_table(url: str, snapshot_id: str | None = None, **kwargs) -> pd.DataFrame:
    """Generic fetch for any IP Fabric table by API path."""
    if settings.is_live:
        ipf = _get_client()
        if snapshot_id:
            kwargs["snapshot_id"] = snapshot_id
        rows = ipf.fetch_all(url, **kwargs)
        return pd.DataFrame(rows)

    # In demo mode, derive a filename from the url
    slug = url.strip("/").replace("/", "_")
    return pd.DataFrame(_load_demo(slug))
