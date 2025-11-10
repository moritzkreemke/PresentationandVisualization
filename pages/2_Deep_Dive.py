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
    st.markdown("---")

    # Back button and title
    top_cols = st.columns([1, 8])
    with top_cols[0]:
        if st.button("← Back", width='stretch'):
            st.session_state.selected_country = "All Europe"
            st.switch_page("pages/1_Overview.py")
    with top_cols[1]:
        st.markdown(f"### 🏴 {selected_country} - Risk Profile")

    # Filter data for selected country (ALL historical data, not just 2020-2025)
    df_country = data[data['country'] == selected_country].copy()

    if len(df_country) == 0:
        st.warning(f"No disaster data available for {selected_country}")
        return

    # ====================
    # SECTION 1: COUNTRY RISK SNAPSHOT
    # ====================
    st.markdown("### 📊 Country Risk Snapshot")

    # Calculate metrics
    peril_freq = df_country['event_type'].value_counts()
    most_frequent = peril_freq.index[0] if len(peril_freq) > 0 else "N/A"
    freq_pct = (peril_freq.iloc[0] / len(df_country) * 100) if len(peril_freq) > 0 else 0

    peril_severity = df_country.groupby('event_type')['severity'].mean().sort_values(ascending=False)
    most_severe = peril_severity.index[0] if len(peril_severity) > 0 else "N/A"
    severity_avg = peril_severity.iloc[0] if len(peril_severity) > 0 else 0

    peril_cost = df_country.groupby('event_type')['economic_impact_million_usd'].sum().sort_values(ascending=False)
    most_costly = peril_cost.index[0] if len(peril_cost) > 0 else "N/A"
    cost_total = peril_cost.iloc[0] / 1000 if len(peril_cost) > 0 else 0  # Convert to billions

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

    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #1f77b4;'>
            <h4 style='margin: 0; color: #666;'>Most Frequent Peril</h4>
            <h2 style='margin: 0.5rem 0; color: #1f77b4;'>{most_frequent}</h2>
            <p style='margin: 0; color: #666;'>{freq_pct:.0f}% of events</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #d62728;'>
            <h4 style='margin: 0; color: #666;'>Most Severe Peril</h4>
            <h2 style='margin: 0.5rem 0; color: #d62728;'>{most_severe}</h2>
            <p style='margin: 0; color: #666;'>Avg: {severity_avg:.1f}/10</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style='background-color: #f0f2f6; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #ff7f0e;'>
            <h4 style='margin: 0; color: #666;'>Most Costly Peril</h4>
            <h2 style='margin: 0.5rem 0; color: #ff7f0e;'>{most_costly}</h2>
            <p style='margin: 0; color: #666;'>${cost_total:.1f}B total</p>
        </div>
        """, unsafe_allow_html=True)

    st.info(f"**Risk Trend:** {trend_direction} {abs(trend_pct):.0f}% {'increase' if trend_pct > 0 else 'decrease'} in events (comparing last two decades)")

    st.markdown("---")

    # ====================
    # SECTION 2: PORTFOLIO VS RISK ALIGNMENT
    # ====================
    st.markdown("### 🎯 Portfolio vs. Risk Alignment")

    # Get portfolio data for this country
    country_portfolio = portfolio[portfolio['country'] == selected_country]

    if len(country_portfolio) > 0:
        # Calculate country's share of total premium to estimate peril-specific premiums
        country_premium_total = country_portfolio['annual_premium_eur_million'].iloc[0]

        # Estimate country's peril premiums proportionally from total premium by peril
        premium_by_peril_copy = premium_by_peril.copy()
        premium_by_peril_copy.columns = ['event_type', 'premium_million_eur']
        total_premium_all = premium_by_peril_copy['premium_million_eur'].sum()

        # Distribute country premium across perils based on global distribution
        country_premium = premium_by_peril_copy.copy()
        country_premium['premium_million_eur'] = (
            country_premium['premium_million_eur'] / total_premium_all * country_premium_total
        )

        # Calculate historical event frequency by peril
        event_freq = df_country['event_type'].value_counts().reset_index()
        event_freq.columns = ['event_type', 'event_count']

        # Calculate average economic impact
        avg_impact = df_country.groupby('event_type')['economic_impact_million_usd'].mean().reset_index()
        avg_impact.columns = ['event_type', 'avg_impact']

        # Merge data
        alignment = country_premium.merge(event_freq, on='event_type', how='outer').fillna(0)
        alignment = alignment.merge(avg_impact, on='event_type', how='left').fillna(0)

        # Create scatter plot
        fig_align = go.Figure()

        for _, row in alignment.iterrows():
            # Determine color based on alignment
            if row['premium_million_eur'] > 0 and row['event_count'] > 0:
                color = '#2ca02c'  # Green - good alignment
            elif row['premium_million_eur'] > 50 and row['event_count'] < 5:
                color = '#ffbb33'  # Yellow - high premium, low frequency
            elif row['event_count'] > 20 and row['premium_million_eur'] < 20:
                color = '#d62728'  # Red - high frequency, low premium
            else:
                color = '#7f7f7f'  # Gray - other

            fig_align.add_trace(go.Scatter(
                x=[row['event_count']],
                y=[row['premium_million_eur']],
                mode='markers+text',
                marker=dict(size=max(row['avg_impact']/10, 10), color=color, opacity=0.7),
                text=row['event_type'],
                textposition='top center',
                name=row['event_type'],
                showlegend=False,
                hovertemplate=f"<b>{row['event_type']}</b><br>Events: {row['event_count']:.0f}<br>Premium: €{row['premium_million_eur']:.0f}M<br>Avg Impact: ${row['avg_impact']:.0f}M<extra></extra>"
            ))

        fig_align.update_layout(
            xaxis_title="Historical Event Frequency",
            yaxis_title="EuroShield Premium (€M)",
            height=450,
            hovermode='closest'
        )

        st.plotly_chart(fig_align, width='stretch')

        # Insights
        st.markdown("**Strategic Insights:**")
        insights_shown = 0
        for _, row in alignment.iterrows():
            if row['event_count'] > 0 and row['premium_million_eur'] > 0:
                event_pct = row['event_count'] / df_country.shape[0] * 100
                premium_pct = row['premium_million_eur'] / alignment['premium_million_eur'].sum() * 100
                if abs(event_pct - premium_pct) > 10:
                    st.caption(f"• {row['event_type']}: {event_pct:.0f}% of events but {premium_pct:.0f}% of premium - {'underweight' if premium_pct < event_pct else 'overweight'} in portfolio")
                    insights_shown += 1

        if insights_shown == 0:
            st.caption("• Portfolio allocation aligns well with historical risk distribution")
    else:
        st.info("No premium data available for this country.")

    st.markdown("---")

    # ====================
    # SECTION 3: SEASONAL PATTERNS
    # ====================
    st.markdown("### 📅 Seasonal Risk Calendar")

    # Extract month from date
    df_country['month'] = pd.to_datetime(df_country['date']).dt.month

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
        colorscale='YlOrRd',
        hovertemplate='%{y}<br>%{x}: %{z} events<extra></extra>'
    ))

    fig_heatmap.update_layout(
        height=300,
        xaxis_title="Month",
        yaxis_title="Peril Type",
        margin=dict(l=0, r=0, t=20, b=0)
    )

    st.plotly_chart(fig_heatmap, width='stretch')

    # Find peak risk months
    month_totals = df_country.groupby('month').size().sort_values(ascending=False)
    peak_month = pd.to_datetime(f'2024-{int(month_totals.index[0]):02d}-01').strftime('%B') if len(month_totals) > 0 else "N/A"
    st.info(f"**Strategic Insight:** Peak risk period is **{peak_month}** - ensure reinsurance coverage is in place before this period.")

    st.markdown("---")

    # ====================
    # SECTION 4: IMPACT ANALYSIS
    # ====================
    st.markdown("### 💥 Impact Distribution Analysis")

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
        st.plotly_chart(fig_pie, width='stretch')

        # Business interpretation
        total = total_deaths + total_injured + total_affected
        if total > 0:
            affected_pct = (total_affected / total * 100)
            if affected_pct > 60:
                st.caption("⚠️ High 'Affected' percentage suggests significant health insurance exposure")

    with col2:
        st.markdown("#### Damage Distribution by Peril")
        damage_by_peril = df_country.groupby('event_type')['economic_impact_million_usd'].sum().sort_values(ascending=False)

        fig_bar = go.Figure(data=[go.Bar(
            x=damage_by_peril.values / 1000,  # Convert to billions
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

        # Business interpretation
        if len(damage_by_peril) > 0:
            top_peril = damage_by_peril.index[0]
            st.caption(f"💼 {top_peril} damage dominance indicates homeowners insurance should focus on {top_peril.lower()} coverage")

    st.markdown("---")

    # ====================
    # SECTION 5: MAJOR HISTORICAL EVENTS
    # ====================
    st.markdown("### 🔍 Most Significant Disasters")

    # Prepare table data
    df_events = df_country.copy()
    df_events['Total Impact Score'] = (
        df_events['Total Deaths'].fillna(0) * 100 +
        df_events['No. Affected'].fillna(0) +
        df_events['economic_impact_million_usd'].fillna(0)
    )

    df_events = df_events.sort_values('Total Impact Score', ascending=False).head(20)

    # Format columns
    df_events['Date'] = pd.to_datetime(df_events['date']).dt.strftime('%b %Y')
    df_events['Deaths'] = df_events['Total Deaths'].fillna(0).astype(int)
    df_events['Affected'] = df_events['No. Affected'].fillna(0).astype(int)
    df_events['Damage ($M)'] = df_events['economic_impact_million_usd'].fillna(0).round(0).astype(int)

    # Create Google search links
    def make_search_url(row):
        # Check for Location column (with capital L from original data)
        location_col = 'Location' if 'Location' in df_events.columns else ('location' if 'location' in df_events.columns else None)
        location = row[location_col] if location_col and pd.notna(row.get(location_col)) else selected_country
        query = f"{row['Date']} {selected_country} {row['event_type']} {location} disaster"
        return f"https://www.google.com/search?q={query.replace(' ', '+')}"

    df_events['Learn More'] = df_events.apply(make_search_url, axis=1)

    # Select and display columns - check if Location exists
    location_col = 'Location' if 'Location' in df_events.columns else None
    if location_col:
        display_cols = ['Date', 'event_type', location_col, 'Deaths', 'Affected', 'Damage ($M)', 'Learn More']
        rename_cols = {
            'event_type': 'Event Type',
            location_col: 'Location'
        }
    else:
        display_cols = ['Date', 'event_type', 'Deaths', 'Affected', 'Damage ($M)', 'Learn More']
        rename_cols = {
            'event_type': 'Event Type'
        }

    df_display = df_events[display_cols].rename(columns=rename_cols).reset_index(drop=True)
    df_display.index = df_display.index + 1

    # Sorting options
    sort_col1, sort_col2, sort_col3, sort_col4 = st.columns([2, 2, 2, 6])
    with sort_col1:
        if st.button("📊 By Deaths"):
            df_display = df_display.sort_values('Deaths', ascending=False)
    with sort_col2:
        if st.button("👥 By Affected"):
            df_display = df_display.sort_values('Affected', ascending=False)
    with sort_col3:
        if st.button("💰 By Damage"):
            df_display = df_display.sort_values('Damage ($M)', ascending=False)

    st.dataframe(
        df_display,
        width='stretch',
        column_config={
            'Learn More': st.column_config.LinkColumn('Learn More', display_text='🔍 Google Search'),
            'Damage ($M)': st.column_config.NumberColumn(format='$%d'),
            'Deaths': st.column_config.NumberColumn(format='%d'),
            'Affected': st.column_config.NumberColumn(format='%d')
        },
        height=600
    )

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
render_country_deep_dive(data, portfolio, premium_by_peril, st.session_state.selected_country)

# Footer
st.caption("""
    📊 **EuroShield Insurance Group** | Climate Risk Analytics Division  
    Data Source: EM-DAT (Emergency Events Database) - CRED / UCLouvain, Brussels, Belgium  
    Dashboard covers historical disaster events across European markets
    """)
