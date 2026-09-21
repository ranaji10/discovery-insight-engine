"""Compare two snapshot bundles (see data.load_bundle): what discovery found differently between runs."""

from __future__ import annotations

from collections import Counter

from src import data


def compare_bundles(a: dict, b: dict) -> dict:
    """a = baseline, b = current."""
    da = {d["sn"]: d for d in a["devices"]}
    db = {d["sn"]: d for d in b["devices"]}
    added = [db[s] for s in db.keys() - da.keys()]
    removed = [da[s] for s in da.keys() - db.keys()]

    cov_a, cov_b = data.coverage(a), data.coverage(b)
    cat_a = Counter(t["category"] for t in a["tasks"])
    cat_b = Counter(t["category"] for t in b["tasks"])
    cats = sorted(set(cat_a) | set(cat_b))

    failed_a = {t["ip"] for t in a["tasks"] if t["category"] in ("Authentication failed", "Connection timed out", "Connection refused")}
    failed_b = {t["ip"] for t in b["tasks"] if t["category"] in ("Authentication failed", "Connection timed out", "Connection refused")}

    return {
        "baseline": a["meta"]["name"],
        "current": b["meta"]["name"],
        "device_count": (len(da), len(db)),
        "added": [{"hostname": d["hostname"], "siteName": d["siteName"], "vendor": d["vendor"],
                   "platform": d.get("platform"), "loginType": d.get("loginType")} for d in added],
        "removed": [{"hostname": d["hostname"], "siteName": d["siteName"], "vendor": d["vendor"],
                     "platform": d.get("platform")} for d in removed],
        "coverage": {dom: (cov_a[dom]["rate"], cov_b[dom]["rate"]) for dom in cov_a},
        "task_categories": [{"category": c, "baseline": cat_a.get(c, 0), "current": cat_b.get(c, 0),
                             "change": cat_b.get(c, 0) - cat_a.get(c, 0)} for c in cats],
        "new_failures": sorted(failed_b - failed_a),
        "resolved_failures": sorted(failed_a - failed_b),
    }
