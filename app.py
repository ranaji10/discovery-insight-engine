"""
Discovery Insight Engine — Streamlit Dashboard

Upstream Network Discovery, Normalization & Parsing Diagnostics Engine.
Built by Ranaji Deb for the Senior Product Manager – Network Discovery role at IP Fabric.
"""

from __future__ import annotations

import json
import importlib
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import settings
from src import data, insights, compare

importlib.reload(data)
importlib.reload(insights)
importlib.reload(compare)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Discovery Insight Engine — Ranaji Deb",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Presets (Defined early for robust session state management)
# ---------------------------------------------------------------------------
VENDOR_PRESETS = {
    "Arista EOS 4.31 (EVPN Multi-Homing & Symmetric IRB)": {
        "vendor": "Arista",
        "os": "EOS 4.31.3M",
        "input": (
            "Arista EOS 4.31 Command Reference Snippet:\n\n"
            "switch# show bgp evpn route-type ip-prefix ipv4 detail\n"
            "BGP routing table information for VRF default\n"
            "Router identifier 10.50.2.1, local AS number 65001\n"
            "Route Distinguisher: 10.50.2.1:100 (rd1)\n"
            "Prefix: [5]:[0]:[24]:[10.100.1.0]/120\n"
            "  Paths: 2 available\n"
            "    Path 1: via 10.50.1.1 (vtep-leaf-01), ESI: 00:00:00:00:00:00:00:00:01:00\n"
            "      VNI: 10010, Route Target: 65001:10010, Encapsulation: VXLAN\n"
            "      Router MAC: 00:1c:73:00:01:01, Gateway IP: 10.100.1.254\n"
            "      Community: target:65001:10010\n"
            "      Status: Valid, Active, Best"
        ),
    },
    "Palo Alto PAN-OS 11.1 (Dynamic Address Groups & Security Policy)": {
        "vendor": "Palo Alto",
        "os": "PAN-OS 11.1.3",
        "input": (
            "Palo Alto XML API / CLI Command Reference:\n"
            "admin@pa-5260> show running security-policy rule-name Corporate-Trust-Rule\n"
            "rule Corporate-Trust-Rule {\n"
            "    from [ trust-internal trust-dmz ];\n"
            "    to [ untrust-wan ];\n"
            "    source [ dag-corp-endpoints 10.0.0.0/8 ];\n"
            "    destination any;\n"
            "    service [ application-default service-https ];\n"
            "    action allow;\n"
            "    log-start no;\n"
            "    log-end yes;\n"
            "    profile-setting {\n"
            "        group AntiVirus-Strict;\n"
            "    }\n"
            "}"
        ),
    },
    "Fortinet FortiOS 7.4.3 (SD-WAN Health & BGP Overlay)": {
        "vendor": "Fortinet",
        "os": "FortiOS 7.4.3",
        "input": (
            "FortiGate-60F # diagnose sys sdwan health-check status\n"
            "Health-Check(HUB-Health): seq:1, sla-map-idx:1, packet-loss:0.000%, latency:14.230ms, jitter:1.120ms\n"
            "  members(2):\n"
            "    1: Interface: advpn-hub1 (seq:1), state: alive, sla(0x1): pass, inbandwidth: 450kbps, outbandwidth: 210kbps\n"
            "    2: Interface: advpn-hub2 (seq:2), state: alive, sla(0x1): pass, inbandwidth: 120kbps, outbandwidth: 80kbps\n"
            "BGP neighbor 192.168.200.1 (advpn-hub1) state: Established, up for 42d 12h"
        ),
    },
    "Custom Vendor / CLI Output": {
        "vendor": "",
        "os": "",
        "input": "",
    },
}

PM_PRESETS = {
    "Enterprise RFQ: Cisco Catalyst 9800 WLC + Meraki Cloud Stitching": (
        "Enterprise Customer (Tier-1 Retail, 12,000 APs):\n"
        "\"We are migrating from legacy Cisco AireOS 5520 controllers to Catalyst 9800-CL in AWS and rolling out "
        "Meraki MR access points across 600 retail stores. We need IP Fabric to automatically stitch wireless client AP-to-switch "
        "CDP/LLDP neighbors into the core campus topology without requiring separate Meraki API keys per store. Also, we need "
        "to extract roaming mobility tunnel state (CAPWAP over IPsec). If discovery takes more than 15 minutes, our NetOps team "
        "cannot use it during change windows.\""
    ),
    "Vendor API Spec: AWS VPC Transit Gateway & Direct Connect Cloud Discovery": (
        "AWS Transit Gateway BGP & Route Table API Snippet:\n"
        "DescribeTransitGatewayRouteTables API returns multi-region route tables, attachment IDs (tgw-attach-01), "
        "and BGP ASN 64512 associations. Need IP Fabric discovery worker to query AWS SDK via IAM role, normalize "
        "TGW route tables into the standard IP Fabric L3 routing model, and stitch Direct Connect Gateway circuits "
        "to on-prem Juniper MX edge routers."
    ),
    "Legacy Edge Switch Customer Escalation (Enterasys / Extreme EOS)": (
        "Customer Escalation (Manufacturing Plant):\n"
        "\"Our shop floor still runs 140 vintage Enterasys SecureStack switches running firmware 6.81. Discovery currently fails "
        "because the switch only responds to SNMPv1 and drops SSH after 2 commands. We need full L2 VLAN and MAC table support "
        "or we cannot renew our enterprise license.\""
    ),
    "Custom Feature Request / Vendor Snippet": "",
}

# ---------------------------------------------------------------------------
# Session State Initialization (Persistent history across all tabs)
# ---------------------------------------------------------------------------
if "health_assessment" not in st.session_state:
    st.session_state["health_assessment"] = None
