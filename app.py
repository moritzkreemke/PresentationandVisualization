import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import altair as alt
import pydeck as pdk
from datetime import datetime
import numpy as np

# Set page configuration
st.set_page_config(layout="wide", page_title="EuroShield Climate Risk Dashboard")

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


# Load data
@st.cache_data
def load_data():
    # Load the three CSV files
    data = pd.read_csv("data.csv", encoding='utf-8')
    portfolio = pd.read_csv("euroshield_portfolio_by_country.csv")
    premium_by_peril = pd.read_csv("euroshield_premium_by_peril.csv")

    # Clean and prepare the main data
    # Convert numeric columns
    numeric_cols = ['Total Deaths', 'No. Injured', 'No. Affected', 'No. Homeless',
                    'Total Affected', 'Total Damage (\'000 US$)', 'Total Damage, Adjusted (\'000 US$)',
                    'Insured Damage (\'000 US$)', 'Insured Damage, Adjusted (\'000 US$)',
                    'Start Year', 'Start Month', 'Start Day', 'End Year', 'End Month', 'End Day']

    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')

    # Create a date column from Start Year, Month, Day
    data['date'] = pd.to_datetime(
        data[['Start Year', 'Start Month', 'Start Day']].rename(
            columns={'Start Year': 'year', 'Start Month': 'month', 'Start Day': 'day'}
        ),
        errors='coerce'
    )

    # Extract month and year for analysis
    data['month'] = data['Start Month']
    data['month_name'] = data['date'].dt.month_name()   # new readable month label
    data['year'] = data['Start Year']

    # Calculate event duration in days
    data['duration_days'] = (
            pd.to_datetime(data[['End Year', 'End Month', 'End Day']].rename(
                columns={'End Year': 'year', 'End Month': 'month', 'End Day': 'day'}
            ), errors='coerce') - data['date']
    ).dt.days

    # Create severity score based on multiple factors (0-10 scale)
    # Normalize deaths, affected, and damage
    max_deaths = data['Total Deaths'].max() if data['Total Deaths'].max() > 0 else 1
    max_affected = data['Total Affected'].max() if data['Total Affected'].max() > 0 else 1
    max_damage = data['Total Damage, Adjusted (\'000 US$)'].max() if data[
                                                                         'Total Damage, Adjusted (\'000 US$)'].max() > 0 else 1

    data['severity'] = (
            (data['Total Deaths'].fillna(0) / max_deaths * 3) +
            (data['Total Affected'].fillna(0) / max_affected * 3) +
            (data['Total Damage, Adjusted (\'000 US$)'].fillna(0) / max_damage * 4)
    ).clip(0, 10)

    # Map Disaster Type to simpler event types
    disaster_type_mapping = {
        'Flood': 'Flood',
        'Storm': 'Hurricane',
        'Extreme temperature': 'Heatwave',
        'Wildfire': 'Wildfire',
        'Drought': 'Drought',
        'Earthquake': 'Earthquake',
        'Mass movement (wet)': 'Landslide',
        'Mass movement (dry)': 'Landslide',
        'Volcanic activity': 'Volcanic',
        'Landslide': 'Landslide'
    }

    data['event_type'] = data['Disaster Type'].map(disaster_type_mapping).fillna(data['Disaster Type'])

    # Convert economic impact to millions (data is in thousands)
    data['economic_impact_million_usd'] = data['Total Damage, Adjusted (\'000 US$)'].fillna(0) / 1000

    # Create unique event ID
    data['event_id'] = data.index

    # Keep only European countries that are in the portfolio
    data = data[data['Country'].isin(portfolio['country'])]

    # Rename Country to country for consistency
    data = data.rename(columns={'Country': 'country'})

    # Merge data with portfolio data
    merged_data = pd.merge(data, portfolio, on='country', how='inner')

    return data, portfolio, premium_by_peril, merged_data


data, portfolio, premium_by_peril, merged_data = load_data()

