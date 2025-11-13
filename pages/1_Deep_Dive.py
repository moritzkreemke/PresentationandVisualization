import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_loader import load_data

try:
    from streamlit_plotly_events import plotly_events
except ImportError:
    plotly_events = None


def render_country_deep_dive(data: pd.DataFrame, portfolio: pd.DataFrame, premium_by_peril: pd.DataFrame,
                             selected_country: str):
    """Render the country deep dive page with detailed analysis."""

    col_back, col_header = st.columns([1, 11])
    with col_back:
        if st.button("← Back", type="secondary", width='stretch'):
            st.session_state.selected_country = "All Europe"
            st.switch_page("0_Overview.py")

    with col_header:
        st.markdown(f"""
            <div class="main-header">{selected_country} Risk Profile</div>
        """, unsafe_allow_html=True)


    # Filter data for selected country
    df_country = data[data['country'] == selected_country].copy()

    if len(df_country) == 0:
        st.warning(f"No disaster data available for {selected_country}")
        return

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
    else:
        trend_pct = 0

    # Extract month for seasonal analysis
    df_country['month'] = pd.to_datetime(df_country['date']).dt.month

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
            colorscale=[[0, 'rgb(255,230,230)'], [1, 'rgb(139,0,0)']],
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

        st.plotly_chart(fig_heatmap, width='stretch')

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Human Impact Distribution")
            total_deaths = df_country['Total Deaths'].sum()
            total_injured = df_country['No. Injured'].sum()
            total_affected = df_country['No. Affected'].sum()

            labels = ['Total Deaths', 'No. Injured', 'No. Affected']
            values = [total_deaths, total_injured, total_affected]
            colors = ['#d62728', '#ff9896', '#ffbb78']

            fig_bar = go.Figure(data=[go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                text=values,
                texttemplate='%{text:.2s}',
                textposition='auto',
            )])
            
            fig_bar.update_layout(
                height=300, 
                margin=dict(l=0, r=0, t=20, b=0),
                yaxis_title="Total People",
                showlegend=False
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)

            total = total_deaths + total_injured + total_affected
            if total > 0:
                affected_pct = (total_affected / total * 100)
                if affected_pct > 60:
                    st.caption("Significant health risk exposure")
        
        with col2:
            st.markdown("#### Damage Distribution by Peril")
            damage_by_peril = df_country.groupby('event_type')['economic_impact_million_usd'].sum().sort_values(
                ascending=False)

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
            st.plotly_chart(fig_bar, width='stretch')

            if len(damage_by_peril) > 0:
                top_peril = damage_by_peril.index[0]
                st.caption(
                    f"Primary risk: {top_peril.lower()}")

        

    # RIGHT COLUMN: KEY METRICS
    with col_metrics:
        st.markdown("")

        # Unified design style
        accent_color = "#1E3A8A"  # deep navy blue – calm, professional

        card_style = f"""
            padding: 1.8rem;
            border-radius: 16px;
            margin-bottom: 1.2rem;
            background-color: #ffffff;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            border-left: 6px solid {accent_color};
            transition: all 0.3s ease;
        """

        label_style = """
            font-size: 0.8rem;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.3rem;
        """

        value_style = """
            font-size: 1.1rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.2rem;
        """

        number_style = f"""
            font-size: 3rem;
            font-weight: 800;
            color: {accent_color};
            margin: 0.4rem 0 0.8rem 0;
            line-height: 1;
        """

        subtext_style = """
            font-size: 0.95rem;
            color: #4b5563;
            opacity: 0.8;
        """

        # Most Frequent Peril
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">Most Frequent Peril</div>
                <div style="{value_style}">{most_frequent}</div>
                <div style="{number_style}">{freq_pct:.0f}%</div>
                <div style="{subtext_style}">of all recorded events</div>
            </div>
        """, unsafe_allow_html=True)

        # Highest Severity
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">Highest Severity</div>
                <div style="{value_style}">{most_severe}</div>
                <div style="{number_style}">{severity_avg:.1f}/10</div>
                <div style="{subtext_style}">average severity score</div>
            </div>
        """, unsafe_allow_html=True)

        # Highest Economic Impact
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{label_style}">Highest Economic Impact</div>
                <div style="{value_style}">{most_costly}</div>
                <div style="{number_style}">${cost_total:.1f}B</div>
                <div style="{subtext_style}">total damage</div>
            </div>
        """, unsafe_allow_html=True)

        # Risk Trend
        trend_color = "#10B981" if trend_pct < 0 else "#EF4444" if trend_pct > 0 else "#6B7280"
        trend_icon = "↘" if trend_pct < 0 else "↗" if trend_pct > 0 else "→"
        trend_text = "Decrease" if trend_pct < 0 else "Increase" if trend_pct > 0 else "Stable"

        st.markdown(f"""
            <div style="{card_style} border-left: 6px solid {trend_color};">
                <div style="{label_style}">Risk Trend</div>
                <div style="{value_style}">{trend_text}</div>
                <div style="font-size: 3rem; font-weight: 800; color:{trend_color}; margin: 0.4rem 0 0.8rem 0; line-height: 1;">
                    {trend_icon} {abs(trend_pct):.0f}%
                </div>
                <div style="{subtext_style}">change in events (last 2 decades)</div>
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
        font-weight: bold;
        color: #1f4788;
        margin-bottom: 1rem;
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

# Render the deep dive analysis
render_country_deep_dive(data, portfolio, premium_by_peril, st.session_state.selected_country)

