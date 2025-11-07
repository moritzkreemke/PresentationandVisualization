import streamlit as st
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_loader import load_data

try:
    from streamlit_plotly_events import plotly_events
except ImportError:
    plotly_events = None


def render_country_deep_dive(data: pd.DataFrame, portfolio: pd.DataFrame, selected_country: str):
    """Render the country deep dive page with detailed analysis."""
    st.markdown("---")
    # Back button and title
    top_cols = st.columns([1, 6, 3])
    with top_cols[0]:
        if st.button("← Back to Overview", use_container_width=True):
            st.session_state.deep_dive_peril = 'All Perils'
            st.switch_page("pages/1_Overview.py")
    with top_cols[1]:
        st.markdown(f"### Deep Dive: {selected_country}")
    with top_cols[2]:
        # Breadcrumb
        peril_bc = st.session_state.get('deep_dive_peril', 'All Perils')
        trail = f"{selected_country}" + (f" > {peril_bc}" if peril_bc and peril_bc != 'All Perils' else "")
        st.caption(trail)

    # Filter data for selected country and years 2020-2025
    df_all = data[(data['country'] == selected_country) & (data['year'] >= 2020) & (data['year'] <= 2025)].copy()

    # Apply peril filter if set
    peril_filter = st.session_state.get('deep_dive_peril', 'All Perils')
    df = df_all.copy()
    if peril_filter and peril_filter != 'All Perils':
        df = df[df['event_type'] == peril_filter]

    # Fetch market share
    mkt = portfolio[portfolio['country'] == selected_country]
    market_share = mkt['market_share_percent'].iloc[0] if not mkt.empty else 0.0

    # KPI calculations
    total_events = int(len(df_all))
    total_impact = float(df_all['economic_impact_million_usd'].sum()) if len(df_all) else 0.0
    est_insured_loss = total_impact * (market_share / 100.0)
    if len(df_all) and 'event_type' in df_all.columns:
        sev_means = df_all.groupby('event_type')['severity'].mean()
        most_severe_peril = sev_means.idxmax() if not sev_means.empty else '—'
    else:
        most_severe_peril = '—'

    # Display KPI cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total Events (2020–2025)", f"{total_events:,}")
    with k2:
        st.metric("Total Economic Impact", f"${total_impact:,.0f}M")
    with k3:
        st.metric("Est. EuroShield Insured Loss", f"${est_insured_loss:,.0f}M")
    with k4:
        st.metric("Most Severe Peril", most_severe_peril)

    st.markdown("---")

    # Component 2: Peril Impact Breakdown (Treemap)
    st.subheader("Peril Impact Breakdown")
    df_peril = df_all.copy()
    if len(df_peril) > 0:
        peril_group = df_peril.groupby('event_type').agg(
            total_impact=('economic_impact_million_usd', 'sum'),
            avg_severity=('severity', 'mean')
        ).reset_index()
        if len(peril_group) == 0:
            st.info("No peril breakdown available.")
        else:
            fig_tree = px.treemap(
                peril_group,
                path=['event_type'],
                values='total_impact',
                color='avg_severity',
                color_continuous_scale=["#fff7bc", "#fee391", "#fec44f", "#fe9929", "#d95f0e", "#993404"],
                hover_data={'total_impact': ':.1f', 'avg_severity': ':.1f'},
                title=''
            )
            fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=360, coloraxis_colorbar=dict(title="Avg Severity"))
            clicked = None
            used_click_capture = False
            if plotly_events is not None:
                used_click_capture = True
                sel = plotly_events(fig_tree, click_event=True, hover_event=False, select_event=False, override_width="100%", override_height=380)
                if sel:
                    clicked = sel[0].get('label')
            else:
                st.plotly_chart(fig_tree, use_container_width=True)
            c1, c2, c3 = st.columns([2,2,6])
            with c1:
                if st.button("Show All Perils"):
                    st.session_state.deep_dive_peril = 'All Perils'
                    st.rerun()
            with c2:
                if not used_click_capture:
                    options = ['All Perils'] + sorted(peril_group['event_type'].unique().tolist())
                    chosen = st.selectbox("Filter by peril", options, index=options.index(peril_filter) if peril_filter in options else 0)
                    if chosen != peril_filter:
                        st.session_state.deep_dive_peril = chosen
                        st.rerun()
            if clicked:
                st.session_state.deep_dive_peril = clicked
                st.rerun()
    else:
        st.info("No events found for the selected period.")

    st.markdown("---")

    # Component 3: Damage Profile Over Time (Stacked Bars + Line)
    st.subheader("Damage Profile Over Time")
    df_time = df_all.copy()
    if peril_filter and peril_filter != 'All Perils':
        df_time = df_time[df_time['event_type'] == peril_filter]
    if len(df_time) > 0:
        yearly = df_time.groupby('year').agg(
            deaths=('Total Deaths', 'sum'),
            injured=('No. Injured', 'sum'),
            econ=('economic_impact_million_usd', 'sum')
        ).reset_index()
        fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_combo.add_bar(x=yearly['year'], y=yearly['deaths'], name='Deaths', marker_color='#d62728')
        fig_combo.add_bar(x=yearly['year'], y=yearly['injured'], name='Injuries', marker_color='#ff9896')
        fig_combo.add_trace(
            go.Scatter(
                x=yearly['year'], y=yearly['econ'], mode='lines+markers', name='Economic Impact ($M)',
                line=dict(color='#1f77b4', width=3)
            ), secondary_y=True
        )
        fig_combo.update_layout(barmode='stack', height=420, legend=dict(orientation='h'))
        fig_combo.update_xaxes(title_text="Year")
        fig_combo.update_yaxes(title_text="Total Casualties", secondary_y=False)
        fig_combo.update_yaxes(title_text="Economic Impact ($M)", secondary_y=True)
        st.plotly_chart(fig_combo, use_container_width=True)
    else:
        st.info("No time-series data for this selection.")

    st.markdown("---")

    # Component 4: Response Time vs. Damage Analysis (Scatter)
    st.subheader("Response Time vs. Damage Analysis")
    df_scatter = df_all.copy()
    if peril_filter and peril_filter != 'All Perils':
        df_scatter = df_scatter[df_scatter['event_type'] == peril_filter]
    if len(df_scatter) > 0 and 'response_time_hours' in df_scatter.columns and 'infrastructure_damage_score' in df_scatter.columns:
        fig_sc = px.scatter(
            df_scatter,
            x='response_time_hours',
            y='infrastructure_damage_score',
            color='event_type',
            hover_name='event_type',
            hover_data={'response_time_hours': ':.0f', 'infrastructure_damage_score': ':.1f', 'event_type': False},
            labels={'response_time_hours': 'Response Time (hours)', 'infrastructure_damage_score': 'Infrastructure Damage Score (0–10)'}
        )
        fig_sc.update_traces(marker=dict(size=9, opacity=0.8))
        fig_sc.update_layout(height=400)
        st.plotly_chart(fig_sc, use_container_width=True)
        st.caption("Note: Response time approximated from event duration due to data limitations.")
    else:
        st.info("Response vs. damage data not available for this selection.")

    st.markdown("---")

    # Component 5: Catastrophic Events Table
    st.subheader("Catastrophic Events")
    df_tbl = df_all.copy()
    if peril_filter and peril_filter != 'All Perils':
        df_tbl = df_tbl[df_tbl['event_type'] == peril_filter]
    if len(df_tbl) > 0:
        df_tbl['Total Casualties'] = df_tbl['Total Deaths'].fillna(0) + df_tbl['No. Injured'].fillna(0)
        df_tbl['Year'] = df_tbl['year'].astype(int)
        df_tbl['Month'] = pd.to_datetime(df_tbl['date']).dt.month_name()
        df_tbl['Economic Impact (€M)'] = df_tbl['economic_impact_million_usd']
        def _mk_url(row):
            q = f"{row['Year']}+{row['Month']}+{selected_country}+{row['event_type']}"
            return f"https://www.google.com/search?q={q.replace(' ', '+')}"
        df_tbl['Investigate'] = df_tbl.apply(_mk_url, axis=1)
        show_cols = ['date', 'event_type', 'severity', 'Economic Impact (€M)', 'Total Casualties', 'Investigate']
        rename = {'date': 'Date', 'event_type': 'Event Type', 'severity': 'Severity (1-10)'}
        table = df_tbl[show_cols].rename(columns=rename).sort_values(by='Economic Impact (€M)', ascending=False)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Investigate': st.column_config.LinkColumn("Investigate", display_text="Search"),
                'Economic Impact (€M)': st.column_config.NumberColumn(format="%.0f")
            }
        )
    else:
        st.info("No events to display for the selected filters.")

