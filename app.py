"""
Discovery Insight Engine — Streamlit app

Reads one IP Fabric snapshot (live via the Python SDK, or a recorded export of a live snapshot)
and turns its discovery data into product and triage insight for a Network Discovery PM.

Built by Ranaji Deb as a proof of concept for the Senior Product Manager – Network Discovery role at IP Fabric.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import settings
from src import data, insights, compare

importlib.reload(data)
importlib.reload(insights)
importlib.reload(compare)

st.set_page_config(
    page_title="Discovery Insight Engine — Ranaji Deb",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sample inputs for the two drafting tools (clearly labelled as samples)
# ---------------------------------------------------------------------------
SAMPLE_VENDOR_INPUTS = {
    "Sample: Arista EOS 4.31 BGP EVPN output": {
        "vendor": "Arista", "os": "EOS 4.31",
        "input": (
            "switch# show bgp evpn route-type ip-prefix ipv4 detail\n"
            "BGP routing table information for VRF default\n"
            "Router identifier 10.50.2.1, local AS number 65001\n"
            "Route Distinguisher: 10.50.2.1:100\n"
            " Prefix: [5]:[0]:[24]:[10.100.1.0]/120\n"
            "  Paths: 2 available\n"
            "   Path 1: via 10.50.1.1, ESI: 00:00:00:00:00:00:00:00:01:00\n"
            "    VNI: 10010, Route Target: 65001:10010, Encapsulation: VXLAN\n"
            "    Status: Valid, Active, Best"
        ),
    },
    "Sample: Palo Alto PAN-OS 11.1 security rule": {
        "vendor": "Palo Alto", "os": "PAN-OS 11.1",
        "input": (
            "admin@pa-5260> show running security-policy rule-name Corporate-Trust-Rule\n"
            "rule Corporate-Trust-Rule {\n    from [ trust-internal trust-dmz ];\n    to [ untrust-wan ];\n"
            "    source [ dag-corp-endpoints 10.0.0.0/8 ];\n    destination any;\n"
            "    service [ application-default service-https ];\n    action allow;\n}"
        ),
    },
    "Custom input": {"vendor": "", "os": "", "input": ""},
}

SAMPLE_PM_INPUTS = {
    "Sample request (fictional): Catalyst 9800 WLC + Meraki stitching": (
        "Fictional enterprise request: \"We are moving from AireOS 5520 controllers to Catalyst 9800-CL and rolling out "
        "Meraki MR access points across 600 stores. We need AP-to-switch CDP/LLDP neighbours stitched into the campus "
        "topology without a separate Meraki API key per store. If discovery takes more than 15 minutes, NetOps cannot "
        "use it during change windows.\""
    ),
    "Sample request (fictional): legacy Enterasys switches": (
        "Fictional escalation: \"Our plant runs 140 Enterasys SecureStack switches on firmware 6.81. Discovery fails "
        "because they only answer SNMPv1 and drop SSH after 2 commands. We need VLAN and MAC tables or we will not renew.\""
    ),
    "Custom input": "",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
for key, default in [
    ("health_assessment", None), ("health_history", []),
    ("triage_assessment", None), ("triage_history", []),
    ("vendor_parser_output", None), ("vendor_history", []),
    ("pm_spec_output", None), ("pm_history", []),
    ("chat_messages", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


@st.cache_data(ttl=900, show_spinner="Reading snapshot tables from IP Fabric…")
def _cached_bundle(mode: str, snapshot_id: str) -> dict:
    return data.load_bundle(snapshot_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_snapshots(mode: str) -> list[dict]:
    return data.list_snapshots()


def _run_llm(fn, *args, fallback=None):
    """Call an insight function. On failure show the error and, if given, a labelled rule-based summary."""
    try:
        return fn(*args), None
    except insights.LLMError as e:
        return (fallback() if fallback else None), str(e)


def _fmt_duration(sec):
    if not sec:
        return "n/a"
    m, s = divmod(int(sec), 60)
    return f"{m}m {s:02d}s"


# ---------------------------------------------------------------------------
# Sidebar: author, data source, snapshot
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔍 Discovery Insight Engine")
    st.caption("Discovery coverage, connectivity triage and vendor-support signals from an IP Fabric snapshot.")
    st.divider()
    st.markdown("**Built by:** Ranaji Deb")
    st.caption("Proof of concept for IP Fabric's Senior Product Manager – Network Discovery application")
    st.divider()

    source_error = None
    snapshots: list[dict] = []
    try:
        snapshots = _cached_snapshots(settings.data_mode)
    except data.DataSourceError as e:
        source_error = str(e)
    except Exception as e:  # unexpected SDK/API error
        source_error = f"{type(e).__name__}: {e}"

    if settings.is_live and not source_error:
        st.markdown("**Data source:** 🟢 Live IP Fabric")
        st.caption(f"`{settings.ipf_url}`" + (f" · v{data.ipf_version()}" if data.ipf_version() else ""))
    elif settings.is_live:
        st.markdown("**Data source:** 🔴 Live connection failed")
    else:
        st.markdown("**Data source:** 🟡 Recorded export")
        st.caption("Real IP Fabric demo-snapshot data, recorded from a live instance. Not a live connection.")

    st.markdown(f"**LLM:** {'✅ ' + settings.openrouter_model if settings.has_llm else '⚠️ not configured'}")
    st.divider()

    snap_labels = [f"{s['name']} ({s.get('device_count', '?')} devices)" for s in snapshots]
    sel_idx = st.selectbox("Snapshot", range(len(snapshots)), format_func=lambda i: snap_labels[i],
                           disabled=not snapshots) if snapshots else None
    selected = snapshots[sel_idx] if snapshots and sel_idx is not None else None

    if st.button("🔄 Re-read from IP Fabric", disabled=not settings.is_live):
        st.cache_data.clear()
        data.reset_client()
        st.rerun()

# ---------------------------------------------------------------------------
# Load the bundle (explicit errors, no silent fallback)
# ---------------------------------------------------------------------------
if source_error or selected is None:
    st.error(f"**Could not read discovery data.** {source_error or 'No snapshot selected.'}")
    if settings.is_live:
        st.info("Check IPF_URL / IPF_TOKEN in `.env`, that the appliance is running, and that a snapshot is loaded. "
                "To view the recorded export instead, set `DATA_MODE=recorded`.")
    st.stop()

try:
    bundle = _cached_bundle(settings.data_mode, selected["id"])
except Exception as e:
    st.error(f"**Could not read snapshot `{selected['name']}`.** {type(e).__name__}: {e}")
    st.stop()

meta = bundle["meta"]
ctx = data.llm_context(bundle)
cov = data.coverage(bundle)
tsum = data.task_summary(bundle)
acc = data.access_summary(bundle)
devices_df = pd.DataFrame(bundle["devices"])

with st.sidebar:
    if settings.is_live:
        if st.button("💾 Record this snapshot for the hosted app"):
            path = data.record_bundle(bundle)
            st.success(f"Saved {path.relative_to(data.ROOT)}")
    st.divider()
    st.caption("Every number in this app is read from IP Fabric tables for the selected snapshot, "
               "except the clearly marked illustrative backlog in the Vendor tab.")

if meta["source"] == "live":
    st.success(f"**Live data** · snapshot **{meta['name']}** · taken {meta['start'][:16].replace('T', ' ')} UTC · "
               f"read {meta['read_at'][:19].replace('T', ' ')} UTC from `{settings.ipf_url}`", icon="🟢")
else:
    st.info(f"**Recorded export** of IP Fabric snapshot **{meta['name']}** (taken {meta['start'][:10]}), "
            f"recorded {meta.get('recorded_at', '')[:10]} from a live IP Fabric instance. "
            "This hosted version cannot reach the appliance, so it reads the export.", icon="🟡")

tab_health, tab_triage, tab_vendor, tab_copilot, tab_ask = st.tabs([
    "🏥 Discovery Health", "🔍 Connectivity Triage", "🧩 Vendor & Platform Support",
    "🛠️ PM Copilot", "💬 Assistant",
])

# ===========================================================================
# TAB 1: DISCOVERY HEALTH
# ===========================================================================
with tab_health:
    st.header("Discovery Health")
    st.caption("How complete is this snapshot as the basis for IP Fabric's network model?")

    failed_conn = len(tsum["failures"])
    attempted = tsum["total_tasks"] - tsum["by_category"].get("Outside discovery scope", 0)

    k = st.columns(6)
    k[0].metric("Devices in model", meta["device_count"])
    for i, dom in enumerate(["l2", "l3", "sec"], start=1):
        c = cov[dom]
        k[i].metric(c["label"], f"{c['rate']}%" if c["rate"] is not None else "n/a",
                    help=f"{c['present']} of {c['applicable']} devices. Rule: {c['rule']}")
    k[4].metric("Possible gaps / failed", f"{tsum['failures_not_in_model']} / {failed_conn}",
                help=f"Connectivity report rows with authentication failure, timeout or refusal. "
                     f"{tsum['failures_on_discovered_devices']} of them are interfaces of devices already discovered via another IP.")
    k[5].metric("Discovery issues", len(bundle["discovery_errors"]), help="Rows in IP Fabric's Discovery Issues report (command/parse problems on reached devices).")

    with st.popover("ℹ️ How these numbers are measured"):
        st.markdown("**Coverage rules** (share of applicable devices with at least one row in the named tables):")
        for c in cov.values():
            st.markdown(f"- **{c['label']}:** {c['rule']}")
        st.markdown("**Failed connections:** rows in *Discovery Connectivity Report* (`tables/reports/discovery-tasks`) "
                    "classified from `errorType` and the error messages.")
        st.markdown("**Discovery issues:** `tables/reports/discovery-errors`.")
        st.markdown("Row counts per device come from the technology tables listed in `src/data.py` (TECH_TABLES).")

    st.divider()
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("How addresses were found, and what happened to them")
        mat = pd.DataFrame(tsum["source_outcome_matrix"]).fillna(0).T
        if not mat.empty:
            long = mat.reset_index().melt(id_vars="index", var_name="Outcome", value_name="Addresses")
            long = long[long["Addresses"] > 0].rename(columns={"index": "Discovery source"})
            fig = px.bar(long, x="Discovery source", y="Addresses", color="Outcome", text="Addresses",
                         color_discrete_map={"Discovered": "#2e7d32", "Duplicate path (already queued)": "#9e9e9e",
                                             "Outside discovery scope": "#90caf9", "Connection timed out": "#ef6c00",
                                             "Connection refused": "#c62828", "Authentication failed": "#6a1b9a"})
            fig.update_layout(height=360, margin=dict(t=10, b=10), legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig, width="stretch")
        st.caption(f"Seeds configured: {', '.join(tsum['seeds']) or 'none'} · "
                   f"Discovery-history seeding: {'on' if bundle['settings'].get('discovery_history_seeds') else 'off'} · "
                   f"Task sources enabled: {', '.join(bundle['settings'].get('task_sources', []))}")
    with c2:
        st.subheader("Management access used")
        la = pd.DataFrame([{"Access": k_, "Devices": v} for k_, v in acc["by_login_type"].items()])
        fig2 = px.pie(la, names="Access", values="Devices", hole=0.45)
        fig2.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig2, width="stretch")
        if acc["telnet_devices"]:
            st.warning(f"{len(acc['telnet_devices'])} devices were collected over **Telnet** "
                       f"(allowTelnet = {acc['allow_telnet']}).")
        st.caption(f"Credential sets configured: {acc['credential_sets']} · authentication failures: {acc['auth_failures']}")

    st.subheader("Run metrics")
    r = bundle["run"]
    m = st.columns(5)
    m[0].metric("Snapshot duration", _fmt_duration(meta["duration_sec"]))
    m[1].metric("Addresses processed", tsum["total_tasks"], help="All rows in the connectivity report, including out-of-scope.")
    m[2].metric("Connection attempts", tsum["total_attempts"])
    m[3].metric("Links in topology", r.get("connectionCount") or "n/a")
    m[4].metric("Managed IPs", r.get("managedIpCount") or "n/a")

    sites = pd.DataFrame(data.site_summary(bundle))
    with st.expander(f"Sites ({len(sites)})", expanded=False):
        if (sites["site"] == "unknown").any():
            st.warning("Some devices have no site assigned: site separation rules do not cover them.")
        st.dataframe(sites, width="stretch", hide_index=True)

    missing_rows = [dict(m_, domain=cov[d]["label"]) for d in cov for m_ in cov[d]["missing"]]
    if missing_rows:
        st.subheader("Applicable devices with no data in a domain")
        st.dataframe(pd.DataFrame(missing_rows), width="stretch", hide_index=True)

    st.divider()
    h1, h2 = st.columns([3.5, 1.5])
    h1.subheader("🤖 AI assessment of this snapshot")
    with h2.popover("ℹ️ What the model sees"):
        st.markdown(f"- Model: `{settings.openrouter_model}`, temperature 0.2")
        st.markdown("- Input: the JSON below, built only from this snapshot's IP Fabric tables")
        st.markdown("- The prompt forbids inventing devices, IPs or numbers")
        st.json(ctx, expanded=False)

    if st.button("Generate assessment", type="primary", key="btn_health"):
        with st.spinner("Assessing snapshot…"):
            text, err = _run_llm(insights.assess_discovery_health, ctx, fallback=lambda: insights.rule_based_health(ctx))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["health_assessment"] = {"text": text, "error": err, "timestamp": ts, "snapshot": meta["name"]}
        st.session_state["health_history"].append(st.session_state["health_assessment"])

    ha = st.session_state["health_assessment"]
    if ha:
        if ha["error"]:
            st.error(f"LLM call failed: {ha['error']}. Showing a rule-based summary of the same data instead.")
        st.caption(f"Generated {ha['timestamp']} for snapshot **{ha['snapshot']}**")
        st.markdown(ha["text"])
        st.download_button("📥 Download assessment (.md)",
                           data=f"# Discovery assessment — {ha['snapshot']}\n\n{ha['text']}",
                           file_name=f"Discovery_Assessment_{ha['snapshot'].replace(' ', '_')}.md", key="dl_health")

    st.divider()
    with st.expander("🔁 Compare with another snapshot"):
        others = [s for s in snapshots if s["id"] != selected["id"]]
        if not others:
            st.caption("Only one snapshot available.")
        else:
            base_i = st.selectbox("Baseline snapshot", range(len(others)), format_func=lambda i: others[i]["name"], key="cmp_base")
            try:
                base = _cached_bundle(settings.data_mode, others[base_i]["id"])
                diff = compare.compare_bundles(base, bundle)
                cc = st.columns(3)
                cc[0].metric("Devices", diff["device_count"][1], delta=diff["device_count"][1] - diff["device_count"][0])
                cc[1].metric("New connection failures", len(diff["new_failures"]))
                cc[2].metric("Resolved failures", len(diff["resolved_failures"]))
                if diff["added"]:
                    st.markdown(f"**Devices only in {diff['current']}**")
                    st.dataframe(pd.DataFrame(diff["added"]), width="stretch", hide_index=True)
                if diff["removed"]:
                    st.markdown(f"**Devices only in {diff['baseline']}**")
                    st.dataframe(pd.DataFrame(diff["removed"]), width="stretch", hide_index=True)
                st.dataframe(pd.DataFrame(diff["task_categories"]), width="stretch", hide_index=True)
            except Exception as e:
                st.error(f"Could not read baseline snapshot: {e}")

    st.subheader("📋 Device explorer")
    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.3, 1.6])
    sel_vendor = f1.multiselect("Vendor", sorted(devices_df["vendor"].dropna().unique()))
    sel_site = f2.multiselect("Site", sorted(devices_df["siteName"].fillna("unknown").unique()))
    sel_type = f3.multiselect("Device type", sorted(devices_df["devType"].dropna().unique()))
    search = f4.text_input("Search hostname / IP / platform")
    gaps_only = st.checkbox("Only devices with discovery issues or missing domain data")
    df = devices_df.copy()
    if sel_vendor:
        df = df[df["vendor"].isin(sel_vendor)]
    if sel_site:
        df = df[df["siteName"].fillna("unknown").isin(sel_site)]
    if sel_type:
        df = df[df["devType"].isin(sel_type)]
    if search:
        s = search.lower()
        df = df[df.apply(lambda r: s in " ".join(str(r.get(c, "")) for c in ["hostname", "loginIp", "platform", "family", "version"]).lower(), axis=1)]
    if gaps_only:
        missing_hosts = {m_["hostname"] for d in cov.values() for m_ in d["missing"]}
        df = df[(df["discovery_issues"] > 0) | (df["hostname"].isin(missing_hosts))]
    cols = ["hostname", "siteName", "vendor", "family", "platform", "version", "devType", "loginType", "loginIp",
            "discovery_source", "vlans", "mac_entries", "stp_instances", "routes", "arp_entries", "vrf_interfaces",
            "ospf_neighbors", "bgp_neighbors", "acl_rules", "zone_fw_policies", "aaa_servers", "discovery_issues"]
    st.caption(f"{len(df)} of {len(devices_df)} devices · columns after `loginIp` are row counts in each IP Fabric table")
    st.dataframe(df[[c for c in cols if c in df.columns]], width="stretch", hide_index=True, height=360)

# ===========================================================================
# TAB 2: CONNECTIVITY TRIAGE
# ===========================================================================
with tab_triage:
    st.header("Connectivity Triage")
    st.caption("From IP Fabric's Discovery Connectivity Report and Discovery Issues for this snapshot.")

    cats = tsum["by_category"]
    t = st.columns(6)
    t[5].metric("Found, not attempted", cats.get("Found, not attempted", 0))
    t[0].metric("Discovered", cats.get("Discovered", 0))
    t[1].metric("Timed out", cats.get("Connection timed out", 0))
    t[2].metric("Refused", cats.get("Connection refused", 0))
    t[3].metric("Auth failed", cats.get("Authentication failed", 0))
    t[4].metric("Outside scope", cats.get("Outside discovery scope", 0))

    failures = tsum["failures"]
    st.subheader(f"Failed addresses ({len(failures)})")
    st.caption(f"{tsum['failures_not_in_model']} are not in the model (possible coverage gaps). "
               f"{tsum['failures_on_discovered_devices']} are extra interfaces of devices already discovered through another IP "
               "(matched against `tables/addressing/managed-devs`).")
    only_gaps = st.checkbox("Only addresses not in the model", value=False)
    fc1, fc2 = st.columns(2)
    sel_cat = fc1.multiselect("Category", sorted({f["category"] for f in failures}))
    sel_src = fc2.multiselect("Found via", sorted({data.SOURCE_LABELS.get(f["source"], f["source"]) for f in failures}))
    shown = [f for f in failures if (not only_gaps or not f.get("owned_by")) and (not sel_cat or f["category"] in sel_cat)
             and (not sel_src or data.SOURCE_LABELS.get(f["source"], f["source"]) in sel_src)]

    fail_df = pd.DataFrame([{
        "IP": f["ip"], "DNS name": f["dnsName"], "Category": f["category"],
        "Already in model as": f.get("owned_by") or "—",
        "Found via": data.SOURCE_LABELS.get(f["source"], f["source"]), "Attempts": f["attempts"],
        "Last error": f["reasons"][-1]["msg"] if f["reasons"] else "",
    } for f in shown])
    if not fail_df.empty:
        st.dataframe(fail_df, width="stretch", hide_index=True, height=280)

    for f in shown[:15]:
        with st.expander(f"`{f['ip']}` — {f['category']} (found via {data.SOURCE_LABELS.get(f['source'], f['source'])}, {f['attempts']} attempts)"):
            if f.get("owned_by"):
                st.markdown(f"**Not a gap:** {data.OWNED_NOTE.format(owner=f['owned_by'])}")
            else:
                st.markdown(f"**Next check:** {data.NEXT_CHECK.get(f['category'], 'Inspect the task log in IP Fabric.')}")
            st.code("\n".join(f"{r['ts'][:19] if r['ts'] else ''}  [{r['protocol']}]  {r['msg']}" for r in f["reasons"]) or "(no error detail)", language="text")
    if len(shown) > 15:
        st.caption(f"Showing details for 15 of {len(shown)}; all are in the table above.")

    if failures:
        ticket = "# Discovery connectivity follow-up — " + meta["name"] + "\n\n" + "\n".join(
            f"- [ ] `{f['ip']}` — {f['category']} (via {f['source']}): {f['reasons'][-1]['msg'] if f['reasons'] else ''}\n"
            f"      " + (f"Already in model as {f['owned_by']} (not a gap)" if f.get('owned_by') else f"Next check: {data.NEXT_CHECK.get(f['category'], '')}")
            for f in failures)
        st.download_button("📥 Download follow-up checklist (.md)", data=ticket,
                           file_name=f"Discovery_Followup_{meta['name'].replace(' ', '_')}.md", key="dl_ticket")

    st.divider()
    st.subheader(f"Discovery issues on reached devices ({len(bundle['discovery_errors'])})")
    st.caption("Command or parsing problems IP Fabric recorded while collecting from devices it did reach.")
    if bundle["discovery_errors"]:
        st.dataframe(pd.DataFrame(bundle["discovery_errors"]), width="stretch", hide_index=True)
    else:
        st.caption("None in this snapshot.")
    if meta.get("snapshot_errors"):
        st.caption("Snapshot error counters: " + ", ".join(f"{e['type']}: {e['count']}" for e in meta["snapshot_errors"]))

    st.divider()
    st.subheader("Discovery boundary")
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**Learned addresses outside the include list** (grouped by /16)")
        oos = pd.DataFrame(data.out_of_scope_ranges(bundle))
        st.dataframe(oos, width="stretch", hide_index=True, height=240)
        st.caption("Include list: " + ", ".join(bundle["settings"].get("include_networks", [])) +
                   (" · Exclude: " + ", ".join(bundle["settings"]["exclude_networks"]) if bundle["settings"].get("exclude_networks") else ""))
    with b2:
        st.markdown("**Protocol neighbours that are not managed devices**")
        um = pd.DataFrame(bundle["unmanaged_protocol_neighbors"])
        st.dataframe(um, width="stretch", hide_index=True, height=240)
        if bundle["unmanaged_cdp_lldp_neighbors"]:
            st.markdown("**CDP/LLDP neighbours not discovered**")
            st.dataframe(pd.DataFrame(bundle["unmanaged_cdp_lldp_neighbors"]), width="stretch", hide_index=True)
        else:
            st.caption("No unmanaged CDP/LLDP neighbours in this snapshot.")

    st.divider()
    st.subheader("🤖 AI triage")
    triage_ctx = {k: ctx[k] for k in ["data_provenance", "discovery_settings", "discovery_tasks", "failed_tasks",
                                      "discovery_errors", "out_of_scope_ranges", "unmanaged_protocol_neighbors_total", "unmanaged_protocol_neighbors_sample",
                                      "unmanaged_cdp_lldp_neighbors", "access"]}
    if st.button("Generate triage", type="primary", key="btn_triage"):
        with st.spinner("Clustering failures…"):
            text, err = _run_llm(insights.diagnose_discovery_failures, triage_ctx, fallback=lambda: insights.rule_based_triage(ctx))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["triage_assessment"] = {"text": text, "error": err, "timestamp": ts, "snapshot": meta["name"]}
        st.session_state["triage_history"].append(st.session_state["triage_assessment"])
    ta = st.session_state["triage_assessment"]
    if ta:
        if ta["error"]:
            st.error(f"LLM call failed: {ta['error']}. Showing a rule-based summary instead.")
        st.caption(f"Generated {ta['timestamp']} for snapshot **{ta['snapshot']}**")
        st.markdown(ta["text"])
        st.download_button("📥 Download triage (.md)", data=ta["text"],
                           file_name=f"Discovery_Triage_{ta['snapshot'].replace(' ', '_')}.md", key="dl_triage")

# ===========================================================================
# TAB 3: VENDOR & PLATFORM SUPPORT
# ===========================================================================
with tab_vendor:
    st.header("Vendor & Platform Support")
    st.caption("What this snapshot says about platform coverage, plus a drafting tool for new vendor support.")

    st.subheader("1. Platforms in this snapshot")
    st.dataframe(pd.DataFrame(data.platform_matrix(bundle)), width="stretch", hide_index=True)
    api_devs = devices_df[devices_df["loginType"] == "api"]
    if not api_devs.empty:
        st.info(f"**{len(api_devs)} devices were discovered through vendor APIs** "
                f"({', '.join(sorted(api_devs['vendor'].unique()))}), not CLI. Cloud and controller discovery "
                "is a growing share of the Network Discovery surface.")

    st.markdown("**Discovery issues by platform**")
    de = pd.DataFrame(bundle["discovery_errors"])
    if not de.empty:
        st.dataframe(de[["hostname", "loginIp", "loginType", "version", "taskId", "errorType", "errorText"]],
                     width="stretch", hide_index=True)
    else:
        st.caption("None in this snapshot.")
    cloud_noise = [f for f in tsum["failures"] if f.get("owned_by") and any(
        d["hostname"] == f["owned_by"].split(" ")[0] and d.get("loginType") == "api" for d in bundle["devices"])]
    if cloud_noise:
        st.warning(f"{len(cloud_noise)} failed CLI connection attempts targeted IPs of objects IP Fabric had already "
                   "discovered through a cloud API: " + ", ".join(f"`{f['ip']}` ({f['owned_by']})" for f in cloud_noise)
                   + ". API-discovered objects could be excluded from CLI attempts.")

    with st.expander("📐 Vendor-support scoring model (illustrative, not IP Fabric data)"):
        st.markdown("How I would rank vendor/OS support requests. Weights are a starting hypothesis to validate "
                    "with Field and Engineering, not a finished model.")
        st.latex(r"\text{Priority} = 0.40\,\text{Reach} + 0.30\,\text{Model impact} + 0.20\,\text{Collection stability} + 0.10\,\text{Customer requests}")
        bl = data.illustrative_backlog()
        if bl:
            bdf = pd.DataFrame(bl)
            bdf["priority"] = (0.4 * bdf["reach"] + 0.3 * bdf["model_impact"] + 0.2 * bdf["stability"] + 0.1 * bdf["requests"]).round(1)
            st.dataframe(bdf.sort_values("priority", ascending=False), width="stretch", hide_index=True)
            st.caption("Scores 1–10 are illustrative placeholders. In the role they would come from CRM, support tickets and install-base data.")

    st.divider()
    st.subheader("2. Draft vendor support scope (AI)")
    st.caption("Drafts commands, a parsing approach and test fixtures for engineers to review. "
               "Discovery at runtime stays deterministic; AI only helps at development time.")

    live_presets = {}
    for e in bundle["discovery_errors"]:
        label = f"From this snapshot: {e['errorType']} on {e['hostname'] or e['loginIp']} ({e['version']})"
        live_presets[label] = {
            "vendor": (e["version"] or "").split(" ")[0].title(), "os": e["version"] or "",
            "input": (f"Discovery issue recorded by IP Fabric in snapshot '{meta['name']}':\n"
                      f"device: {e['hostname']} ({e['loginIp']}), access: {e['loginType']}\n"
                      f"task / command group: {e['taskId']}\nerror type: {e['errorType']}\nerror text: {e['errorText']}\n\n"
                      "Question: what does this mean for the data collected from this device, and how should the "
                      "parser handle it?"),
        }
    presets = {**live_presets, **SAMPLE_VENDOR_INPUTS}

    def _apply_vendor_preset():
        p = presets[st.session_state["vendor_preset"]]
        st.session_state["vi_vendor"], st.session_state["vi_os"], st.session_state["vi_raw"] = p["vendor"], p["os"], p["input"]

    if ("vendor_preset" not in st.session_state or st.session_state["vendor_preset"] not in presets
            or st.session_state.get("vendor_preset_snap") != meta["snapshot_id"]):
        if st.session_state.get("vendor_preset") not in presets:
            st.session_state["vendor_preset"] = list(presets)[0]
        st.session_state["vendor_preset_snap"] = meta["snapshot_id"]
        _apply_vendor_preset()
    st.selectbox("Input", list(presets), key="vendor_preset", on_change=_apply_vendor_preset)
    vc1, vc2 = st.columns(2)
    vc1.text_input("Vendor", key="vi_vendor")
    vc2.text_input("OS / version", key="vi_os")
    st.text_area("Vendor documentation, CLI output or discovery issue", height=200, key="vi_raw")
    if st.button("Draft support scope", type="primary", key="btn_vendor"):
        if not st.session_state["vi_raw"].strip():
            st.warning("Enter some input first.")
        else:
            with st.spinner("Drafting…"):
                text, err = _run_llm(insights.generate_vendor_parser, st.session_state["vi_vendor"],
                                     st.session_state["vi_os"], st.session_state["vi_raw"])
            st.session_state["vendor_parser_output"] = {"text": text, "error": err,
                                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                        "vendor": st.session_state["vi_vendor"], "os": st.session_state["vi_os"]}
    vp = st.session_state["vendor_parser_output"]
    if vp:
        if vp["error"]:
            st.error(f"LLM call failed: {vp['error']}")
        else:
            st.caption(f"Draft generated {vp['timestamp']} for {vp['vendor']} {vp['os']} — review before use")
            st.markdown(vp["text"])
            st.download_button("📥 Download draft (.md)", data=vp["text"], file_name="Vendor_Support_Draft.md", key="dl_vendor")

# ===========================================================================
# TAB 4: PM COPILOT
# ===========================================================================
with tab_copilot:
    st.header("PM Copilot")
    st.caption("Turn a raw request into a scoped epic, and keep roadmap themes tied to evidence.")

    st.subheader("Evidence log from this snapshot")
    st.caption("Each theme links to what the data shows. Customer interviews and field input would be added next to it.")
    n_timeout = cats.get("Connection timed out", 0)
    n_refused = cats.get("Connection refused", 0)
    n_auth = cats.get("Authentication failed", 0)
    n_oos = cats.get("Outside discovery scope", 0)
    n_dup = cats.get("Duplicate path (already queued)", 0)
    evidence = [
        {"Theme": "Explain why an address was not discovered",
         "Evidence in this snapshot": f"{n_timeout} timeouts, {n_refused} refusals, {n_auth} auth failures; each needs a different fix and owner.",
         "Source": "Discovery Connectivity Report"},
        {"Theme": "Suggest scope changes from learned addresses",
         "Evidence in this snapshot": f"{n_oos} addresses learned but outside the include list, grouped into {len(data.out_of_scope_ranges(bundle))} /16 ranges.",
         "Source": "Discovery Connectivity Report + snapshot settings"},
        {"Theme": "Management access hygiene",
         "Evidence in this snapshot": f"{len(acc['telnet_devices'])} of {len(devices_df)} devices collected over Telnet.",
         "Source": "Device Inventory (loginType)"},
        {"Theme": "Cloud and API discovery",
         "Evidence in this snapshot": f"{len(api_devs)} devices discovered via vendor API; {len(bundle['unmanaged_protocol_neighbors'])} protocol neighbours not managed.",
         "Source": "Device Inventory + unmanaged neighbours; IP Fabric 8.0/8.1 release notes"},
        {"Theme": "Parser resilience to vendor bugs",
         "Evidence in this snapshot": "; ".join(f"{e['hostname'] or e['loginIp']}: {e['errorText']}" for e in bundle["discovery_errors"]) or "No discovery issues in this snapshot.",
         "Source": "Discovery Issues report"},
        {"Theme": "Separate real gaps from redundant attempts",
         "Evidence in this snapshot": f"{tsum['failures_on_discovered_devices']} of {len(failures)} failed addresses belong to devices already discovered via another IP.",
         "Source": "Connectivity Report joined with Managed IPs table"},
        {"Theme": "Queue efficiency",
         "Evidence in this snapshot": f"{n_dup} of {tsum['total_tasks']} addresses were duplicates already in the queue.",
         "Source": "Discovery Connectivity Report"},
    ]
    st.dataframe(pd.DataFrame(evidence), width="stretch", hide_index=True)

    st.divider()
    st.subheader("Draft an epic from a raw request (AI)")

    def _apply_pm_preset():
        st.session_state["pm_raw"] = SAMPLE_PM_INPUTS[st.session_state["pm_preset"]]

    if "pm_preset" not in st.session_state:
        st.session_state["pm_preset"] = list(SAMPLE_PM_INPUTS)[0]
        _apply_pm_preset()
    st.selectbox("Input", list(SAMPLE_PM_INPUTS), key="pm_preset", on_change=_apply_pm_preset)
    st.text_area("Customer request, escalation or vendor API note", height=160, key="pm_raw")
    if st.button("Draft epic", type="primary", key="btn_pm"):
        if not st.session_state["pm_raw"].strip():
            st.warning("Enter some input first.")
        else:
            with st.spinner("Drafting…"):
                text, err = _run_llm(insights.synthesize_pm_spec, st.session_state["pm_raw"])
            st.session_state["pm_spec_output"] = {"text": text, "error": err,
                                                  "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                  "source": st.session_state["pm_preset"]}
    ps = st.session_state["pm_spec_output"]
    if ps:
        if ps["error"]:
            st.error(f"LLM call failed: {ps['error']}")
        else:
            st.caption(f"Draft generated {ps['timestamp']} from *{ps['source']}*")
            st.markdown(ps["text"])
            st.download_button("📥 Download epic (.md)", data=ps["text"], file_name="Discovery_Epic_Draft.md", key="dl_pm")

# ===========================================================================
# TAB 5: ASSISTANT
# ===========================================================================
with tab_ask:
    a1, a2 = st.columns([4, 1])
    a1.header("Assistant")
    a1.caption("Questions about this snapshot, answered only from its IP Fabric data. "
               "In production this would run on IP Fabric's MCP server instead of an export.")
    if a2.button("🗑️ Clear", key="clear_chat"):
        st.session_state["chat_messages"] = []
        st.rerun()

    suggestions = []
    gaps = [f for f in failures if not f.get("owned_by")]
    if gaps:
        suggestions.append(f"Why was {gaps[0]['ip']} not discovered, and what should be checked first?")
    if len(gaps) != len(failures):
        suggestions.append("Which failed addresses are real coverage gaps, and which are already in the model?")
    if bundle["discovery_errors"]:
        e0 = bundle["discovery_errors"][0]
        suggestions.append(f"What does the {e0['errorType']} on {e0['hostname'] or e0['loginIp']} mean for its data?")
    suggestions += ["Which include-list changes would you consider, and what is the risk of each?",
                    "Is this snapshot complete enough for path analysis? Answer with evidence."]
    chosen = None
    sc = st.columns(2)
    for i, q in enumerate(suggestions):
        if sc[i % 2].button(q, key=f"sugg_{i}"):
            chosen = q

    user_q = st.chat_input("Ask about this snapshot")
    prompt = user_q or chosen

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt:
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Reading the snapshot data…"):
                history = [{"role": m_["role"], "content": m_["content"]} for m_ in st.session_state["chat_messages"]]
                reply, err = _run_llm(insights.answer_conversation, history, ctx)
                if err:
                    reply = f"⚠️ LLM call failed: {err}"
            st.markdown(reply)
        st.session_state["chat_messages"].append({"role": "assistant", "content": reply})

st.divider()
st.caption("Discovery Insight Engine — proof of concept by Ranaji Deb for IP Fabric's Senior Product Manager – "
           "Network Discovery application. Reads IP Fabric data through the public Python SDK; not an IP Fabric product.")