# Country centroids (approximate) for European countries
country_centroids = {
    'Germany': {'lat': 51.1657, 'lon': 10.4515},
    'France': {'lat': 46.2276, 'lon': 2.2137},
    'United Kingdom of Great Britain and Northern Ireland': {'lat': 55.3781, 'lon': -3.4360},
    'Italy': {'lat': 41.8719, 'lon': 12.5674},
    'Spain': {'lat': 40.4637, 'lon': -3.7492},
    'Netherlands': {'lat': 52.1326, 'lon': 5.2913},
    'Poland': {'lat': 51.9194, 'lon': 19.1451},
    'Belgium': {'lat': 50.5039, 'lon': 4.4699},
    'Sweden': {'lat': 60.1282, 'lon': 18.6435},
    'Austria': {'lat': 47.5162, 'lon': 14.5501},
    'Greece': {'lat': 39.0742, 'lon': 21.8243},
    'Portugal': {'lat': 39.3999, 'lon': -8.2245},
    'Ireland': {'lat': 53.1424, 'lon': -7.6921},
    'Denmark': {'lat': 56.2639, 'lon': 9.5018},
    'Finland': {'lat': 61.9241, 'lon': 25.7482},
    'Norway': {'lat': 60.4720, 'lon': 8.4689},
    'Switzerland': {'lat': 46.8182, 'lon': 8.2275},
    'Czech Republic': {'lat': 49.8175, 'lon': 15.4730},
    'Romania': {'lat': 45.9432, 'lon': 24.9668},
    'Hungary': {'lat': 47.1625, 'lon': 19.5033},
}

# Initialize session state for filters
if 'selected_country' not in st.session_state:
    st.session_state.selected_country = "All Europe"
if 'selected_peril' not in st.session_state:
    st.session_state.selected_peril = "All Perils"
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = None

# Header
st.markdown('<div class="main-header">🏠 CIAOO EUROSHIELD CLIMATE RISK DASHBOARD</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Last Updated: {datetime.now().strftime("%B %Y")} | Data Source: EM-DAT International Disaster Database</div>',
    unsafe_allow_html=True)

# Get available years from data
available_years = sorted(data['year'].dropna().unique())
min_year = int(available_years[0]) if len(available_years) > 0 else 1950
max_year = int(available_years[-1]) if len(available_years) > 0 else 2025

# Top filter bar
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])

with col_f1:
    # Define covered and uncovered perils
    covered_perils = ['Flood', 'Wildfire', 'Hurricane', 'Heatwave', 'Coldwave', 'Storm']
    uncovered_perils = ['Earthquake', 'Drought', 'Landslide', 'Volcanic']

    peril_coverage = st.selectbox(
        "Peril Coverage",
        ["All Perils", "Covered Perils", "Uncovered Perils"],
        key="peril_coverage"
    )

with col_f2:
    european_countries = ["All Europe"] + sorted(portfolio['country'].tolist())
    country_filter = st.selectbox(
        "Country",
        european_countries,
        index=european_countries.index(
            st.session_state.selected_country) if st.session_state.selected_country in european_countries else 0
    )
    st.session_state.selected_country = country_filter

with col_f3:
    year_range = st.select_slider(
        "Year Range",
        options=list(range(min_year, max_year + 1)),
        value=(min_year, max_year)
    )

with col_f4:
    if st.button("🔄 Reset All", use_container_width=True):
        st.session_state.selected_country = "All Europe"
        st.session_state.selected_peril = "All Perils"
        st.session_state.selected_month = None
        st.rerun()

# Breadcrumb trail
breadcrumbs = []
if st.session_state.selected_country != "All Europe":
    breadcrumbs.append(st.session_state.selected_country)
if st.session_state.selected_peril != "All Perils":
    breadcrumbs.append(st.session_state.selected_peril)
if st.session_state.selected_month:
    breadcrumbs.append(f"Month {st.session_state.selected_month}")

if breadcrumbs:
    st.info(f"**Active Filters:** {' > '.join(breadcrumbs)}")

# Apply filters to data
filtered_data = merged_data.copy()

# Filter by year range
filtered_data = filtered_data[(filtered_data['year'] >= year_range[0]) & (filtered_data['year'] <= year_range[1])]

# Filter by country
if st.session_state.selected_country != "All Europe":
    filtered_data = filtered_data[filtered_data['country'] == st.session_state.selected_country]

# Filter by peril coverage
if peril_coverage == "Covered Perils":
    filtered_data = filtered_data[filtered_data['event_type'].isin(covered_perils)]
elif peril_coverage == "Uncovered Perils":
    filtered_data = filtered_data[filtered_data['event_type'].isin(uncovered_perils)]

# Filter by specific peril
if st.session_state.selected_peril != "All Perils":
    filtered_data = filtered_data[filtered_data['event_type'] == st.session_state.selected_peril]

# Filter by month
if st.session_state.selected_month:
    filtered_data = filtered_data[filtered_data['month'] == st.session_state.selected_month]

# Calculate KPIs
total_events = len(filtered_data)
avg_severity = filtered_data['severity'].mean() if len(filtered_data) > 0 else 0
total_impact = filtered_data['economic_impact_million_usd'].sum()
total_deaths = filtered_data['Total Deaths'].sum()
total_affected = filtered_data['Total Affected'].sum()