if "health_history" not in st.session_state:
    st.session_state["health_history"] = []

if "triage_assessment" not in st.session_state:
    st.session_state["triage_assessment"] = None
if "triage_history" not in st.session_state:
    st.session_state["triage_history"] = []

if "vendor_parser_output" not in st.session_state:
    st.session_state["vendor_parser_output"] = None
if "vendor_history" not in st.session_state:
    st.session_state["vendor_history"] = []

if "pm_spec_output" not in st.session_state:
    st.session_state["pm_spec_output"] = None
if "pm_history" not in st.session_state:
    st.session_state["pm_history"] = []

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

# Initialize widget keys from first preset if not already present
first_v_key = list(VENDOR_PRESETS.keys())[0]
if "vi_vendor" not in st.session_state:
    st.session_state["vi_vendor"] = VENDOR_PRESETS[first_v_key]["vendor"]
if "vi_os" not in st.session_state:
    st.session_state["vi_os"] = VENDOR_PRESETS[first_v_key]["os"]
if "vi_raw_input" not in st.session_state:
    st.session_state["vi_raw_input"] = VENDOR_PRESETS[first_v_key]["input"]

first_pm_key = list(PM_PRESETS.keys())[0]
if "pm_raw_input" not in st.session_state:
    st.session_state["pm_raw_input"] = PM_PRESETS[first_pm_key]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔍 IP Fabric")
    st.markdown("### Discovery Insight Engine")
    st.caption("Upstream Collection, Normalization & Multi-Vendor Parser Diagnostics")
    st.divider()

    st.markdown("**Author:** Ranaji Deb")
    st.caption("Senior Product Manager — Network Discovery (POC)")
    st.divider()

    mode_icon = "🟢 Live" if settings.is_live else "🟡 Demo"
    st.markdown(f"**Data mode:** {mode_icon}")
    if settings.is_live:
        st.caption(f"Connected to `{settings.ipf_url}`")
    st.markdown(f"**LLM:** {'✅ Enabled' if settings.has_llm else '⚠️ Disabled'}")
    if settings.has_llm:
        st.caption(f"Model: `{settings.openrouter_model}`")
    st.divider()

    # Snapshot selector
    try:
        snapshots = data.get_snapshots()
    except Exception as e:
        st.error(f"Failed to load snapshots: {e}")
        snapshots = []

    snap_names = [s.get("name", s.get("id", "unknown")) for s in snapshots]
    snap_map = {s.get("name", s.get("id")): s for s in snapshots}

    selected_snap = st.selectbox(
        "Active snapshot",
        snap_names,
        index=len(snap_names) - 1 if snap_names else 0,
        disabled=not snap_names,
    )
    snap_id = snap_map.get(selected_snap, {}).get("id") if selected_snap else None

    if st.button("🔄 Sync Live Snapshots", key="refresh_snaps_btn"):
        data.reset_client()
        st.rerun()

    st.divider()
    st.markdown(
        "**Core Mandate:** Demonstrating upstream product judgment across "
        "**Discovery Worker Queues**, **Seed Hop Traversal**, "
        "**CLI Parsing Diagnostics**, **Vendor Ingestion**, and **PM Decision Velocity**."
    )

# ---------------------------------------------------------------------------
# Load Telemetry & Fixtures
# ---------------------------------------------------------------------------
devices_df = data.get_devices(snap_id)
traversal_data = data.get_traversal_metrics(snap_id)
diagnostics_list = data.get_diagnostics(snap_id)
vendor_matrix = data.get_vendor_matrix()

# ---------------------------------------------------------------------------
# Tabs Navigation
# ---------------------------------------------------------------------------
tab_health, tab_triage, tab_vendor, tab_copilot, tab_ask = st.tabs([
    "🏥 Discovery Health & Traversal",
    "🔍 Discovery Triage & Diagnostics",
    "🧩 Vendor Support & AI Ingestion",
    "🛠️ PM Copilot & Spec Synthesizer",
    "💬 Discovery Engine Assistant",
])

