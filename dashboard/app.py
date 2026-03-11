import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import func
from src.database import init_db, get_session
from src.models import Organization, Contact, Score, ApiCost

st.set_page_config(
    page_title="LP Prospect Scoring Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

TIER_COLORS = {
    "PRIORITY CLOSE": "#10b981",
    "STRONG FIT": "#3b82f6",
    "MODERATE FIT": "#f59e0b",
    "WEAK FIT": "#ef4444",
}

TIER_ORDER = ["PRIORITY CLOSE", "STRONG FIT", "MODERATE FIT", "WEAK FIT"]


@st.cache_data(ttl=30)
def load_data():
    init_db()
    session = get_session()
    try:
        query = (
            session.query(
                Contact.name.label("contact_name"),
                Contact.role,
                Contact.email,
                Contact.contact_status,
                Contact.relationship_depth.label("rel_depth_raw"),
                Organization.name.label("organization"),
                Organization.org_type,
                Organization.region,
                Organization.aum_estimated,
                Organization.investment_mandate,
                Organization.sustainability_focus,
                Organization.emerging_mgr_programs,
                Organization.is_lp,
                Organization.enrichment_status,
                Score.sector_fit,
                Score.sector_fit_reasoning,
                Score.sector_fit_confidence,
                Score.relationship_depth,
                Score.halo_value,
                Score.halo_reasoning,
                Score.halo_confidence,
                Score.emerging_fit,
                Score.emerging_reasoning,
                Score.emerging_confidence,
                Score.composite_score,
                Score.tier,
                Score.check_size_low,
                Score.check_size_high,
                Score.is_anomaly,
            )
            .join(Organization, Contact.organization_id == Organization.id)
            .outerjoin(Score, Score.contact_id == Contact.id)
            .all()
        )

        if not query:
            return pd.DataFrame()

        df = pd.DataFrame(query, columns=[
            "Contact Name", "Role", "Email", "Contact Status", "Rel Depth Raw",
            "Organization", "Org Type", "Region", "AUM", "Investment Mandate",
            "Sustainability Focus", "Emerging Mgr Programs", "Is LP", "Enrichment Status",
            "Sector Fit", "Sector Fit Reasoning", "Sector Fit Confidence",
            "Relationship Depth", "Halo Value", "Halo Reasoning", "Halo Confidence",
            "Emerging Fit", "Emerging Reasoning", "Emerging Confidence",
            "Composite Score", "Tier", "Check Size Low", "Check Size High", "Anomaly",
        ])
        return df
    finally:
        session.close()


@st.cache_data(ttl=30)
def load_cost_data():
    session = get_session()
    try:
        costs = session.query(ApiCost).all()
        if not costs:
            return pd.DataFrame()
        return pd.DataFrame([{
            "Run ID": c.run_id,
            "Service": c.service,
            "Operation": c.operation,
            "Organization": c.organization,
            "Tokens In": c.tokens_input,
            "Tokens Out": c.tokens_output,
            "Cost ($)": c.estimated_cost,
            "Timestamp": c.timestamp,
        } for c in costs])
    finally:
        session.close()


def render_sidebar(df: pd.DataFrame):
    st.sidebar.title("Filters")

    tiers = st.sidebar.multiselect(
        "Tier", options=TIER_ORDER,
        default=TIER_ORDER,
    )
    org_types = sorted(df["Org Type"].dropna().unique().tolist())
    selected_org_types = st.sidebar.multiselect(
        "Org Type", options=org_types, default=org_types,
    )

    statuses = sorted(df["Contact Status"].dropna().unique().tolist())
    selected_statuses = st.sidebar.multiselect(
        "Contact Status", options=statuses, default=statuses,
    )

    score_range = st.sidebar.slider(
        "Composite Score Range", 1.0, 10.0, (1.0, 10.0), 0.5
    )

    is_lp_options = sorted(df["Is LP"].dropna().unique().tolist())
    selected_lp = st.sidebar.multiselect(
        "LP Status", options=is_lp_options, default=is_lp_options,
    )

    show_anomalies_only = st.sidebar.checkbox("Show anomalies only", False)

    return {
        "tiers": tiers,
        "org_types": selected_org_types,
        "statuses": selected_statuses,
        "score_range": score_range,
        "lp_status": selected_lp,
        "anomalies_only": show_anomalies_only,
    }


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)

    if filters["tiers"]:
        mask &= df["Tier"].isin(filters["tiers"])
    if filters["org_types"]:
        mask &= df["Org Type"].isin(filters["org_types"])
    if filters["statuses"]:
        mask &= df["Contact Status"].isin(filters["statuses"])
    if filters["lp_status"]:
        mask &= df["Is LP"].isin(filters["lp_status"])

    lo, hi = filters["score_range"]
    mask &= df["Composite Score"].fillna(0).between(lo, hi)

    if filters["anomalies_only"]:
        mask &= df["Anomaly"].notna() & (df["Anomaly"] != "")

    return df[mask]


