"""
Snapshot comparison — diff two IP Fabric snapshots to detect drift.

Produces structured diff data that the insight engine can interpret.
"""

from __future__ import annotations

import pandas as pd


def compare_device_inventories(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key: str = "hostname",
) -> dict:
    """
    Compare two device DataFrames and return a structured diff.

    Args:
        df_a: older snapshot devices
        df_b: newer snapshot devices
        key: column to use as device identity

    Returns:
        dict with added_devices, removed_devices, changed_devices, and stats
    """
    if df_a.empty and df_b.empty:
        return {"added_devices": [], "removed_devices": [], "changed_devices": [], "stats": {}}

    if key not in df_a.columns or key not in df_b.columns:
        return {"error": f"Key column '{key}' not found in one or both snapshots"}

    hosts_a = set(df_a[key].dropna().unique())
    hosts_b = set(df_b[key].dropna().unique())

    added = sorted(hosts_b - hosts_a)
    removed = sorted(hosts_a - hosts_b)
    common = hosts_a & hosts_b

    # Detect changes in common devices
    compare_cols = [c for c in ["vendor", "platform", "version", "siteName", "model"] if c in df_a.columns and c in df_b.columns]
    changed = []
    if compare_cols:
        for host in sorted(common):
            row_a = df_a[df_a[key] == host].iloc[0]
            row_b = df_b[df_b[key] == host].iloc[0]
            diffs = {}
            for col in compare_cols:
                va, vb = str(row_a.get(col, "")), str(row_b.get(col, ""))
                if va != vb:
                    diffs[col] = {"before": va, "after": vb}
            if diffs:
                changed.append({"hostname": host, "changes": diffs})

    # Vendor breakdown diff
    vendor_a = df_a["vendor"].value_counts().to_dict() if "vendor" in df_a.columns else {}
    vendor_b = df_b["vendor"].value_counts().to_dict() if "vendor" in df_b.columns else {}

    # Site breakdown diff
    site_a = df_a["siteName"].value_counts().to_dict() if "siteName" in df_a.columns else {}
    site_b = df_b["siteName"].value_counts().to_dict() if "siteName" in df_b.columns else {}

    return {
        "added_devices": added,
        "removed_devices": removed,
        "changed_devices": changed,
        "stats": {
            "total_a": len(hosts_a),
            "total_b": len(hosts_b),
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "net_change": len(hosts_b) - len(hosts_a),
        },
        "vendor_breakdown": {"before": vendor_a, "after": vendor_b},
        "site_breakdown": {"before": site_a, "after": site_b},
    }
