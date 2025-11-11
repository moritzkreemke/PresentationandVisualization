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


def render_country_deep_dive(data: pd.DataFrame, portfolio: pd.DataFrame, premium_by_peril: pd.DataFrame, selected_country: str):
    """Render the country deep dive page with detailed analysis."""
    
    # ====================
    # IMPROVED HEADER SECTION
    # ====================
    
    # Back button with improved styling
    col_back, col_header = st.columns([1, 11])
    with col_back:
        if st.button("← Back", type="secondary", use_container_width=True):
            st.session_state.selected_country = "All Europe"
            st.switch_page("pages/1_Overview.py")
    
    with col_header:
        st.markdown(f"""
            <div style='padding: 0.5rem 0; margin-bottom: 0.5rem; border-bottom: 1px solid #e0e0e0;'>
                <h1 style='color: #2c3e50; margin: 0; font-size: 1.8rem; font-weight: 600;'>
                    {selected_country} Risk Profile
                </h1>
                <p style='color: #7f8c8d; margin: 0.3rem 0 0 0; font-size: 0.9rem;'>
                    Comprehensive Natural Disaster Analysis & Insurance Intelligence
                </p>
            </div>
        """, unsafe_allow_html=True)

    # Filter data for selected country
    df_country = data[data['country'] == selected_country].copy()

    if len(df_country) == 0:
        st.warning(f"No disaster data available for {selected_country}")
        return

    # ====================
    # CALCULATE ALL METRICS FIRST
    # ====================
    
    # Peril metrics
    peril_freq = df_country['event_type'].value_counts()
    most_frequent = peril_freq.index[0] if len(peril_freq) > 0 else "N/A"
    freq_pct = (peril_freq.iloc[0] / len(df_country) * 100) if len(peril_freq) > 0 else 0

    peril_severity = df_country.groupby('event_type')['severity'].mean().sort_values(ascending=False)
    most_severe = peril_severity.index[0] if len(peril_severity) > 0 else "N/A"
    severity_avg = peril_severity.iloc[0] if len(peril_severity) > 0 else 0

    peril_cost = df_country.groupby('event_type')['economic_impact_million_usd'].sum().sort_values(ascending=False)
    most_costly = peril_cost.index[0] if len(peril_cost) > 0 else "N/A"
    cost_total = peril_cost.iloc[0] / 1000 if len(peril_cost) > 0 else 0

    # Risk trend calculation
    df_country['decade'] = (df_country['year'] // 20) * 20
    decade_counts = df_country.groupby('decade').size()
    if len(decade_counts) >= 2:
        recent_decade = decade_counts.iloc[-1]
        previous_decade = decade_counts.iloc[-2]
        trend_pct = ((recent_decade - previous_decade) / previous_decade * 100) if previous_decade > 0 else 0
        trend_direction = "↗️" if trend_pct > 0 else "↘️" if trend_pct < 0 else "→"
    else:
        trend_pct = 0
        trend_direction = "→"

    # Extract month for seasonal analysis
    df_country['month'] = pd.to_datetime(df_country['date']).dt.month

    # ====================
    # NEW LAYOUT: HEATMAP LEFT, METRICS RIGHT
    # ====================
    
    
    
    
    # Create two columns: 60% for heatmap, 40% for metrics
    col_heatmap, col_metrics = st.columns([4, 1])
    
    # LEFT COLUMN: SEASONAL HEATMAP
    with col_heatmap:
        st.markdown("####  Seasonal Event Count")
        
        # Create heatmap data
        perils_for_heatmap = df_country['event_type'].value_counts().head(5).index.tolist()
        heatmap_data = []

        for peril in perils_for_heatmap:
            monthly_counts = df_country[df_country['event_type'] == peril].groupby('month').size()
            row = [monthly_counts.get(m, 0) for m in range(1, 13)]
            heatmap_data.append(row)

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=perils_for_heatmap,
            colorscale='RdYlBu_r',
            hovertemplate='<b>%{y}</b><br>%{x}: %{z} events<extra></extra>',
            colorbar=dict(title="Events")
        ))

        fig_heatmap.update_layout(
            height=400,
            xaxis_title="Month",
            yaxis_title="",
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(size=12)
        )

        st.plotly_chart(fig_heatmap, use_container_width=True)


        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Human Impact Distribution")
            total_deaths = df_country['Total Deaths'].sum()
            total_injured = df_country['No. Injured'].sum()
            total_affected = df_country['No. Affected'].sum()

            fig_pie = go.Figure(data=[go.Pie(
                labels=['Total Deaths', 'No. Injured', 'No. Affected'],
                values=[total_deaths, total_injured, total_affected],
                hole=0.3,
                marker_colors=['#d62728', '#ff9896', '#ffbb78']
            )])
            fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)

            total = total_deaths + total_injured + total_affected
            if total > 0:
                affected_pct = (total_affected / total * 100)
                if affected_pct > 60:
                    st.caption("⚠️ High 'Affected' percentage suggests significant health insurance exposure")

        with col2:
            st.markdown("#### Damage Distribution by Peril")
            damage_by_peril = df_country.groupby('event_type')['economic_impact_million_usd'].sum().sort_values(ascending=False)

            fig_bar = go.Figure(data=[go.Bar(
                x=damage_by_peril.values / 1000,
                y=damage_by_peril.index,
                orientation='h',
                marker_color='#1f77b4'
            )])
            fig_bar.update_layout(
                height=300,
                xaxis_title="Total Damage ($B)",
                yaxis_title="",
                margin=dict(l=0, r=0, t=20, b=0)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            if len(damage_by_peril) > 0:
                top_peril = damage_by_peril.index[0]
                st.caption(f"💼 {top_peril} damage dominance indicates homeowners insurance should focus on {top_peril.lower()} coverage")

        st.markdown("---")
    
    # RIGHT COLUMN: KEY METRICS
    with col_metrics:
        st.markdown("")  # Empty - metrics start immediately

        # Base style for all cards
        card_style = """
            padding: 1.5rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            background-color: #ffffff;
            color: #111827;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        """

        label_style = """
            font-size: 0.8rem;
            font-weight: 600;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.3rem;
        """

        value_style = """
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
            color: #111827;
        """

        subtext_style = """
            font-size: 0.95rem;
            opacity: 0.75;
        """

        # Metric card 1: Most Frequent
        st.markdown(f"""
            <div style='{card_style}'>
                <div style='{label_style}'>Most Frequent Peril</div>
                <div style='{value_style}'>{most_frequent}</div>
                <div style='{subtext_style}'>↑ {freq_pct:.0f}% of all events</div>
            </div>
        """, unsafe_allow_html=True)

        # Metric card 2: Most Severe
        st.markdown(f"""
            <div style='{card_style}'>
                <div style='{label_style}'>Highest Severity</div>
                <div style='{value_style}'>{most_severe}</div>
                <div style='{subtext_style}'>⚠️ Average: {severity_avg:.1f}/10</div>
            </div>
        """, unsafe_allow_html=True)

        # Metric card 3: Most Costly
        st.markdown(f"""
            <div style='{card_style}'>
                <div style='{label_style}'>Highest Economic Impact</div>
                <div style='{value_style}'>{most_costly}</div>
                <div style='{subtext_style}'>💰 ${cost_total:.1f}B total damage</div>
            </div>
        """, unsafe_allow_html=True)

        # Risk trend
        trend_color = "#ef4444" if trend_pct > 0 else "#10b981" if trend_pct < 0 else "#6b7280"
        st.markdown(f"""
            <div style='{card_style} border-left: 5px solid {trend_color};'>
                <div style='{label_style}'>Risk Trend</div>
                <div style='font-size: 1.8rem; font-weight: 700; margin-bottom: 0.3rem;'>{trend_direction} {abs(trend_pct):.0f}%</div>
                <div style='{subtext_style}'>{'Increase' if trend_pct > 0 else 'Decrease'} in events<br>(last two decades)</div>
            </div>
        """, unsafe_allow_html=True)


    

    

# Set page configuration
st.set_page_config(layout="wide", page_title="Country Deep Dive - EuroShield")

# Custom CSS
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
    </style>
""", unsafe_allow_html=True)

# Load data
data, portfolio, premium_by_peril, merged_data = load_data()

# Initialize session state
if 'deep_dive_peril' not in st.session_state:
    st.session_state.deep_dive_peril = 'All Perils'

# Check if a country has been selected
if 'selected_country' not in st.session_state or st.session_state.selected_country == "All Europe":
    st.warning("Please select a specific country from the overview page to view the deep dive.")
    if st.button("← Go to Overview"):
        st.switch_page("pages/1_Overview.py")
    st.stop()

# Header


# Render the deep dive analysis
render_country_deep_dive(data, portfolio, premium_by_peril, st.session_state.selected_country)

# Footer
st.caption("""
    📊 **EuroShield Insurance Group** | Climate Risk Analytics Division  
    Data Source: EM-DAT (Emergency Events Database) - CRED / UCLouvain, Brussels, Belgium  
    Dashboard covers historical disaster events across European markets
    """)