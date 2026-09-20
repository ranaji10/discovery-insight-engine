"""
Discovery Insight Engine — Streamlit Dashboard

AI-powered product decision support for IP Fabric Network Discovery.
Built by Ranaji Deb for the Senior Product Manager – Network Discovery role.
"""

from __future__ import annotations

from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.config import settings
from src import data, insights, compare

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
# Session State Initialization (Persistent history across clicks & tabs)
# ---------------------------------------------------------------------------
if "health_assessment" not in st.session_state:
    st.session_state["health_assessment"] = None
if "health_history" not in st.session_state:
    st.session_state["health_history"] = []

if "drift_result" not in st.session_state:
    st.session_state["drift_result"] = None
if "drift_history" not in st.session_state:
    st.session_state["drift_history"] = []

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔍 IP Fabric")
    st.markdown("### Discovery Insight Engine")
    st.caption("AI-powered product decision support for Network Discovery")
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
        "Built by **Ranaji Deb** to demonstrate product thinking "
        "at the intersection of **Network Discovery**, **AI/MCP**, "
        "and **customer value framing**."
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_health, tab_drift, tab_ask = st.tabs([
    "🏥 Discovery Health",
    "📊 Snapshot Drift",
    "💬 Ask Your Network",
])

# ===========================
# TAB 1: DISCOVERY HEALTH
# ===========================
with tab_health:
    st.header("Discovery Health Score")
    st.caption("How complete and reliable is the current network discovery?")

    with st.spinner("Loading device inventory…"):
        try:
            devices_df = data.get_devices(snap_id)
        except Exception as e:
            st.error(f"Failed to load devices: {e}")
            devices_df = pd.DataFrame()

    if devices_df.empty:
        st.warning("No device data available for this snapshot.")
    else:
        # --- KPI row ---
        col1, col2, col3, col4 = st.columns(4)
        device_count = len(devices_df)
        vendor_count = devices_df["vendor"].nunique() if "vendor" in devices_df.columns else 0
        site_count = devices_df["siteName"].nunique() if "siteName" in devices_df.columns else 0
        failed_count = (
            len(devices_df[devices_df["taskKey"] == "failed"])
            if "taskKey" in devices_df.columns else 0
        )

        col1.metric("Devices Discovered", device_count)
        col2.metric("Vendors", vendor_count)
        col3.metric("Sites", site_count)
        col4.metric("Failed Tasks", failed_count, delta=None if failed_count == 0 else f"-{failed_count}", delta_color="inverse")

        st.divider()

        # --- Charts row ---
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            if "vendor" in devices_df.columns:
                vendor_counts = devices_df["vendor"].value_counts().reset_index()
                vendor_counts.columns = ["Vendor", "Count"]
                fig_vendor = px.pie(
                    vendor_counts, names="Vendor", values="Count",
                    title="Device Distribution by Vendor",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_vendor.update_layout(height=400)
                st.plotly_chart(fig_vendor, width="stretch")

        with chart_col2:
            if "siteName" in devices_df.columns:
                site_counts = devices_df["siteName"].value_counts().reset_index()
                site_counts.columns = ["Site", "Devices"]
                fig_site = px.bar(
                    site_counts, x="Site", y="Devices",
                    title="Devices per Site",
                    color="Devices",
                    color_continuous_scale="Teal",
                )
                fig_site.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_site, width="stretch")

        # --- Platform breakdown ---
        if "platform" in devices_df.columns:
            st.subheader("Platform Breakdown")
            platform_counts = devices_df["platform"].value_counts().reset_index()
            platform_counts.columns = ["Platform", "Count"]
            fig_plat = px.bar(
                platform_counts, x="Count", y="Platform",
                orientation="h", title="Devices by Platform/OS",
                color="Platform",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_plat.update_layout(height=max(300, len(platform_counts) * 35), showlegend=False)
            st.plotly_chart(fig_plat, width="stretch")

        st.divider()

        # --- AI Health Assessment ---
        st.subheader("🤖 AI Discovery Health Assessment")
        summary = {
            "device_count": device_count,
            "vendor_breakdown": devices_df["vendor"].value_counts().to_dict() if "vendor" in devices_df.columns else {},
            "site_count": site_count,
            "platform_breakdown": devices_df["platform"].value_counts().to_dict() if "platform" in devices_df.columns else {},
            "failed_devices": devices_df[devices_df["taskKey"] == "failed"]["hostname"].tolist() if "taskKey" in devices_df.columns else [],
            "low_uptime_devices": (
                devices_df[devices_df["uptime"] < 86400]["hostname"].tolist()
                if "uptime" in devices_df.columns else []
            ),
            "snapshot": selected_snap,
        }

        btn_label = "Regenerate Health Assessment" if st.session_state["health_assessment"] else "Generate Health Assessment"
        if st.button(btn_label, type="primary", key="health_btn"):
            with st.spinner("Analysing discovery data with AI…"):
                assessment = insights.assess_discovery_health(summary)
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
            current = st.session_state["health_assessment"]
            st.caption(f"📅 Generated at {current['timestamp']} for snapshot **{current['snapshot']}**")
            st.markdown(current["text"])
        else:
            st.info("Click **Generate Health Assessment** to get an AI-powered product analysis.")

        # History expander
        if len(st.session_state["health_history"]) > 1:
            with st.expander(f"📜 Previous Health Assessments ({len(st.session_state['health_history'])} runs)"):
                for idx, h in enumerate(reversed(st.session_state["health_history"][:-1]), 1):
                    st.markdown(f"**Run {len(st.session_state['health_history']) - idx}** — *{h['timestamp']}* (Snapshot: `{h['snapshot']}`)")
                    st.markdown(h["text"])
                    st.divider()

        # --- Raw data expander ---
        with st.expander("📋 Raw Device Inventory"):
            st.dataframe(devices_df, width="stretch", height=400)


# ===========================
# TAB 2: SNAPSHOT DRIFT
# ===========================
with tab_drift:
    st.header("Snapshot Drift Detector")
    st.caption("Compare two snapshots to detect what changed — and what it means for the product.")

    if len(snapshots) < 2:
        st.warning(
            "At least **two snapshots** are needed for drift detection. "
            "Run another discovery in IP Fabric to enable this view."
        )
    else:
        drift_col1, drift_col2 = st.columns(2)
        with drift_col1:
            snap_a_name = st.selectbox("Baseline snapshot (older)", snap_names, index=0, key="snap_a")
        with drift_col2:
            snap_b_name = st.selectbox("Current snapshot (newer)", snap_names, index=len(snap_names) - 1, key="snap_b")

        snap_a_id = snap_map.get(snap_a_name, {}).get("id")
        snap_b_id = snap_map.get(snap_b_name, {}).get("id")

        if snap_a_id == snap_b_id:
            st.info("Select two different snapshots to compare.")
        else:
            btn_drift_label = "Re-compare Snapshots" if st.session_state["drift_result"] else "Compare Snapshots"
            if st.button(btn_drift_label, type="primary", key="compare_btn"):
                with st.spinner("Loading and comparing snapshots…"):
                    try:
                        df_a = data.get_devices(snap_a_id)
                        df_b = data.get_devices(snap_b_id)
                        diff = compare.compare_device_inventories(df_a, df_b)
                        if diff and "error" not in diff:
                            diff["snapshot_a"] = snap_a_name
                            diff["snapshot_b"] = snap_b_name
                            analysis = insights.analyse_drift(diff)
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            st.session_state["drift_result"] = {
                                "diff": diff,
                                "analysis": analysis,
                                "timestamp": timestamp,
                                "snap_a": snap_a_name,
                                "snap_b": snap_b_name,
                            }
                            st.session_state["drift_history"].append({
                                "timestamp": timestamp,
                                "snap_a": snap_a_name,
                                "snap_b": snap_b_name,
                                "diff": diff,
                                "analysis": analysis,
                            })
                    except Exception as e:
                        st.error(f"Comparison failed: {e}")

            if st.session_state["drift_result"]:
                res = st.session_state["drift_result"]
                diff = res["diff"]
                stats = diff.get("stats", {})

                st.caption(f"📅 Compared at {res['timestamp']}: Baseline **{res['snap_a']}** ➔ Current **{res['snap_b']}**")

                # KPI row
                d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                d_col1.metric("Devices (before)", stats.get("total_a", 0))
                d_col2.metric("Devices (after)", stats.get("total_b", 0), delta=stats.get("net_change", 0))
                d_col3.metric("New Devices", stats.get("added_count", 0))
                d_col4.metric("Removed Devices", stats.get("removed_count", 0), delta_color="inverse")

                st.divider()

                # Details
                detail_col1, detail_col2 = st.columns(2)

                with detail_col1:
                    added = diff.get("added_devices", [])
                    if added:
                        st.subheader(f"🟢 New Devices ({len(added)})")
                        for d in added:
                            st.markdown(f"- `{d}`")
                    else:
                        st.info("No new devices detected.")

                with detail_col2:
                    removed = diff.get("removed_devices", [])
                    if removed:
                        st.subheader(f"🔴 Removed Devices ({len(removed)})")
                        for d in removed:
                            st.markdown(f"- `{d}`")
                    else:
                        st.info("No devices removed.")

                changed = diff.get("changed_devices", [])
                if changed:
                    st.subheader(f"🟡 Changed Devices ({len(changed)})")
                    for item in changed:
                        with st.expander(f"`{item['hostname']}`"):
                            for col, vals in item["changes"].items():
                                st.markdown(f"**{col}:** `{vals['before']}` → `{vals['after']}`")

                st.divider()

                # AI Drift Analysis
                st.subheader("🤖 AI Drift Analysis")
                st.markdown(res["analysis"])

                # History expander
                if len(st.session_state["drift_history"]) > 1:
                    with st.expander(f"📜 Previous Drift Comparisons ({len(st.session_state['drift_history'])} runs)"):
                        for idx, h in enumerate(reversed(st.session_state["drift_history"][:-1]), 1):
                            st.markdown(f"**Run {len(st.session_state['drift_history']) - idx}** — *{h['timestamp']}* (`{h['snap_a']}` ➔ `{h['snap_b']}`)")
                            st.markdown(h["analysis"])
                            st.divider()


# ===========================
# TAB 3: ASK YOUR NETWORK (Interactive Chat + Follow-ups)
# ===========================
with tab_ask:
    st.header("Ask Your Network")
    st.caption(
        "Interactive AI conversation grounded in your IP Fabric discovery data. "
        "Ask questions, drill down into details, and ask follow-up questions."
    )

    # Context builder helper
    def _build_network_context():
        dev_df = data.get_devices(snap_id)
        return {
            "device_count": len(dev_df),
            "vendor_breakdown": dev_df["vendor"].value_counts().to_dict() if "vendor" in dev_df.columns else {},
            "site_breakdown": dev_df["siteName"].value_counts().to_dict() if "siteName" in dev_df.columns else {},
            "platform_breakdown": dev_df["platform"].value_counts().to_dict() if "platform" in dev_df.columns else {},
            "failed_devices": (
                dev_df[dev_df["taskKey"] == "failed"]["hostname"].tolist()
                if "taskKey" in dev_df.columns else []
            ),
            "low_uptime_devices": (
                dev_df[dev_df["uptime"] < 86400][["hostname", "uptime"]].to_dict("records")
                if "uptime" in dev_df.columns else []
            ),
            "os_versions": (
                dev_df.groupby(["vendor", "version"]).size().reset_index(name="count").to_dict("records")
                if "version" in dev_df.columns else []
            ),
            "snapshot": selected_snap,
        }

    # Top action bar: Quick Prompt Buttons + Clear Chat
    quick_col1, quick_col2 = st.columns([4, 1])
    with quick_col2:
        if st.button("🗑️ Clear Chat", key="clear_chat_btn"):
            st.session_state["chat_messages"] = []
            st.rerun()

    with quick_col1:
        st.markdown("**Suggested questions to get started:**")
        sug_cols = st.columns(3)
        sample_q1 = "What is our biggest vendor concentration risk and how to address it?"
        sample_q2 = "Which sites have incomplete discovery or fewest devices?"
        sample_q3 = "Which devices drifted or have low uptime?"

        chosen_prompt = None
        if sug_cols[0].button("⚠️ Vendor Concentration Risk", key="sug_1"):
            chosen_prompt = sample_q1
        if sug_cols[1].button("🏢 Incomplete Discovery Sites", key="sug_2"):
            chosen_prompt = sample_q2
        if sug_cols[2].button("⏱️ Uptime & Drift Anomalies", key="sug_3"):
            chosen_prompt = sample_q3

    st.divider()

    # Render full chat history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "timestamp" in msg:
                st.caption(f"🕒 {msg['timestamp']}")

    # Handle chat input or button click
    user_input = st.chat_input("Ask a question or follow-up about your network...")
    prompt_to_run = user_input or chosen_prompt

    if prompt_to_run:
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Add user message to history
        st.session_state["chat_messages"].append({
            "role": "user",
            "content": prompt_to_run,
            "timestamp": timestamp,
        })
        with st.chat_message("user"):
            st.markdown(prompt_to_run)
            st.caption(f"🕒 {timestamp}")

        # Generate assistant reply
        with st.chat_message("assistant"):
            with st.spinner("Analyzing discovery data and reasoning…"):
                context = _build_network_context()
                # Pass conversation history for true multi-turn follow-ups!
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


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Discovery Insight Engine — POC by **Ranaji Deb** for IP Fabric's "
    "Senior Product Manager, Network Discovery role. "
    "Built with IP Fabric Python SDK, Streamlit, and AI (OpenRouter)."
)