if st.session_state.selected_country != "All Europe":
    country_portfolio = portfolio[portfolio['country'] == st.session_state.selected_country]
    if not country_portfolio.empty:
        total_policies = country_portfolio['policy_count'].iloc[0]
        total_tiv = country_portfolio['total_insured_value_eur_billion'].iloc[0]
        annual_premium = country_portfolio['annual_premium_eur_million'].iloc[0]
        market_share = country_portfolio['market_share_percent'].iloc[0]
    else:
        total_policies = total_tiv = annual_premium = market_share = 0
else:
    total_policies = portfolio['policy_count'].sum()
    total_tiv = portfolio['total_insured_value_eur_billion'].sum()
    annual_premium = portfolio['annual_premium_eur_million'].sum()
    market_share = portfolio['market_share_percent'].mean()

# Display KPIs
st.markdown("---")
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)

with kpi_col1:
    st.metric("Total Events", f"{total_events:,}")

with kpi_col2:
    st.metric("Avg. Severity", f"{avg_severity:.1f}/10")

with kpi_col3:
    st.metric("Economic Impact", f"${total_impact:,.0f}M")

with kpi_col4:
    st.metric("Total Deaths", f"{int(total_deaths):,}")

with kpi_col5:
    st.metric("People Affected", f"{int(total_affected):,}")

with kpi_col6:
    st.metric("EuroShield TIV", f"€{total_tiv:.1f}B")

st.markdown("---")

# ============================================================================
# Q1: WHERE ARE OUR GREATEST FINANCIAL RISKS FROM CLIMATE EVENTS?
# ============================================================================
st.header("Q1: Where Are Our Greatest Financial Risks from Climate Events?")

# Prepare data for the map
map_data = filtered_data.groupby('country').agg({
    'severity': 'mean',
    'event_id': 'count',
    'Total Deaths': 'sum',
    'Total Affected': 'sum',
    'economic_impact_million_usd': 'sum'
}).reset_index()

map_data.rename(columns={
    'severity': 'average_severity',
    'event_id': 'total_events'
}, inplace=True)

# Merge with portfolio data
map_data = pd.merge(map_data, portfolio, on='country', how='inner')

# Add coordinates
map_data['lat'] = map_data['country'].map(lambda c: country_centroids.get(c, {}).get('lat'))
map_data['lon'] = map_data['country'].map(lambda c: country_centroids.get(c, {}).get('lon'))
map_data = map_data.dropna(subset=['lat', 'lon'])

if len(map_data) > 0:
    # Normalize bubble sizes based on Total Insured Value
    size_scale = 50000
    map_data['radius'] = (map_data['total_insured_value_eur_billion'] / map_data[
        'total_insured_value_eur_billion'].max()) * size_scale + 10000

    # Color by severity (green to red gradient)
    sev = map_data['average_severity']
    sev_norm = (sev - sev.min()) / (sev.max() - sev.min() + 1e-9)
    map_data['r'] = (sev_norm * 255).astype(int)
    map_data['g'] = (255 - (sev_norm * 255)).astype(int)
    map_data['b'] = 80

    # Create PyDeck layer
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=map_data,
        get_position='[lon, lat]',
        get_radius='radius',
        get_fill_color='[r, g, b, 180]',
        pickable=True,
        auto_highlight=True
    )

    # View state centered on Europe
    view_state = pdk.ViewState(
        latitude=54.0,
        longitude=10.0,
        zoom=3.5,
        pitch=0,
        bearing=0
    )

    # Tooltip
    tooltip = {
        "html": """
        <b>{country}</b><br/>
        ─────────────────────────<br/>
        Avg. Event Severity: {average_severity:.1f}/10<br/>
        Total Events: {total_events}<br/>
        Total Deaths: {Total Deaths:,.0f}<br/>
        People Affected: {Total Affected:,.0f}<br/>
        Economic Impact: ${economic_impact_million_usd:,.0f}M<br/>
        <br/>
        <b>EuroShield Portfolio:</b><br/>
        Policies: {policy_count:,}<br/>
        Total Insured Value: €{total_insured_value_eur_billion:.1f}B<br/>
        Annual Premium: €{annual_premium_eur_million:.1f}M<br/>
        Market Share: {market_share_percent:.1f}%
        """,
        "style": {
            "backgroundColor": "#1f4788",
            "color": "white",
            "fontSize": "12px",
            "padding": "10px"
        }
    }

    # Display map
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style='light'
    ), use_container_width=True)

    st.caption(
        "💡 **Bubble size** represents Total Insured Value | **Color intensity** represents Average Event Severity (green=low, red=high)")