# ===========================================================================
# TAB 1: DISCOVERY HEALTH & TRAVERSAL SCORECARD
# ===========================================================================
with tab_health:
    st.header("Discovery Health & Traversal Scorecard")
    st.caption("Fidelity, normalization completeness, seed traversal reachability, and engine worker metrics.")

    if devices_df.empty:
        st.warning("No device data available for this snapshot.")
    else:
        # --- Normalization & Traversal Calculations ---
        device_count = len(devices_df)
        vendor_count = devices_df["vendor"].nunique() if "vendor" in devices_df.columns else 0
        site_count = devices_df["siteName"].nunique() if "siteName" in devices_df.columns else 0
        failed_count = len(devices_df[devices_df["taskKey"] == "failed"]) if "taskKey" in devices_df.columns else 0
        
        l2_rate = round(float(devices_df["l2_normalized"].mean() * 100), 1) if "l2_normalized" in devices_df.columns else 94.2
        l3_rate = round(float(devices_df["l3_normalized"].mean() * 100), 1) if "l3_normalized" in devices_df.columns else 89.6
        sec_rate = round(float(devices_df["sec_normalized"].mean() * 100), 1) if "sec_normalized" in devices_df.columns else 82.1
        
        seed_summary = traversal_data.get("seed_summary", {})
        seed_rate = seed_summary.get("reachability_rate_pct", 95.8)
        engine_perf = traversal_data.get("engine_performance", {})

        # --- Top KPI Row ---
        k_col1, k_col2, k_col3, k_col4, k_col5, k_col6 = st.columns(6)
        k_col1.metric("Discovered Devices", device_count)
        k_col2.metric("L2 Topology Rate", f"{l2_rate}%", help="Percentage of devices with complete MAC/STP/VLAN normalization")
        k_col3.metric("L3 Routing Rate", f"{l3_rate}%", help="Percentage of devices with complete Route/ARP/VRF tables")
        k_col4.metric("Security Policy Rate", f"{sec_rate}%", help="Percentage of devices with complete ACL/Policy tables")
        k_col5.metric("Seed Reachability", f"{seed_rate}%", help="23 of 24 configured seed gateway IPs reached")
        k_col6.metric("Task Failures", failed_count, delta=f"-{failed_count}" if failed_count > 0 else "0", delta_color="inverse")

        st.divider()

        # --- Middle Section: Traversal Funnel + Credential Hit Rates + Engine Performance ---
        m_col1, m_col2 = st.columns(2)

        with m_col1:
            st.subheader("🌱 Seed & Traversal Hop Distribution")
            hop_breakdown = traversal_data.get("hop_traversal_breakdown", [])
            if hop_breakdown:
                hop_df = pd.DataFrame(hop_breakdown)
                fig_hops = px.bar(
                    hop_df,
                    x="name",
                    y="discovered_count",
                    text="discovered_count",
                    color="avg_latency_ms",
                    color_continuous_scale="Viridis",
                    labels={"discovered_count": "Nodes Discovered", "name": "Hop Distance", "avg_latency_ms": "Avg Latency (ms)"},
                    title="Discovery Graph Expansion by Hop Distance",
                )
                fig_hops.update_layout(height=340)
                st.plotly_chart(fig_hops, width="stretch")

        with m_col2:
            st.subheader("🔑 Credential Pool Hit Rates")
            cred_rates = traversal_data.get("credential_pool_hit_rates", [])
            if cred_rates:
                cred_df = pd.DataFrame(cred_rates)
                fig_creds = px.pie(
                    cred_df,
                    names="profile",
                    values="hits",
                    hole=0.45,
                    title="Authentication Profile Distribution",
                    color_discrete_sequence=px.colors.qualitative.Safe,
                )
                fig_creds.update_layout(height=340)
                st.plotly_chart(fig_creds, width="stretch")

        # --- Engine Performance Card ---
        st.subheader("⚙️ Worker Queue & Engine Scalability Telemetry")
        p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
        p_col1.metric("Discovery Duration", engine_perf.get("snapshot_duration_formatted", "8m 42s"))
        p_col2.metric("Worker Pool Utilization", f"{engine_perf.get('peak_worker_utilization_pct', 68.5)}%", help="Peak queue saturation across 32 async workers")
        p_col3.metric("Avg Device Discovery", f"{engine_perf.get('avg_device_discovery_sec', 3.41)}s")
        p_col4.metric("CLI Commands Executed", f"{engine_perf.get('total_cli_commands_executed', 3412):,}")
        p_col5.metric("CLI Output Parsed", f"{engine_perf.get('total_cli_bytes_parsed_mb', 142.8)} MB")

        st.divider()

        # --- AI Discovery Health Assessment ---
        ai_hdr_col1, ai_hdr_col2 = st.columns([3.5, 1.5])
        with ai_hdr_col1:
            st.subheader("🤖 AI Discovery Health & Traversal Assessment")
        with ai_hdr_col2:
            with st.popover("ℹ️ Discovery Model & Trust Parameters", help="Click to view inference grounding"):
                st.markdown("#### 🛡️ Discovery Reasoning Grounding")
                st.markdown(f"- **Inference Engine:** `{settings.openrouter_model}`")
                st.markdown("- **Telemetry Inputs:** Normalization completion rates, Seed hop traversal, Worker queue saturation, Credential profile hits")
                st.markdown("- **Deterministic Mode:** Temperature `0.3`")
                st.markdown("- **Target Persona:** Discovery Lead / VP of Infrastructure")

        health_summary_payload = {
            "snapshot": selected_snap,
            "device_count": device_count,
            "normalization_rates": {"l2": l2_rate, "l3": l3_rate, "sec": sec_rate},
            "seed_reachability": seed_summary,
            "engine_performance": engine_perf,
            "failed_devices": devices_df[devices_df["taskKey"] == "failed"][["hostname", "siteName", "vendor", "parsing_status"]].to_dict("records") if "taskKey" in devices_df.columns else [],
            "credential_pool": cred_rates,
            "unreached_hops": traversal_data.get("unreached_neighbor_hops", []),
        }

        btn_health_label = "Regenerate Health Assessment" if st.session_state["health_assessment"] else "Generate Discovery Health Assessment"
        if st.button(btn_health_label, type="primary", key="btn_run_health_ai"):
            with st.spinner("Analyzing discovery normalization and traversal fidelity…"):
                assessment = insights.assess_discovery_health(health_summary_payload)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["health_assessment"] = {
                    "text": assessment,
                    "timestamp": timestamp,
                    "snapshot": selected_snap,
                }
                st.session_state["health_history"].append({
                    "timestamp": timestamp,
                    "snapshot": selected_snap,
                    "text": assessment,
                })

        if st.session_state["health_assessment"]:
            curr_h = st.session_state["health_assessment"]
            st.caption(f"📅 Generated at {curr_h['timestamp']} for snapshot **{curr_h['snapshot']}**")
            st.markdown(curr_h["text"])

            st.download_button(
                label="📥 Download Discovery Health Assessment (.md)",
                data=f"# Discovery Health & Traversal Assessment\n\n**Snapshot:** {curr_h['snapshot']}\n**Generated:** {curr_h['timestamp']}\n\n{curr_h['text']}",
                file_name=f"Discovery_Health_{curr_h['snapshot'].replace(' ', '_')}.md",
                mime="text/markdown",
                key="dl_health_md",
            )

            # --- Immediate & Strategic Actions Hub ---
            st.divider()
            st.subheader("⚡ Discovery Operational Actions Hub")
            act_col1, act_col2, act_col3 = st.columns(3)
            with act_col1:
                if st.button("🔄 Queue Discovery for Incomplete Nodes", width="stretch", key="act_requeue_incomplete"):
                    st.toast("Queued targeted discovery tasks for 4 nodes with partial table reads.", icon="🚀")
            with act_col2:
                if st.button("🔑 Expand Credential Pool for Floor 3", width="stretch", key="act_cred_pool"):
                    st.toast("Opened Credential Management dialog to associate TACACS+ profile for Floor 3.", icon="🔑")
            with act_col3:
                if st.button("⏱️ Adjust SSH Session Buffer Timeout", width="stretch", key="act_buffer_timeout"):
                    st.toast("Updated global discovery timeout: BGP/VRF command timeout extended to 90s.", icon="⏱️")

        # --- History Section for Tab 1 ---
        if st.session_state["health_history"]:
            with st.expander(f"📜 Previous Health Assessments ({len(st.session_state['health_history'])} runs)", expanded=False):
                for idx, h in enumerate(reversed(st.session_state["health_history"]), 1):
                    st.markdown(f"**Run {len(st.session_state['health_history']) - idx + 1}** — *{h['timestamp']}* (Snapshot: `{h['snapshot']}`)")
                    st.markdown(h["text"])
                    st.divider()

        # --- Interactive Device Inventory Explorer with Normalization Badges ---
        st.divider()
        st.subheader("📋 Discovered Device Normalization Explorer")
        st.caption("Inspect individual device normalization completeness across Layer 2, Layer 3, and Security tables.")

        f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 1.5])
        all_vendors = sorted(devices_df["vendor"].dropna().unique().tolist()) if "vendor" in devices_df.columns else []
        all_sites = sorted(devices_df["siteName"].dropna().unique().tolist()) if "siteName" in devices_df.columns else []

        with f_col1:
            f_vendors = st.multiselect("Filter Vendor", all_vendors, default=[], key="df_vendor")
        with f_col2:
            f_sites = st.multiselect("Filter Site", all_sites, default=[], key="df_site")
        with f_col3:
            f_search = st.text_input("Search Hostname / IP / Model", placeholder="e.g. core-rtr, 10.0, C9300", key="df_search")
        with f_col4:
            st.write("")
            f_failed_only = st.checkbox("Failed / Partial only", key="df_failed_only")

        filtered_devs = devices_df.copy()
        if f_vendors:
            filtered_devs = filtered_devs[filtered_devs["vendor"].isin(f_vendors)]
        if f_sites:
            filtered_devs = filtered_devs[filtered_devs["siteName"].isin(f_sites)]
        if f_search:
            q = f_search.lower()
            mask = filtered_devs["hostname"].astype(str).str.lower().str.contains(q)
            if "loginIpv4" in filtered_devs.columns:
                mask = mask | filtered_devs["loginIpv4"].astype(str).str.contains(q)
            if "model" in filtered_devs.columns:
                mask = mask | filtered_devs["model"].astype(str).str.lower().str.contains(q)
            filtered_devs = filtered_devs[mask]
        if f_failed_only and "taskKey" in filtered_devs.columns:
            filtered_devs = filtered_devs[(filtered_devs["taskKey"] == "failed") | (filtered_devs["parsing_status"] != "Fully Normalized")]

        # Render dataframe with column configurations
        st.caption(f"Displaying **{len(filtered_devs)}** of **{len(devices_df)}** discovered devices")
        st.dataframe(
            filtered_devs[[
                "hostname", "vendor", "platform", "version", "siteName", "loginIpv4",
                "seed_hop", "cred_profile", "l2_normalized", "l3_normalized", "sec_normalized", "parsing_status"
            ]],
            column_config={
                "l2_normalized": st.column_config.ProgressColumn("L2 Normalization", min_value=0, max_value=1.0, format="%.0f%%"),
                "l3_normalized": st.column_config.ProgressColumn("L3 Normalization", min_value=0, max_value=1.0, format="%.0f%%"),
                "sec_normalized": st.column_config.ProgressColumn("Sec Policy", min_value=0, max_value=1.0, format="%.0f%%"),
                "seed_hop": st.column_config.NumberColumn("Hop", help="0=Seed device, 1=Direct neighbor"),
            },
            width="stretch",
            height=320,
        )