# Set page configuration
st.set_page_config(layout="wide", page_title="Country Deep Dive - EuroShield")

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f4788;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f4788;
    }
    </style>
""", unsafe_allow_html=True)

# Load data via helper module
data, portfolio, premium_by_peril, merged_data = load_data()

# Initialize session state for deep dive
if 'deep_dive_peril' not in st.session_state:
    st.session_state.deep_dive_peril = 'All Perils'

# Check if a country has been selected
if 'selected_country' not in st.session_state or st.session_state.selected_country == "All Europe":
    st.warning("Please select a specific country from the overview page to view the deep dive.")
    if st.button("← Go to Overview"):
        st.switch_page("pages/1_Overview.py")
    st.stop()

# Header
st.markdown('<div class="main-header">🔍 Country Deep Dive</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Last Updated: {datetime.now().strftime("%B %Y")} | Data Source: EM-DAT International Disaster Database</div>',
    unsafe_allow_html=True)

# Render the deep dive analysis
render_country_deep_dive(data, portfolio, st.session_state.selected_country)

# Footer
st.caption("""
    📊 **EuroShield Insurance Group** | Climate Risk Analytics Division  
    Data Source: EM-DAT (Emergency Events Database) - CRED / UCLouvain, Brussels, Belgium  
    Dashboard covers historical disaster events across European markets
    """)