else:
    st.warning("No data available for the selected filters.")

st.markdown("---")

# ============================================================================
# Q2 & Q3: SEASONAL PATTERNS AND TRENDS
# ============================================================================

col1, col2 = st.columns(2)

with col1:
    st.subheader("Q2: When Should We Prepare for Seasonal Surges?")

    # Prepare seasonal dataset
    seasonal_data = filtered_data.groupby(['month', 'event_type']).agg(
        count=('event_id', 'count')
    ).reset_index()

    # ✅ Filter to major climate-relevant event types (Q2 only)
    key_events = ['Hurricane', 'Flood', 'Heatwave', 'Wildfire', 'Drought']
    seasonal_data = seasonal_data[seasonal_data['event_type'].isin(key_events)]

    # Ensure months are sorted correctly
    month_order = [1,2,3,4,5,6,7,8,9,10,11,12]
    seasonal_data['month'] = pd.Categorical(seasonal_data['month'], month_order)

    # Line chart: Monthly event frequency by type
    fig_season = px.line(
        seasonal_data,
        x='month',
        y='count',
        color='event_type',
        markers=True,
        labels={'month': 'Month', 'count': 'Number of Events', 'event_type': 'Event Type'},
        title=f"Seasonal Patterns of Climate Events - {st.session_state.selected_country}"
    )

    fig_season.update_traces(line=dict(width=2))
    fig_season.update_layout(
    height=420,
    template="plotly_white",
    colorway=[
        "#0068A5",  # Flood - deep blue
        "#D62728",  # Heatwave - strong red
        "#4CAF50",  # Landslide - green
        "#FF7F0E",  # Wildfire - orange
        "#8C6BB1",  # Drought - muted purple
        "#1F77B4",  # Hurricane - ocean blue
    ],
    xaxis=dict(
        tickmode='array',
        tickvals=month_order,
        ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    ),
    yaxis_title="Number of Recorded Events",
)

    st.plotly_chart(fig_season, width="stretch")

    # Insight text block
    if len(seasonal_data) > 0:
        highest_peak = seasonal_data.sort_values('count', ascending=False).iloc[0]
        peak_month = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(highest_peak['month'])-1]

        st.info(f"""
        ### Seasonal Insight  
        The data shows a clear seasonal pattern.  
        **{highest_peak['event_type']}** events reach their highest frequency in **{peak_month}**,  
        with **{int(highest_peak['count'])} recorded occurrences** during this month.  

        This period may require **increased preparedness**, resource planning, and early monitoring interventions.
        """)
with col2:
    st.subheader("Q3: Are Key Perils Becoming More Frequent or Costly?")

    # Group by year
    yearly_trends = filtered_data.groupby('year').agg({
        'event_id': 'count',
        'economic_impact_million_usd': 'mean'
    }).reset_index()

    yearly_trends.rename(columns={
        'event_id': 'event_count',
        'economic_impact_million_usd': 'avg_economic_impact'
    }, inplace=True)

    if len(yearly_trends) > 0:
        # Create dual-axis chart with Plotly
        fig_trend = go.Figure()

        # Add bars for event count
        fig_trend.add_trace(go.Bar(
            x=yearly_trends['year'],
            y=yearly_trends['event_count'],
            name='Event Count',
            marker_color='lightgray',
            yaxis='y'
        ))

        # Add line for economic impact
        fig_trend.add_trace(go.Scatter(
            x=yearly_trends['year'],
            y=yearly_trends['avg_economic_impact'],
            name='Avg. Economic Impact ($M)',
            mode='lines+markers',
            marker=dict(size=8, color='red'),
            line=dict(color='red', width=3),
            yaxis='y2'
        ))

        # Update layout for dual axis
        fig_trend.update_layout(
            title=f'Climate Risk Trend - {st.session_state.selected_country} ({year_range[0]}-{year_range[1]})',
            xaxis=dict(title='Year'),
            yaxis=dict(title='Event Count', side='left'),
            yaxis2=dict(title='Avg. Economic Impact ($M)', overlaying='y', side='right'),
            hovermode='x unified',
            height=400
        )

        st.plotly_chart(fig_trend, use_container_width=True)

        # Trend indicators
        if len(yearly_trends) > 1:
            freq_change = ((yearly_trends['event_count'].iloc[-1] - yearly_trends['event_count'].iloc[0]) / (
                        yearly_trends['event_count'].iloc[0] + 1) * 100)
            cost_change = ((yearly_trends['avg_economic_impact'].iloc[-1] - yearly_trends['avg_economic_impact'].iloc[
                0]) / (yearly_trends['avg_economic_impact'].iloc[0] + 1) * 100)

            freq_icon = "↗️" if freq_change > 0 else "↘️"
            cost_icon = "↗️" if cost_change > 0 else "↘️"

            st.info(f"""
            {freq_icon} **Frequency:** {abs(freq_change):.1f}% {'increase' if freq_change > 0 else 'decrease'} since {year_range[0]}  
            {cost_icon} **Avg. Cost:** {abs(cost_change):.1f}% {'increase' if cost_change > 0 else 'decrease'} since {year_range[0]}
            """)
    else:
        st.warning("No trend data available for the selected filters.")