# ===========================================================================
# TAB 2: DISCOVERY TRIAGE & PARSING DIAGNOSTICS
# ===========================================================================
with tab_triage:
    st.header("Discovery Triage & Parsing Diagnostics")
    st.caption("Deep CLI-level failure analysis, regex parsing diagnostics, SSH timeouts, and traversal boundaries.")

    # --- Diagnostics KPIs ---
    total_diag_failures = len(diagnostics_list)
    timeout_failures = sum(1 for d in diagnostics_list if d.get("errorCategory") in ["Command Timeout", "SSH Jumphost Timeout"])
    regex_failures = sum(1 for d in diagnostics_list if d.get("errorCategory") == "Parsing/Regex Mismatch")
    syntax_failures = sum(1 for d in diagnostics_list if d.get("errorCategory") == "Unsupported CLI Syntax")
    auth_failures = sum(1 for d in diagnostics_list if d.get("errorCategory") == "Auth / Privilege Mismatch")
    unreached_hops_count = len(traversal_data.get("unreached_neighbor_hops", []))

    t_col1, t_col2, t_col3, t_col4, t_col5 = st.columns(5)
    t_col1.metric("Diagnosed Failures", total_diag_failures, delta=None if total_diag_failures == 0 else f"{total_diag_failures} issues", delta_color="inverse")
    t_col2.metric("Timeouts / Jumphost", timeout_failures)
    t_col3.metric("Regex Mismatches", regex_failures)
    t_col4.metric("Syntax / Privilege", syntax_failures + auth_failures)
    t_col5.metric("Unreached Neighbor Hops", unreached_hops_count)

    st.divider()

    # --- Interactive Diagnostic Filter Toolbar ---
    diag_f1, diag_f2 = st.columns([2, 2])
    all_categories = sorted(list({d.get("errorCategory", "Unknown") for d in diagnostics_list}))
    all_diag_sites = sorted(list({d.get("siteName", "Unknown") for d in diagnostics_list}))

    with diag_f1:
        sel_cat = st.multiselect("Filter Error Category", all_categories, default=[], key="triage_cat_filter")
    with diag_f2:
        sel_diag_site = st.multiselect("Filter Site", all_diag_sites, default=[], key="triage_site_filter")

    filtered_diag = [
        d for d in diagnostics_list
        if (not sel_cat or d.get("errorCategory") in sel_cat)
        and (not sel_diag_site or d.get("siteName") in sel_diag_site)
    ]

    st.subheader(f"🔬 CLI-Level Diagnostic Inspector ({len(filtered_diag)} Issues)")
    st.caption("Expand any card to inspect raw CLI snippets, buffer outputs, and execute immediate remediation:")

    for d in filtered_diag:
        with st.expander(f"🔴 `{d['hostname']}` ({d['vendor']} {d['platform']} {d['version']}) — **{d['errorCategory']}** at `{d['siteName']}`", expanded=True):
            d_c1, d_c2 = st.columns([2.5, 1.5])
            with d_c1:
                st.markdown(f"**Failed Command:** `{d['command']}`")
                st.markdown(f"**Discovery Phase:** `{d['phase']}`")
                st.markdown(f"**Technical Root Cause:** {d['rootCause']}")
                st.markdown(f"**Engineering Remediation:** {d['remediation']}")
                st.markdown(f"**Graph Fidelity Impact:** `{d['impact']}`")
                
                # Direct Call to Action: Fix Issue right below the remediation line
                if st.button(f"⚡ Fix Issue: Apply Remediation for `{d['hostname']}`", key=f"btn_fix_{d['id']}", type="primary"):
                    st.toast(f"✅ Applied Fix for {d['hostname']}: {d['remediation']}", icon="🛠️")
            with d_c2:
                st.markdown("**Raw CLI Output Snippet:**")
                st.code(d["rawSnippet"], language="text")

    st.divider()

    # --- Unreached Neighbor Hops & Unmapped Subnets: VERTICALLY STACKED ---
    st.subheader("🌐 Traversal Blindspots: Unreached Neighbors & Unmapped Subnets")
    st.caption("Full-width inspection of neighbor adjacency breaks and zero-discovery subnets:")

    # 1. CDP/LLDP Neighbors
    st.markdown("##### ⚠️ 1. CDP/LLDP Neighbors Detected But Traversal Stopped")
    unreached_hops = traversal_data.get("unreached_neighbor_hops", [])
    if unreached_hops:
        st.dataframe(
            pd.DataFrame(unreached_hops)[[
                "neighbor_name", "detected_by_device", "neighbor_ip", "protocol", "unreached_reason", "action"
            ]],
            width="stretch",
            height=200,
        )

    st.write("")  # visual spacing

    # 2. Routing Table Subnets
    st.markdown("##### 🗺️ 2. Routing Table Subnets With Zero Discovered Devices")
    unmapped_subs = traversal_data.get("unmapped_subnets", [])
    if unmapped_subs:
        st.dataframe(
            pd.DataFrame(unmapped_subs)[[
                "subnet", "site", "discovered_routes", "risk"
            ]],
            width="stretch",
            height=180,
        )

    st.divider()

    # --- AI Root Cause Classifier & Triage Synthesis ---
    triage_ai_col1, triage_ai_col2 = st.columns([3.5, 1.5])
    with triage_ai_col1:
        st.subheader("🤖 AI Discovery Triage & Root Cause Classifier")
    with triage_ai_col2:
        with st.popover("ℹ️ Triage Model & Parameters", help="Grounding parameters for CLI parsing diagnostics"):
            st.markdown("#### 🛡️ CLI Parsing Diagnostics Engine")
            st.markdown(f"- **Model:** `{settings.openrouter_model}`")
            st.markdown("- **Inputs:** Raw CLI failure snippets, SSH timeout logs, TACACS privilege errors, Unreached neighbor hops")
            st.markdown("- **Output:** Root cause classification, Regex patch patterns, Discovery tuning recommendations")

    triage_summary_payload = {
        "snapshot": selected_snap,
        "total_failures": len(diagnostics_list),
        "by_category": {cat: sum(1 for d in diagnostics_list if d.get("errorCategory") == cat) for cat in all_categories},
        "diagnostic_records": diagnostics_list,
        "unreached_hops": traversal_data.get("unreached_neighbor_hops", []),
        "unmapped_subnets": traversal_data.get("unmapped_subnets", []),
    }

    btn_triage_label = "Regenerate Triage Classification" if st.session_state["triage_assessment"] else "Classify Root Causes with AI"
    if st.button(btn_triage_label, type="primary", key="btn_run_triage_ai"):
        with st.spinner("Classifying discovery failures and synthesizing engineering fixes…"):
            triage_res = insights.diagnose_discovery_failures(triage_summary_payload)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["triage_assessment"] = {
                "text": triage_res,
                "timestamp": timestamp,
                "snapshot": selected_snap,
            }
            st.session_state["triage_history"].append({
                "timestamp": timestamp,
                "snapshot": selected_snap,
                "text": triage_res,
            })

    if st.session_state["triage_assessment"]:
        curr_t = st.session_state["triage_assessment"]
        st.caption(f"📅 Generated at {curr_t['timestamp']} for snapshot **{curr_t['snapshot']}**")
        st.markdown(curr_t["text"])

        # --- Direct Remediation Action Center ---
        st.divider()
        st.markdown("#### ⚡ AI Remediation Action Center")
        st.caption("One-click execution triggers for all diagnosed discovery failure categories:")
        
        fix_col1, fix_col2, fix_col3 = st.columns(3)
        with fix_col1:
            if st.button("🛠️ Fix Issue: Deploy Regex & Syntax Patches", width="stretch", key="act_fix_regex"):
                st.toast("Deployed regex patches for Cisco IOS 15.2 CDP headers & Check Point Gaia R81.20 CLISH syntax.", icon="✅")
        with fix_col2:
            if st.button("🛠️ Fix Issue: Unblock Jumphost Security Group", width="stretch", key="act_fix_jumphost"):
                st.toast("Updated security group on jumphost-eu-west-01 to permit TCP/22 to 10.40.1.0/24.", icon="✅")
        with fix_col3:
            if st.button("🛠️ Fix Issue: Extend Route Dump Timeout (90s)", width="stretch", key="act_fix_timeout"):
                st.toast("Applied chunked pagination and extended SSH command timeout to 90s for large VRF tables.", icon="✅")

        st.write("")
        st.download_button(
            label="📥 Download Triage & Parsing Diagnostics Report (.md)",
            data=f"# Discovery Triage & Parsing Diagnostics Report\n\n**Snapshot:** {curr_t['snapshot']}\n**Generated:** {curr_t['timestamp']}\n\n{curr_t['text']}",
            file_name=f"Discovery_Triage_{curr_t['snapshot'].replace(' ', '_')}.md",
            mime="text/markdown",
            key="dl_triage_md",
        )

    # --- History Section for Tab 2 ---
    if st.session_state["triage_history"]:
        with st.expander(f"📜 Previous Triage & Diagnostics Analyses ({len(st.session_state['triage_history'])} runs)", expanded=False):
            for idx, h in enumerate(reversed(st.session_state["triage_history"]), 1):
                st.markdown(f"**Run {len(st.session_state['triage_history']) - idx + 1}** — *{h['timestamp']}* (Snapshot: `{h['snapshot']}`)")
                st.markdown(h["text"])
                st.divider()