def page_overview(df: pd.DataFrame):
    st.header("Pipeline Overview")

    scored = df[df["Composite Score"].notna()]
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Contacts", len(df))
    with col2:
        st.metric("Unique Organizations", df["Organization"].nunique())
    with col3:
        avg = scored["Composite Score"].mean() if len(scored) > 0 else 0
        st.metric("Avg Composite Score", f"{avg:.2f}")
    with col4:
        priority = len(scored[scored["Tier"] == "PRIORITY CLOSE"])
        st.metric("Priority Close", priority)

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Tier Distribution")
        if len(scored) > 0:
            tier_counts = scored["Tier"].value_counts().reindex(TIER_ORDER, fill_value=0)
            fig = px.bar(
                x=tier_counts.index, y=tier_counts.values,
                color=tier_counts.index,
                color_discrete_map=TIER_COLORS,
                labels={"x": "Tier", "y": "Count"},
            )
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Org Type Breakdown")
        if len(scored) > 0:
            org_tier = scored.groupby(["Org Type", "Tier"]).size().reset_index(name="Count")
            fig = px.bar(
                org_tier, x="Org Type", y="Count", color="Tier",
                color_discrete_map=TIER_COLORS,
                category_orders={"Tier": TIER_ORDER},
            )
            fig.update_layout(height=350, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Score Distributions")
        if len(scored) > 0:
            dims = ["Sector Fit", "Halo Value", "Emerging Fit", "Relationship Depth"]
            melted = scored[dims].melt(var_name="Dimension", value_name="Score")
            fig = px.box(melted, x="Dimension", y="Score", color="Dimension",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("LP Status Breakdown")
        if len(df) > 0:
            lp_counts = df["Is LP"].fillna("Not Enriched").value_counts()
            fig = px.pie(
                names=lp_counts.index, values=lp_counts.values,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)


def page_prospect_table(df: pd.DataFrame):
    st.header("Prospect Table")

    scored = df[df["Composite Score"].notna()].copy()
    if len(scored) == 0:
        st.warning("No scored prospects found. Run the pipeline first.")
        return

    scored = scored.sort_values("Composite Score", ascending=False)

    display_cols = [
        "Contact Name", "Organization", "Org Type", "Role",
        "Composite Score", "Tier", "Sector Fit", "Relationship Depth",
        "Halo Value", "Emerging Fit", "Is LP", "Contact Status", "Region",
    ]
    display_df = scored[display_cols].reset_index(drop=True)
    display_df.index = display_df.index + 1

    def color_tier(val):
        color = TIER_COLORS.get(val, "#666")
        return f"background-color: {color}; color: white; font-weight: bold"

    def color_score(val):
        try:
            v = float(val)
            if v >= 8:
                return "background-color: #10b981; color: white"
            elif v >= 6.5:
                return "background-color: #3b82f6; color: white"
            elif v >= 5:
                return "background-color: #f59e0b; color: white"
            else:
                return "background-color: #ef4444; color: white"
        except (ValueError, TypeError):
            return ""

    styled = display_df.style.map(
        color_tier, subset=["Tier"]
    ).map(
        color_score, subset=["Composite Score"]
    ).format({
        "Composite Score": "{:.2f}",
        "Sector Fit": "{:.1f}",
        "Relationship Depth": "{:.0f}",
        "Halo Value": "{:.1f}",
        "Emerging Fit": "{:.1f}",
    })

    st.dataframe(styled, use_container_width=True, height=600)

    st.divider()
    st.subheader("Detailed View")
    selected = st.selectbox(
        "Select a contact to view details:",
        scored["Contact Name"].tolist(),
    )

    if selected:
        row = scored[scored["Contact Name"] == selected].iloc[0]
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Contact:** {row['Contact Name']}")
            st.markdown(f"**Organization:** {row['Organization']}")
            st.markdown(f"**Role:** {row['Role']}")
            st.markdown(f"**Org Type:** {row['Org Type']}")
            st.markdown(f"**Is LP:** {row['Is LP']}")
            st.markdown(f"**AUM:** {row['AUM']}")

            if row["Check Size Low"] and row["Check Size High"]:
                low = row["Check Size Low"]
                high = row["Check Size High"]
                st.markdown(f"**Est. Check Size:** ${low:,.0f} – ${high:,.0f}")

        with col2:
            st.markdown(f"**Composite Score:** {row['Composite Score']:.2f}")
            st.markdown(f"**Tier:** {row['Tier']}")
            if row.get("Anomaly"):
                st.warning(f"Anomaly: {row['Anomaly']}")

        st.divider()

        dims = [
            ("Sector Fit", "Sector Fit Reasoning", "Sector Fit Confidence"),
            ("Halo Value", "Halo Reasoning", "Halo Confidence"),
            ("Emerging Fit", "Emerging Reasoning", "Emerging Confidence"),
        ]
        for score_col, reasoning_col, conf_col in dims:
            with st.expander(f"{score_col}: {row[score_col]:.1f} (Confidence: {row[conf_col]})"):
                st.write(row[reasoning_col])


def page_org_deep_dive(df: pd.DataFrame):
    st.header("Organization Deep Dive")

    orgs = sorted(df["Organization"].dropna().unique().tolist())
    selected_org = st.selectbox("Select an organization:", orgs)

    if not selected_org:
        return

    org_df = df[df["Organization"] == selected_org]
    first = org_df.iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Organization:** {selected_org}")
        st.markdown(f"**Type:** {first['Org Type']}")
        st.markdown(f"**Region:** {first['Region']}")
        st.markdown(f"**LP Status:** {first['Is LP']}")
    with col2:
        st.markdown(f"**AUM:** {first['AUM']}")
        st.markdown(f"**Enrichment Status:** {first['Enrichment Status']}")
    with col3:
        if first.get("Composite Score") and pd.notna(first["Composite Score"]):
            st.metric("Avg Composite", f"{org_df['Composite Score'].mean():.2f}")

    st.divider()
    st.subheader("Investment Mandate")
    st.write(first.get("Investment Mandate", "N/A"))

    st.subheader("Sustainability Focus")
    st.write(first.get("Sustainability Focus", "N/A"))

    st.subheader("Emerging Manager Programs")
    st.write(first.get("Emerging Mgr Programs", "N/A"))

    st.divider()
    st.subheader(f"Contacts at {selected_org}")

    contacts_display = org_df[[
        "Contact Name", "Role", "Email", "Contact Status",
        "Relationship Depth", "Composite Score", "Tier",
    ]].reset_index(drop=True)
    contacts_display.index = contacts_display.index + 1
    st.dataframe(contacts_display, use_container_width=True)


def page_analytics(df: pd.DataFrame):
    st.header("Analytics")

    scored = df[df["Composite Score"].notna()].copy()
    if len(scored) == 0:
        st.warning("No scored data available.")
        return

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Sector Fit vs. Relationship Depth")
        fig = px.scatter(
            scored,
            x="Sector Fit", y="Relationship Depth",
            size="Composite Score",
            color="Tier",
            color_discrete_map=TIER_COLORS,
            hover_data=["Contact Name", "Organization", "Composite Score"],
            category_orders={"Tier": TIER_ORDER},
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Halo Value vs. Emerging Fit")
        fig = px.scatter(
            scored,
            x="Halo Value", y="Emerging Fit",
            size="Composite Score",
            color="Tier",
            color_discrete_map=TIER_COLORS,
            hover_data=["Contact Name", "Organization", "Composite Score"],
            category_orders={"Tier": TIER_ORDER},
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Top 20 Prospects")
    top20 = scored.nlargest(20, "Composite Score")[[
        "Contact Name", "Organization", "Org Type",
        "Composite Score", "Tier", "Sector Fit",
        "Relationship Depth", "Halo Value", "Emerging Fit",
    ]].reset_index(drop=True)
    top20.index = top20.index + 1
    st.dataframe(top20, use_container_width=True)

    st.divider()
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.subheader("Confidence Distribution")
        conf_data = []
        for dim, col in [("Sector Fit", "Sector Fit Confidence"),
                         ("Halo Value", "Halo Confidence"),
                         ("Emerging Fit", "Emerging Confidence")]:
            counts = scored[col].fillna("Unknown").value_counts()
            for level, count in counts.items():
                conf_data.append({"Dimension": dim, "Confidence": level, "Count": count})
        if conf_data:
            conf_df = pd.DataFrame(conf_data)
            fig = px.bar(conf_df, x="Dimension", y="Count", color="Confidence",
                         barmode="group",
                         color_discrete_map={"High": "#10b981", "Medium": "#f59e0b", "Low": "#ef4444"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

    with col_c2:
        st.subheader("Anomalies")
        anomalies = scored[scored["Anomaly"].notna() & (scored["Anomaly"] != "")]
        if len(anomalies) > 0:
            st.warning(f"{len(anomalies)} anomalies detected")
            for _, row in anomalies.iterrows():
                with st.expander(f"{row['Contact Name']} @ {row['Organization']}"):
                    st.write(f"**Anomaly:** {row['Anomaly']}")
                    st.write(f"**Composite:** {row['Composite Score']:.2f} ({row['Tier']})")
        else:
            st.success("No anomalies detected")


def page_costs(df_costs: pd.DataFrame):
    st.header("API Cost Tracking")

    if df_costs.empty:
        st.info("No cost data available. Run the pipeline to generate cost data.")
        return

    total_cost = df_costs["Cost ($)"].sum()
    total_calls = len(df_costs)
    tavily_calls = len(df_costs[df_costs["Service"] == "tavily"])
    openai_calls = len(df_costs[df_costs["Service"] == "openai"])
    total_tokens = df_costs["Tokens In"].sum() + df_costs["Tokens Out"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Cost", f"${total_cost:.4f}")
    c2.metric("Total API Calls", total_calls)
    c3.metric("Tavily Searches", tavily_calls)
    c4.metric("OpenAI Calls", openai_calls)
    c5.metric("Total Tokens", f"{total_tokens:,}")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Cost by Service")
        by_service = df_costs.groupby("Service")["Cost ($)"].sum().reset_index()
        fig = px.pie(by_service, names="Service", values="Cost ($)",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Cost by Operation")
        by_op = df_costs.groupby("Operation")["Cost ($)"].sum().reset_index()
        fig = px.bar(by_op, x="Operation", y="Cost ($)",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Scaling Projections")

    unique_orgs = df_costs["Organization"].nunique()
    cost_per_org = total_cost / max(unique_orgs, 1)

    proj_data = []
    for scale in [100, 500, 1000, 2500, 5000]:
        est_orgs = int(scale * 0.85)
        proj_data.append({
            "Contacts": scale,
            "Est. Unique Orgs": est_orgs,
            "Est. Cost": f"${est_orgs * cost_per_org:.2f}",
        })
    st.table(pd.DataFrame(proj_data))


def page_csv_import():
    st.header("CSV Import & Re-run")

    uploaded = st.file_uploader("Upload a new prospects CSV", type=["csv"])

    if uploaded:
        preview = pd.read_csv(uploaded)
        st.subheader("Preview")
        st.dataframe(preview.head(20), use_container_width=True)
        st.info(f"File contains {len(preview)} rows and {len(preview.columns)} columns")

        required = {"Contact Name", "Organization", "Org Type", "Role",
                    "Email", "Region", "Contact Status", "Relationship Depth"}
        missing = required - set(preview.columns.str.strip())
        if missing:
            st.error(f"Missing required columns: {missing}")
        else:
            st.success("All required columns present")

            if st.button("Ingest & Score", type="primary"):
                import tempfile, os
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name

                try:
                    from src.pipeline import Pipeline
                    with st.spinner("Running pipeline..."):
                        pipeline = Pipeline()
                        results = pipeline.run(csv_path=tmp_path)
                    st.success("Pipeline completed!")
                    st.json(results)
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")
                finally:
                    os.unlink(tmp_path)


def main():
    st.sidebar.title("LP Prospect Engine")
    st.sidebar.markdown("*PaceZero Capital Partners*")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "Prospect Table", "Organization Deep Dive",
         "Analytics", "Cost Tracking", "CSV Import"],
    )

    df = load_data()

    if df.empty and page not in ("CSV Import", "Cost Tracking"):
        st.warning(
            "No data found. Please run the pipeline first:\n\n"
            "```\npython scripts/run_pipeline.py --csv challenge_contacts.csv\n```\n\n"
            "Or use the CSV Import page to upload and process a file."
        )
        return

    if not df.empty:
        filters = render_sidebar(df)
        filtered = apply_filters(df, filters)
        st.sidebar.divider()
        st.sidebar.markdown(f"**Showing:** {len(filtered)} / {len(df)} contacts")
    else:
        filtered = df

    if page == "Overview":
        page_overview(filtered)
    elif page == "Prospect Table":
        page_prospect_table(filtered)
    elif page == "Organization Deep Dive":
        page_org_deep_dive(filtered)
    elif page == "Analytics":
        page_analytics(filtered)
    elif page == "Cost Tracking":
        df_costs = load_cost_data()
        page_costs(df_costs)
    elif page == "CSV Import":
        page_csv_import()


if __name__ == "__main__":
    main()