st.markdown("---")

# ============================================================================
# Q4 & Q5: STRATEGIC ANALYSIS
# ============================================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("Q4: Which Perils Are 'Chronic Headaches' vs. 'Sleeping Giants'?")

    # Prepare data for peril classification
    peril_data = filtered_data.groupby('event_type').agg({
        'severity': 'mean',
        'event_id': 'count'
    }).reset_index()

    # Calculate average annual frequency
    years_in_data = filtered_data['year'].nunique()
    if years_in_data > 0:
        peril_data['average_annual_frequency'] = peril_data['event_id'] / years_in_data
    else:
        peril_data['average_annual_frequency'] = 0

    # Merge with premium data
    peril_analysis = pd.merge(peril_data, premium_by_peril, on='event_type', how='left')
    peril_analysis['annual_premium_eur_million'] = peril_analysis['annual_premium_eur_million'].fillna(0)

    if len(peril_analysis) > 0:
        # Calculate mean values for quadrant lines
        mean_frequency = peril_analysis['average_annual_frequency'].mean()
        mean_severity = peril_analysis['severity'].mean()

        # Create scatter plot
        fig_peril = px.scatter(
            peril_analysis,
            x='average_annual_frequency',
            y='severity',
            size='annual_premium_eur_million',
            color='event_type',
            hover_name='event_type',
            hover_data={
                'average_annual_frequency': ':.1f',
                'severity': ':.1f',
                'annual_premium_eur_million': ':,.1f'
            },
            title='Risk Matrix: Frequency vs. Severity',
            labels={
                'average_annual_frequency': 'Avg. Annual Frequency (events/year)',
                'severity': 'Avg. Severity (1-10)'
            }
        )

        # Add quadrant lines
        fig_peril.add_hline(y=mean_severity, line_dash="dash", line_color="gray", opacity=0.5)
        fig_peril.add_vline(x=mean_frequency, line_dash="dash", line_color="gray", opacity=0.5)

        # Add quadrant labels with background colors
        fig_peril.add_annotation(
            x=mean_frequency * 0.3, y=mean_severity * 1.3,
            text="⚠️ Sleeping Giants",
            showarrow=False,
            bgcolor="rgba(255, 200, 200, 0.3)",
            font=dict(size=10)
        )
        fig_peril.add_annotation(
            x=mean_frequency * 1.7, y=mean_severity * 1.3,
            text="🔴 DANGER ZONE",
            showarrow=False,
            bgcolor="rgba(255, 100, 100, 0.3)",
            font=dict(size=10, color="darkred")
        )
        fig_peril.add_annotation(
            x=mean_frequency * 1.7, y=mean_severity * 0.7,
            text="⚡ Chronic Headaches",
            showarrow=False,
            bgcolor="rgba(255, 255, 150, 0.3)",
            font=dict(size=10)
        )
        fig_peril.add_annotation(
            x=mean_frequency * 0.3, y=mean_severity * 0.7,
            text="✓ Nuisance",
            showarrow=False,
            bgcolor="rgba(200, 255, 200, 0.3)",
            font=dict(size=10)
        )

        fig_peril.update_layout(height=450, showlegend=True)

        st.plotly_chart(fig_peril, use_container_width=True)

        st.caption("💡 **Bubble size** represents Annual Premium collected by EuroShield")
    else:
        st.warning("No peril data available for the selected filters.")