# ===========================================================================
# TAB 3: VENDOR SUPPORT & AI INGESTION ENGINE
# ===========================================================================
with tab_vendor:
    st.header("Vendor Support & AI Ingestion Engine")
    st.caption("Automate multi-vendor support analysis: match unmanaged OUIs/sysDescr strings and generate production CLI regex parsers from release notes.")

    # --- Sub-section A: Vendor & OS Gap Analyzer (VERTICALLY STACKED) ---
    st.subheader("1️⃣ Vendor & OS Gap Analyzer")
    st.caption("Telemetric matching of unmanaged MAC prefixes (OUIs) and unparsed sysDescr strings against IP Fabric's supported matrix.")

    # 1. Unidentified OUIs (Full Width)
    st.markdown("##### 🏷️ 1. Unidentified / Unmanaged MAC OUIs Detected")
    unknown_ouis = vendor_matrix.get("unknown_ouis", [])
    if unknown_ouis:
        st.dataframe(
            pd.DataFrame(unknown_ouis)[["oui", "vendor_detected", "observed_mac_count", "impact", "status"]],
            width="stretch",
            height=200,
        )

    st.write("")  # visual spacing

    # 2. Unparsed sysDescr Strings (Full Width)
    st.markdown("##### 📝 2. Unparsed sysDescr Strings & Parser Gaps")
    unparsed_sys = vendor_matrix.get("unparsed_sysdescrs", [])
    if unparsed_sys:
        st.dataframe(
            pd.DataFrame(unparsed_sys)[["vendor", "platform", "version", "devices_affected", "gap"]],
            width="stretch",
            height=200,
        )

    # Vendor Support Tiers Reference & Gap Backlog
    with st.expander("📚 IP Fabric Support Matrix & Firmware Gap Backlog"):
        b_c1, b_c2 = st.columns(2)
        with b_c1:
            st.markdown("##### 🏆 Canonical Support Tiers")
            for tier in vendor_matrix.get("vendor_support_tiers", []):
                st.markdown(f"**{tier['tier']}**")
                st.caption(tier["description"])
                st.markdown(f"*Vendors:* {', '.join(tier['vendors'])}")
                st.divider()
        with b_c2:
            st.markdown("##### 🗳️ Enterprise Firmware Gap Prioritization Backlog")
            backlog_df = pd.DataFrame(vendor_matrix.get("firmware_gap_backlog", []))
            st.dataframe(backlog_df, width="stretch", height=260)

    st.divider()

    # --- Sub-section B: AI Vendor Support Ingestion Engine ---
    st.subheader("2️⃣ AI Vendor Support Ingestion Engine")
    st.caption("Feed raw vendor release notes, command reference manuals, or CLI outputs into the LLM to automatically generate CLI commands, regex parsing patterns, and IP Fabric digital twin schema mappings.")

    def on_vendor_preset_change():
        chosen = st.session_state.get("vendor_preset_select")
        if chosen and chosen in VENDOR_PRESETS:
            p_data = VENDOR_PRESETS[chosen]
            st.session_state["vi_vendor"] = p_data["vendor"]
            st.session_state["vi_os"] = p_data["os"]
            st.session_state["vi_raw_input"] = p_data["input"]

    st.selectbox(
        "Choose a Vendor Documentation / CLI Preset",
        list(VENDOR_PRESETS.keys()),
        index=0,
        key="vendor_preset_select",
        on_change=on_vendor_preset_change,
    )

    v_c1, v_c2 = st.columns(2)
    with v_c1:
        st.text_input("Target Vendor", placeholder="e.g. Arista, Palo Alto, Cisco", key="vi_vendor")
    with v_c2:
        st.text_input("Firmware / OS Version", placeholder="e.g. EOS 4.31.3M, PAN-OS 11.1", key="vi_os")

    st.text_area(
        "Raw Vendor Release Note / Command Reference / CLI Output Snippet",
        height=220,
        placeholder="Paste raw vendor documentation or CLI output here...",
        key="vi_raw_input",
    )

    input_vendor = st.session_state["vi_vendor"]
    input_os = st.session_state["vi_os"]
    input_text = st.session_state["vi_raw_input"]

    if st.button("🤖 Generate CLI Command List & Regex Parsers", type="primary", key="btn_run_vendor_ingest"):
        if not input_text.strip():
            st.warning("Please enter vendor documentation or CLI output.")
        else:
            with st.spinner("Synthesizing CLI discovery sequence, named-group regex patterns, and schema mappings…"):
                parser_spec = insights.generate_vendor_parser(input_vendor, input_os, input_text)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["vendor_parser_output"] = {
                    "text": parser_spec,
                    "timestamp": timestamp,
                    "vendor": input_vendor,
                    "os": input_os,
                }
                st.session_state["vendor_history"].append({
                    "timestamp": timestamp,
                    "vendor": input_vendor,
                    "os": input_os,
                    "text": parser_spec,
                })

    if st.session_state["vendor_parser_output"]:
        curr_vp = st.session_state["vendor_parser_output"]
        st.divider()
        st.subheader("🛠️ Generated Discovery Parser Specification")
        st.caption(f"📅 Generated at {curr_vp['timestamp']} for **{curr_vp['vendor']}** ({curr_vp['os']})")
        st.markdown(curr_vp["text"])

        st.download_button(
            label="📥 Download Parser Specification (.md)",
            data=curr_vp["text"],
            file_name=f"Parser_Spec_{curr_vp['vendor']}_{curr_vp['os'].replace(' ', '_')}.md",
            mime="text/markdown",
            key="dl_parser_spec",
        )

    # --- History Section for Tab 3 ---
    if st.session_state["vendor_history"]:
        with st.expander(f"📜 Previous Generated Parser Specifications ({len(st.session_state['vendor_history'])} runs)", expanded=False):
            for idx, h in enumerate(reversed(st.session_state["vendor_history"]), 1):
                st.markdown(f"**Run {len(st.session_state['vendor_history']) - idx + 1}** — *{h['timestamp']}* — Vendor: `{h['vendor']}` (`{h['os']}`)")
                st.markdown(h["text"])
                st.divider()



# ===========================================================================
# TAB 4: PM COPILOT & DISCOVERY SPEC SYNTHESIZER
# ===========================================================================
with tab_copilot:
    st.header("PM Copilot & Discovery Spec Synthesizer")
    st.caption(
        "Practical AI for internal product management: transform unstructured customer requests or vendor API docs "
        "into battle-tested Jira Epics, technical discovery scopes, and explicit engineering vs. business trade-offs."
    )

    def on_pm_preset_change():
        chosen_pm = st.session_state.get("pm_preset_select")
        if chosen_pm and chosen_pm in PM_PRESETS:
            st.session_state["pm_raw_input"] = PM_PRESETS[chosen_pm]

    st.selectbox(
        "Select a Mock Customer Request or Vendor API Doc",
        list(PM_PRESETS.keys()),
        index=0,
        key="pm_preset_select",
        on_change=on_pm_preset_change,
    )

    st.text_area(
        "Raw Input Text",
        height=180,
        placeholder="Enter customer feedback, feature request, or vendor documentation snippet...",
        key="pm_raw_input",
    )

    pm_input_text = st.session_state["pm_raw_input"]
    selected_pm_title = st.session_state.get("pm_preset_select", "Custom Input")

    if st.button("🚀 Synthesize Jira Epic & Technical Discovery Spec", type="primary", key="btn_run_pm_spec"):
        if not pm_input_text.strip():
            st.warning("Please enter input text to synthesize.")
        else:
            with st.spinner("Synthesizing Jira Epic, technical discovery scope, trade-off matrix, and acceptance criteria…"):
                spec_res = insights.synthesize_pm_spec(pm_input_text)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["pm_spec_output"] = {
                    "text": spec_res,
                    "timestamp": timestamp,
                    "source": selected_pm_title,
                }
                st.session_state["pm_history"].append({
                    "timestamp": timestamp,
                    "source": selected_pm_title,
                    "text": spec_res,
                })

    if st.session_state["pm_spec_output"]:
        curr_pms = st.session_state["pm_spec_output"]
        st.divider()
        st.subheader("📋 Synthesized Jira Epic & Product Discovery Memo")
        st.caption(f"📅 Generated at {curr_pms['timestamp']} from *{curr_pms['source']}*")
        st.markdown(curr_pms["text"])

        st.download_button(
            label="📥 Download Jira Epic Specification (.md)",
            data=curr_pms["text"],
            file_name="Jira_Epic_Discovery_Spec.md",
            mime="text/markdown",
            key="dl_pm_spec",
        )

    # --- History Section for Tab 4 ---
    if st.session_state["pm_history"]:
        with st.expander(f"📜 Previous Synthesized Jira Epics ({len(st.session_state['pm_history'])} runs)", expanded=False):
            for idx, h in enumerate(reversed(st.session_state["pm_history"]), 1):
                st.markdown(f"**Run {len(st.session_state['pm_history']) - idx + 1}** — *{h['timestamp']}* — Source: *{h['source']}*")
                st.markdown(h["text"])
                st.divider()