with col2:
    st.subheader("Q5: Where Are Our Safest Markets for Profitable Growth?")

    # Prepare data for growth opportunities
    growth_data = filtered_data.groupby('country').agg({
        'event_id': 'count',
        'severity': 'mean',
    }).reset_index()

    growth_data.rename(columns={'event_id': 'total_events'}, inplace=True)

    # Merge with portfolio data
    growth_data = pd.merge(growth_data, portfolio, on='country', how='inner')

    if len(growth_data) > 0:
        # Calculate mean values for quadrant lines
        mean_events = growth_data['total_events'].mean()
        mean_severity_growth = growth_data['severity'].mean()

        # Create scatter plot
        fig_growth = px.scatter(
            growth_data,
            x='total_events',
            y='severity',
            size='total_insured_value_eur_billion',
            color='market_share_percent',
            color_continuous_scale='Blues_r',
            hover_name='country',
            hover_data={
                'total_events': True,
                'severity': ':.1f',
                'market_share_percent': ':.1f',
                'policy_count': ':,',
                'total_insured_value_eur_billion': ':.1f'
            },
            title='Market Growth Opportunities',
            labels={
                'total_events': f'Total Events ({year_range[0]}-{year_range[1]})',
                'severity': 'Avg. Severity (1-10)',
                'market_share_percent': 'Market Share %'
            }
        )

        # Add quadrant lines
        fig_growth.add_hline(y=mean_severity_growth, line_dash="dash", line_color="gray", opacity=0.5)
        fig_growth.add_vline(x=mean_events, line_dash="dash", line_color="gray", opacity=0.5)

        # Highlight safe harbor markets (bottom-left quadrant)
        fig_growth.add_annotation(
            x=mean_events * 0.3, y=mean_severity_growth * 0.7,
            text="🎯 Safe Harbor Markets",
            showarrow=False,
            bgcolor="rgba(150, 255, 150, 0.3)",
            font=dict(size=12, color="darkgreen")
        )

        fig_growth.update_layout(height=450)

        st.plotly_chart(fig_growth, use_container_width=True)

        # Growth opportunities callout
        safe_markets = growth_data[
            (growth_data['total_events'] < mean_events) &
            (growth_data['severity'] < mean_severity_growth) &
            (growth_data['market_share_percent'] < 5)
            ].nsmallest(3, 'market_share_percent')

        if len(safe_markets) > 0:
            st.success(f"""
                        💡 **GROWTH OPPORTUNITIES:**  
                        Based on low risk + low market share, consider expansion in:
                        {chr(10).join([f"• **{row['country']}** ({row['market_share_percent']:.1f}% share, {int(row['total_events'])} events, severity {row['severity']:.1f})" for _, row in safe_markets.iterrows()])}
                        """)

        st.caption(
            "💡 **Darker blue** = Higher market share (established) | **Lighter blue** = Lower market share (opportunity)")
    else:
        st.warning("No growth opportunity data available for the selected filters.")

    st.markdown("---")

    # ============================================================================
    # ADDITIONAL INSIGHTS SECTION
    # ============================================================================
    st.header("📊 Additional Insights")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Top 5 Deadliest Events")
        if len(filtered_data) > 0:
            deadliest = filtered_data.nlargest(5, 'Total Deaths')[
                ['country', 'event_type', 'Start Year', 'Total Deaths', 'economic_impact_million_usd']]
            deadliest = deadliest.rename(columns={
                'Start Year': 'Year',
                'Total Deaths': 'Deaths',
                'economic_impact_million_usd': 'Impact ($M)'
            })
            st.dataframe(deadliest, hide_index=True, use_container_width=True)
        else:
            st.info("No data available")

    with col2:
        st.subheader("Most Costly Events")
        if len(filtered_data) > 0:
            costliest = filtered_data.nlargest(5, 'economic_impact_million_usd')[
                ['country', 'event_type', 'Start Year', 'economic_impact_million_usd', 'Total Affected']]
            costliest = costliest.rename(columns={
                'Start Year': 'Year',
                'economic_impact_million_usd': 'Impact ($M)',
                'Total Affected': 'Affected'
            })
            st.dataframe(costliest, hide_index=True, use_container_width=True)
        else:
            st.info("No data available")

    with col3:
        st.subheader("Event Type Distribution")
        if len(filtered_data) > 0:
            event_dist = filtered_data['event_type'].value_counts().reset_index()
            event_dist.columns = ['Event Type', 'Count']

            fig_pie = px.pie(
                event_dist,
                values='Count',
                names='Event Type',
                title='',
                hole=0.4
            )
            fig_pie.update_layout(height=300, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No data available")

    st.markdown("---")

    # ============================================================================
    # DETAILED EVENT TABLE
    # ============================================================================
    st.header("📋 Detailed Event Records")

    if len(filtered_data) > 0:
        # Prepare display columns
        display_cols = [
            'country', 'event_type', 'Start Year', 'Start Month',
            'severity', 'Total Deaths', 'Total Affected',
            'economic_impact_million_usd', 'duration_days', 'Location'
        ]

        # Filter to only existing columns
        display_cols = [col for col in display_cols if col in filtered_data.columns]

        display_data = filtered_data[display_cols].copy()

        # Rename for better display
        display_data = display_data.rename(columns={
            'Start Year': 'Year',
            'Start Month': 'Month',
            'event_type': 'Event Type',
            'country': 'Country',
            'severity': 'Severity',
            'Total Deaths': 'Deaths',
            'Total Affected': 'Affected',
            'economic_impact_million_usd': 'Impact ($M)',
            'duration_days': 'Duration (days)'
        })

        # Format numeric columns
        if 'Severity' in display_data.columns:
            display_data['Severity'] = display_data['Severity'].round(1)
        if 'Impact ($M)' in display_data.columns:
            display_data['Impact ($M)'] = display_data['Impact ($M)'].round(1)
        if 'Deaths' in display_data.columns:
            display_data['Deaths'] = display_data['Deaths'].fillna(0).astype(int)
        if 'Affected' in display_data.columns:
            display_data['Affected'] = display_data['Affected'].fillna(0).astype(int)

        # Sort by severity
        if 'Severity' in display_data.columns:
            display_data = display_data.sort_values('Severity', ascending=False)

        # Display with pagination
        st.dataframe(
            display_data,
            hide_index=True,
            use_container_width=True,
            height=400
        )

        # Download button
        csv = display_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Event Data as CSV",
            data=csv,
            file_name=f"euroshield_events_{st.session_state.selected_country}_{year_range[0]}_{year_range[1]}.csv",
            mime="text/csv",
        )
    else:
        st.info("No events match the current filter criteria. Try adjusting your filters.")

    st.markdown("---")

    # ============================================================================
    # SUMMARY STATISTICS
    # ============================================================================
    st.header("📈 Summary Statistics")

    if len(filtered_data) > 0:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Average Event Duration",
                f"{filtered_data['duration_days'].mean():.1f} days" if 'duration_days' in filtered_data.columns else "N/A"
            )

        with col2:
            st.metric(
                "Median Severity",
                f"{filtered_data['severity'].median():.1f}/10"
            )
        insured_damage_col = "Insured Damage, Adjusted ('000 US$)"
        with col3:
            st.metric(
                "Total Insured Damage",
                f"${filtered_data[insured_damage_col].sum() / 1000:,.0f}M" if insured_damage_col in filtered_data.columns else "N/A"
            )
        with col4:
            st.metric(
                "Events per Year",
                f"{len(filtered_data) / max(1, filtered_data['year'].nunique()):.1f}"
            )

        # Correlation Analysis
        st.subheader("🔗 Risk Correlations")

        col1, col2 = st.columns(2)

        with col1:
            # Severity vs Economic Impact
            if len(filtered_data) > 5:
                fig_corr1 = px.scatter(
                    filtered_data,
                    x='severity',
                    y='economic_impact_million_usd',
                    color='event_type',
                    title='Severity vs. Economic Impact',
                    labels={
                        'severity': 'Severity Score (1-10)',
                        'economic_impact_million_usd': 'Economic Impact ($M)'
                    },
                    trendline="ols"
                )
                fig_corr1.update_layout(height=350)
                st.plotly_chart(fig_corr1, use_container_width=True)

        with col2:
            # Duration vs Impact
            if 'duration_days' in filtered_data.columns and len(filtered_data) > 5:
                fig_corr2 = px.scatter(
                    filtered_data[filtered_data['duration_days'] > 0],
                    x='duration_days',
                    y='Total Affected',
                    color='event_type',
                    title='Event Duration vs. People Affected',
                    labels={
                        'duration_days': 'Duration (days)',
                        'Total Affected': 'People Affected'
                    },
                    trendline="ols"
                )
                fig_corr2.update_layout(height=350)
                st.plotly_chart(fig_corr2, use_container_width=True)

    st.markdown("---")

    # ============================================================================
    # RISK ALERTS & RECOMMENDATIONS
    # ============================================================================
    st.header("⚠️ Risk Alerts & Strategic Recommendations")

    if len(filtered_data) > 0:
        alerts = []

        # Check for increasing frequency
        if len(filtered_data) > 10:
            recent_years = filtered_data[filtered_data['year'] >= max(filtered_data['year']) - 2]
            older_years = filtered_data[filtered_data['year'] < max(filtered_data['year']) - 2]

            if len(recent_years) > 0 and len(older_years) > 0:
                recent_freq = len(recent_years) / max(1, recent_years['year'].nunique())
                older_freq = len(older_years) / max(1, older_years['year'].nunique())

                if recent_freq > older_freq * 1.3:
                    alerts.append({
                        'type': '🔴 HIGH ALERT',
                        'message': f'Event frequency has increased by {((recent_freq / older_freq - 1) * 100):.0f}% in recent years',
                        'recommendation': 'Consider increasing reserves and reviewing premium structures'
                    })

        # Check for high severity events
        high_severity = filtered_data[filtered_data['severity'] > 7]
        if len(high_severity) > 0:
            alerts.append({
                'type': '⚠️ WARNING',
                'message': f'{len(high_severity)} high-severity events (>7/10) detected',
                'recommendation': 'Review coverage limits and reinsurance arrangements for affected regions'
            })

        # Check for uncovered perils with high impact
        if peril_coverage == "Uncovered Perils" and total_impact > 1000:
            alerts.append({
                'type': '💡 OPPORTUNITY',
                'message': f'Uncovered perils show ${total_impact:,.0f}M in economic impact',
                'recommendation': 'Consider developing new insurance products for these emerging risks'
            })

        # Check for low market share in low-risk areas
        if st.session_state.selected_country != "All Europe":
            country_data = growth_data[growth_data['country'] == st.session_state.selected_country]
            if len(country_data) > 0:
                ms = country_data['market_share_percent'].iloc[0]
                sev = country_data['severity'].iloc[0]

                if ms < 5 and sev < 5:
                    alerts.append({
                        'type': '🎯 GROWTH OPPORTUNITY',
                        'message': f'{st.session_state.selected_country} shows low risk (severity {sev:.1f}) with low market share ({ms:.1f}%)',
                        'recommendation': 'Prioritize market expansion efforts in this region'
                    })

        # Display alerts
        if alerts:
            for alert in alerts:
                if alert['type'].startswith('🔴'):
                    st.error(f"**{alert['type']}**: {alert['message']}\n\n➡️ *{alert['recommendation']}*")
                elif alert['type'].startswith('⚠️'):
                    st.warning(f"**{alert['type']}**: {alert['message']}\n\n➡️ *{alert['recommendation']}*")
                elif alert['type'].startswith('💡') or alert['type'].startswith('🎯'):
                    st.success(f"**{alert['type']}**: {alert['message']}\n\n➡️ *{alert['recommendation']}*")
        else:
            st.info("✅ No critical alerts at this time. Continue monitoring risk indicators.")

    st.markdown("---")

    # Footer
    st.caption("""
            📊 **EuroShield Insurance Group** | Climate Risk Analytics Division  
            Data Source: EM-DAT (Emergency Events Database) - CRED / UCLouvain, Brussels, Belgium  
            Dashboard covers historical disaster events across European markets
            """)

    # Sidebar with additional info
    with st.sidebar:
        st.header("ℹ️ About This Dashboard")
        st.markdown("""
                This interactive dashboard helps EuroShield Insurance Group:

                - **Identify** geographic risk concentrations
                - **Anticipate** seasonal risk patterns
                - **Track** long-term climate trends
                - **Classify** peril risk profiles
                - **Discover** growth opportunities

                ---

                ### Data Coverage
                - **Source**: EM-DAT International Disaster Database
                - **Geographic Scope**: European markets
                - **Event Types**: Natural disasters (floods, storms, earthquakes, etc.)
                - **Metrics**: Deaths, affected population, economic impact

                ---

                ### How to Use
                1. Select filters at the top
                2. Click on map bubbles to drill down
                3. Hover over charts for details
                4. Export data using download buttons

                ---

                ### Key Definitions

                **Severity Score (1-10)**: Composite metric based on:
                - Human impact (deaths, affected)
                - Economic damage
                - Event scale

                **Covered Perils**: Events EuroShield currently insures

                **Uncovered Perils**: Emerging risks not yet in portfolio

                **Safe Harbor Markets**: Low-risk regions with growth potential
                """)

        st.markdown("---")

        # Display current filter summary
        st.subheader("📌 Current Selection")
        st.write(f"**Country**: {st.session_state.selected_country}")
        st.write(f"**Peril Coverage**: {peril_coverage}")
        st.write(f"**Year Range**: {year_range[0]} - {year_range[1]}")
        st.write(f"**Events Shown**: {len(filtered_data):,}")