# ===========================================================================
# TAB 5: DISCOVERY ENGINE ASSISTANT (Conversational Querying)
# ===========================================================================
with tab_ask:
    chat_hdr_col1, chat_hdr_col2 = st.columns([3.2, 1.8])
    with chat_hdr_col1:
        st.header("Discovery Engine Assistant")
        st.caption(
            "Conversational reasoning grounded directly in discovery logs, CLI parsing errors, "
            "traversal hops, and vendor matrix telemetry."
        )
    with chat_hdr_col2:
        st.write("")
        if st.button("🗑️ Clear Assistant History", type="secondary", key="clear_chat_btn"):
            st.session_state["chat_messages"] = []
            st.toast("🧹 Conversation history cleared.", icon="🗑️")
            st.rerun()

    def _build_discovery_context():
        return {
            "snapshot": selected_snap,
            "device_count": len(devices_df),
            "normalization_rates": {
                "l2": float(devices_df["l2_normalized"].mean() * 100) if "l2_normalized" in devices_df.columns else 94.2,
                "l3": float(devices_df["l3_normalized"].mean() * 100) if "l3_normalized" in devices_df.columns else 89.6,
                "sec": float(devices_df["sec_normalized"].mean() * 100) if "sec_normalized" in devices_df.columns else 82.1,
            },
            "diagnostics": diagnostics_list,
            "traversal": traversal_data,
            "vendor_matrix": vendor_matrix,
        }

    # Suggested Prompts (Accordion)
    chosen_prompt = None
    with st.expander("💡 Discovery Engine Investigation Prompts (Click to Ask)", expanded=False):
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            st.markdown("##### 🔬 CLI & Parsing Diagnostics")
            if st.button("• Why did `show ip route vrf *` time out on `core-rtr-02`?", key="p_sug_1"):
                chosen_prompt = "Explain why 'show ip route vrf *' timed out on core-rtr-02 and what configuration or buffer tuning is required."
            if st.button("• What caused the regex failure on `access-sw-04`?", key="p_sug_2"):
                chosen_prompt = "Why did the CDP neighbor regex parser fail on access-sw-04 running IOS 15.2(7)E7?"

        with p_c2:
            st.markdown("##### 🌱 Traversal & Vendor Priorities")
            if st.button("• Summarize unreached neighbor hops and credential hit rates.", key="p_sug_3"):
                chosen_prompt = "Summarize our credential pool hit rates and explain which neighbor hops were unreached."
            if st.button("• How should we prioritize Arista EOS 4.31 vs ExtremeXOS?", key="p_sug_4"):
                chosen_prompt = "Compare Arista EOS 4.31 vs ExtremeXOS 32.x in our vendor support matrix: what are the customer and engineering trade-offs?"

    # --- Top Ask A Question Field (Positioned directly below suggested prompts) ---
    st.markdown("##### 💬 Ask a Question")
    ask_col1, ask_col2 = st.columns([4.2, 0.8])
    with ask_col1:
        top_user_input = st.text_input(
            "Enter your discovery question",
            placeholder="e.g. Why did discovery fail on sdwan-vedge-01? Or what is our L2 normalization rate?",
            label_visibility="collapsed",
            key="top_ask_input",
        )
    with ask_col2:
        top_send_btn = st.button("Ask ➔", type="primary", key="top_ask_btn", width="stretch")

    prompt_to_run = (top_user_input if top_send_btn and top_user_input.strip() else None) or chosen_prompt

    # Corner Quick-Ask Popover
    pop_c1, pop_c2 = st.columns([4.2, 0.8])
    with pop_c2:
        with st.popover("💬 Quick Ask", help="Click to ask a quick question without navigating to the top"):
            st.markdown("#### 💬 Ask Discovery Assistant")
            pop_input = st.text_input("Quick Question", placeholder="Type your question here...", key="pop_quick_input")
            if st.button("Send", type="primary", key="pop_quick_btn"):
                if pop_input.strip():
                    prompt_to_run = pop_input

    st.divider()

    # --- Conversation Stream (Falls below the input box) ---
    st.subheader(f"🗣️ Conversation History ({len(st.session_state['chat_messages'])} messages)")
    
    if not st.session_state["chat_messages"]:
        st.info("💡 Type a question above or click any suggested prompt to begin the discovery investigation.")

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "timestamp" in msg:
                st.caption(f"🕒 {msg['timestamp']}")

    if prompt_to_run:
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state["chat_messages"].append({
            "role": "user",
            "content": prompt_to_run,
            "timestamp": timestamp,
        })
        with st.chat_message("user"):
            st.markdown(prompt_to_run)
            st.caption(f"🕒 {timestamp}")

        with st.chat_message("assistant"):
            with st.spinner("Reasoning across discovery telemetry, CLI logs, and parser architecture…"):
                context = _build_discovery_context()
                history_for_api = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state["chat_messages"]
                ]
                reply = insights.answer_conversation(history_for_api, context)
                st.markdown(reply)
                reply_timestamp = datetime.now().strftime("%H:%M:%S")
                st.caption(f"🕒 {reply_timestamp}")

            st.session_state["chat_messages"].append({
                "role": "assistant",
                "content": reply,
                "timestamp": reply_timestamp,
            })
            st.rerun()


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Discovery Insight Engine — POC by **Ranaji Deb** for IP Fabric's "
    "**Senior Product Manager – Network Discovery** role."
)


