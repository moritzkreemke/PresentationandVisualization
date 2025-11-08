import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# =================================================================
# 1. GLOBAL CONFIGURATION AND ASSETS
# =================================================================

# Set page configuration
st.set_page_config(layout="wide", page_title="EuroShield Climate Risk Dashboard (COVID Period Analysis)")

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
    /* Reduce padding around plots to save space */
    div.stPlotlyChart {
        padding: 0px;
    }
    </style>
""", unsafe_allow_html=True)


# --- CUSTOM COLOR MAP ---
custom_color_map = {
    "Drought": "#1B9E77",
    "Earthquake": "#D95F02",
    "Epidemic": "#7570B3",
    "Flood": "#E7298A",
    "Glacial Lake Outburst Flood": "#66A61E",
    "Heatwave": "#E6AB02",
    "Hurricane": "#A6761D",
    "Landslide": "#556B2F",
    "Volcanic": "#F781BF",
    "Wildfire": "#FF4500"
}

# Country centroids (approximate)
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

# =================================================================
# 2. DATA LOADING AND PREPARATION (FIXED)
# =================================================================

@st.cache_data
def load_data():
    # Load the three CSV files
    data = pd.read_csv("data.csv", encoding='utf-8')
    portfolio = pd.read_csv("euroshield_portfolio_by_country.csv")
    premium_by_peril = pd.read_csv("euroshield_premium_by_peril.csv")

    # Ensure these columns exist before operating on them
    numeric_cols = ['Total Deaths', 'No. Injured', 'No. Affected', 'No. Homeless',
                    'Total Affected', "Total Damage ('000 US$)", "Total Damage, Adjusted ('000 US$)",
                    "Insured Damage ('000 US$)", "Insured Damage, Adjusted ('000 US$)",
                    'Start Year', 'Start Month', 'Start Day', 'End Year', 'End Month', 'End Day']

    for col in numeric_cols:
        if col in data.columns:
            # Convert to numeric, coercing errors to NaN
            data[col] = pd.to_numeric(data[col], errors='coerce')

            # Use Pandas Nullable Integer Type for temporal columns so they can contain NA
            if 'Year' in col or 'Month' in col or 'Day' in col:
                data[col] = data[col].astype(pd.Int64Dtype())

    # Create an event id (safe unique id)
    data['event_id'] = data.index

    # --- SAFELY BUILD START DATE ---
    if {'Start Year', 'Start Month', 'Start Day'}.issubset(data.columns):
        # Fill missing parts with 1 as placeholder then convert to int for to_datetime assembly
        start_parts = data[['Start Year', 'Start Month', 'Start Day']].fillna(1)
        # after fillna, convert to plain int so pandas can assemble
        try:
            start_parts = start_parts.astype(int)
        except Exception:
            # fallback: convert each column individually
            start_parts['Start Year'] = start_parts['Start Year'].astype(int)
            start_parts['Start Month'] = start_parts['Start Month'].astype(int)
            start_parts['Start Day'] = start_parts['Start Day'].astype(int)

        start_parts = start_parts.rename(columns={'Start Year': 'year', 'Start Month': 'month', 'Start Day': 'day'})
        data['date'] = pd.to_datetime(start_parts, errors='coerce')
    else:
        data['date'] = pd.NaT

    # Extract month and year for analysis (keep same nullable type)
    if 'Start Month' in data.columns:
        data['month'] = data['Start Month']
    else:
        data['month'] = pd.Series([pd.NA] * len(data), dtype="Int64")

    if 'Start Year' in data.columns:
        data['year'] = data['Start Year']
    else:
        data['year'] = pd.Series([pd.NA] * len(data), dtype="Int64")

    # --- SAFELY BUILD END DATE & DURATION ---
    if {'End Year', 'End Month', 'End Day'}.issubset(data.columns):
        end_parts = data[['End Year', 'End Month', 'End Day']].fillna(1)
        try:
            end_parts = end_parts.astype(int)
        except Exception:
            end_parts['End Year'] = end_parts['End Year'].astype(int)
            end_parts['End Month'] = end_parts['End Month'].astype(int)
            end_parts['End Day'] = end_parts['End Day'].astype(int)

        end_parts = end_parts.rename(columns={'End Year': 'year', 'End Month': 'month', 'End Day': 'day'})
        end_dt = pd.to_datetime(end_parts, errors='coerce')
        data['duration_days'] = (end_dt - data['date']).dt.days
    else:
        data['duration_days'] = pd.NA

    # Create severity score (0-10) with safe fallbacks
    max_deaths = data['Total Deaths'].max() if ('Total Deaths' in data.columns and pd.notna(data['Total Deaths'].max())) else 1
    max_affected = data['Total Affected'].max() if ('Total Affected' in data.columns and pd.notna(data['Total Affected'].max())) else 1
    max_damage = data["Total Damage, Adjusted ('000 US$)"].max() if ("Total Damage, Adjusted ('000 US$)" in data.columns and pd.notna(data["Total Damage, Adjusted ('000 US$)"].max())) else 1

    data['severity'] = (
            (data['Total Deaths'].fillna(0) / max_deaths * 3) +
            (data['Total Affected'].fillna(0) / max_affected * 3) +
            (data["Total Damage, Adjusted ('000 US$)"].fillna(0) / max_damage * 4)
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
        'Landslide': 'Landslide',
        'Epidemic': 'Epidemic'
    }

    if 'Disaster Type' in data.columns:
        data['event_type'] = data['Disaster Type'].map(disaster_type_mapping).fillna(data['Disaster Type'])
    else:
        data['event_type'] = pd.NA

    # Convert economic impact to millions (data is in thousands)
    td_col = "Total Damage, Adjusted ('000 US$)"
    if td_col in data.columns:
        data['economic_impact_million_usd'] = data[td_col].fillna(0) / 1000
    else:
        data['economic_impact_million_usd'] = 0

    # Keep only European countries that are in the portfolio (guard missing Country column)
    if 'Country' in data.columns and 'country' in portfolio.columns:
        data = data[data['Country'].isin(portfolio['country'])]
        # Rename Country to country for consistency
        data = data.rename(columns={'Country': 'country'})
    elif 'country' not in data.columns and 'country' in portfolio.columns:
        # nothing to filter if column is missing, but ensure we have country column
        data['country'] = pd.NA

    # Merge data with portfolio data (if country column exists in both)
    if 'country' in data.columns and 'country' in portfolio.columns:
        merged_data = pd.merge(data, portfolio, on='country', how='inner')
    else:
        merged_data = data.copy()

    return data, portfolio, premium_by_peril, merged_data


data, portfolio, premium_by_peril, merged_data = load_data()

# =================================================================
# 3. STREAMLIT APP LAYOUT AND FILTERING
# =================================================================

# Initialize session state for filters
if 'selected_country' not in st.session_state:
    st.session_state.selected_country = "All Europe"
if 'selected_peril' not in st.session_state:
    st.session_state.selected_peril = "All Perils"
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = None

# Header
st.markdown('<div class="main-header">🏠 EUROSHIELD CLIMATE RISK DASHBOARD (COVID Period Analysis) </div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Last Updated: {datetime.now().strftime("%B %Y")} | Data Source: EM-DAT (Natural Disasters only)</div>',
    unsafe_allow_html=True)

# Define fixed year range for COVID period analysis
MIN_YEAR_COVID = 2020
MAX_YEAR_COVID = 2022

# Filter data only for the COVID period (2020-2022)
# Note: merged_data['year'] may be pandas nullable Int64; comparisons work but we coerce safely
merged_data['year_numeric'] = pd.to_numeric(merged_data['year'], errors='coerce')
filtered_data = merged_data[
    (merged_data['year_numeric'] >= MIN_YEAR_COVID) & (merged_data['year_numeric'] <= MAX_YEAR_COVID)
].copy()

st.info(f"🦠 **Analysis Focus:** Data is fixed to the COVID period ({MIN_YEAR_COVID}–{MAX_YEAR_COVID}) to analyze risk patterns.")

# Top filter bar
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])

with col_f1:
    covered_perils = ['Flood', 'Wildfire', 'Hurricane', 'Heatwave', 'Coldwave', 'Storm']
    uncovered_perils = ['Earthquake', 'Drought', 'Landslide', 'Volcanic']

    peril_coverage = st.selectbox(
        "Peril Coverage",
        ["All Perils", "Covered Perils", "Uncovered Perils"],
        key="peril_coverage"
    )

with col_f2:
    european_countries = ["All Europe"]
    if 'country' in portfolio.columns:
        european_countries += sorted(portfolio['country'].tolist())
    country_filter = st.selectbox(
        "Country",
        european_countries,
        index=european_countries.index(
            st.session_state.selected_country) if st.session_state.selected_country in european_countries else 0
    )
    st.session_state.selected_country = country_filter

with col_f3:
    year_range = (MIN_YEAR_COVID, MAX_YEAR_COVID)
    st.select_slider(
        "Year Range (Fixed)",
        options=list(range(MIN_YEAR_COVID, MAX_YEAR_COVID + 1)),
        value=(MIN_YEAR_COVID, MAX_YEAR_COVID),
        disabled=True
    )

with col_f4:
    if st.button("🔄 Reset Filters", use_container_width=True):
        st.session_state.selected_country = "All Europe"
        st.session_state.selected_peril = "All Perils"
        st.session_state.selected_month = None
        st.rerun()

# Apply filters to data (Year filter is already applied above)
if st.session_state.selected_country != "All Europe":
    if 'country' in filtered_data.columns:
        filtered_data = filtered_data[filtered_data['country'] == st.session_state.selected_country]

if peril_coverage == "Covered Perils":
    filtered_data = filtered_data[filtered_data['event_type'].isin(covered_perils)]
elif peril_coverage == "Uncovered Perils":
    filtered_data = filtered_data[filtered_data['event_type'].isin(uncovered_perils)]

# Calculate KPIs (Key Performance Indicators) with safe fills
total_events = len(filtered_data)
avg_severity = filtered_data['severity'].mean() if total_events > 0 else 0
total_impact = filtered_data['economic_impact_million_usd'].fillna(0).sum()
total_deaths = int(filtered_data['Total Deaths'].fillna(0).sum()) if 'Total Deaths' in filtered_data.columns else 0
total_affected = int(filtered_data['Total Affected'].fillna(0).sum()) if 'Total Affected' in filtered_data.columns else 0

# Portfolio KPIs
if st.session_state.selected_country != "All Europe" and 'country' in portfolio.columns:
    country_portfolio = portfolio[portfolio['country'] == st.session_state.selected_country]
    if not country_portfolio.empty:
        total_policies = int(country_portfolio['policy_count'].iloc[0]) if 'policy_count' in country_portfolio.columns else 0
        total_tiv = float(country_portfolio['total_insured_value_eur_billion'].iloc[0]) if 'total_insured_value_eur_billion' in country_portfolio.columns else 0
        annual_premium = float(country_portfolio['annual_premium_eur_million'].iloc[0]) if 'annual_premium_eur_million' in country_portfolio.columns else 0
        market_share = float(country_portfolio['market_share_percent'].iloc[0]) if 'market_share_percent' in country_portfolio.columns else 0
    else:
        total_policies = total_tiv = annual_premium = market_share = 0
else:
    total_policies = int(portfolio['policy_count'].sum()) if 'policy_count' in portfolio.columns else 0
    total_tiv = float(portfolio['total_insured_value_eur_billion'].sum()) if 'total_insured_value_eur_billion' in portfolio.columns else 0
    annual_premium = float(portfolio['annual_premium_eur_million'].sum()) if 'annual_premium_eur_million' in portfolio.columns else 0
    market_share = float(portfolio['market_share_percent'].mean()) if 'market_share_percent' in portfolio.columns else 0

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
    st.metric("Total Deaths", f"{total_deaths:,}")

with kpi_col5:
    st.metric("People Affected", f"{total_affected:,}")

with kpi_col6:
    st.metric("EuroShield TIV", f"€{total_tiv:,.1f}B")

st.markdown("---")

# =================================================================
# 4. COVID PATTERN ANALYSIS CHARTS
# =================================================================

total_mean_severity = filtered_data['severity'].mean() if len(filtered_data) > 0 else 5
total_mean_impact = filtered_data['economic_impact_million_usd'].mean() if len(filtered_data) > 0 else 100
if total_mean_impact == 0:
    total_mean_impact = 1

st.subheader("COVID Period Risk Patterns (2020-2022)")

col1, col2 = st.columns(2)

# =====================================================
#1: Annual Event Frequency Trend (col1)
# =====================================================
with col1:
    st.markdown("Annual Event Frequency Trend")

    if 'event_id' in filtered_data.columns and 'year_numeric' in filtered_data.columns:
        annual_count = filtered_data.groupby('year_numeric')['event_id'].count().reset_index()
        annual_count.columns = ['Year', 'Event Count']
    elif 'year' in filtered_data.columns:
        annual_count = filtered_data.groupby('year')['event_id'].count().reset_index()
        annual_count.columns = ['Year', 'Event Count']
    else:
        annual_count = pd.DataFrame({'Year': [], 'Event Count': []})

    fig_annual = px.bar(
        annual_count,
        x='Year',
        y='Event Count',
        title='',
        text='Event Count',
        color='Event Count',
        color_continuous_scale=px.colors.sequential.Teal
    )

    fig_annual.update_traces(textposition='outside')
    fig_annual.update_layout(
        xaxis_title="",
        yaxis_title="Number of Events",
        height=400,
        margin=dict(t=20, b=0, l=0, r=0)
    )

    st.plotly_chart(fig_annual, use_container_width=True)
    st.caption(
        "**Increased Climate Risk:** The frequency of natural disasters consistently grew during this period, "
        "indicating that climate risks did not subside but continued to intensify during the pandemic years."
    )

# =====================================================
#Event Type Distribution (col2)
# =====================================================
with col2:
    st.markdown("Event Type Distribution")

    if len(filtered_data) > 0 and 'event_type' in filtered_data.columns:
        event_dist = filtered_data['event_type'].value_counts().reset_index()
        event_dist.columns = ['Event Type', 'Count']

        fig_pie = px.pie(
            event_dist,
            values='Count',
            names='Event Type',
            title='',
            hole=0.4,
            color='Event Type',
            color_discrete_map=custom_color_map
        )

        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(
            height=400,
            showlegend=True,
            margin=dict(t=20, b=0, l=0, r=0)
        )

        st.plotly_chart(fig_pie, use_container_width=True)
        st.caption(
            "**Peril Frequency Breakdown:** Shows the relative frequency of each disaster type in the current filter. "
            "This drives initial premium allocation and portfolio exposure analysis."
        )
    else:
        st.info("No event type data available for distribution.")

st.markdown("---")


# =================================================================
#CORE DASHBOARD VISUALIZATIONS
# =================================================================

st.subheader("Core Risk Analysis")
col1, col2, col3 = st.columns([1, 1, 1])

# --- Q4: Disaster Risk Profile (Matrix)
with col1:
    st.subheader("Q4: Disaster Risk Profile (Matrix)")
    if len(filtered_data) > 5 and 'event_type' in filtered_data.columns:
        peril_metrics = filtered_data.groupby('event_type').agg(
            Avg_Severity=('severity', 'mean'),
            Frequency=('event_id', 'count')
        ).reset_index()

        max_freq = peril_metrics['Frequency'].max() if not peril_metrics['Frequency'].isna().all() else 1
        peril_metrics['Rel_Frequency'] = peril_metrics['Frequency'] / max_freq

        fig_peril = px.scatter(
            peril_metrics,
            x='Rel_Frequency',
            y='Avg_Severity',
            color='event_type',
            size='Frequency',
            hover_data=['event_type', 'Avg_Severity', 'Frequency'],
            title='Peril Risk Matrix (Severity vs. Frequency)',
            labels={'Rel_Frequency': 'Relative Frequency (0-1)', 'Avg_Severity': 'Average Severity Score (0-10)'},
            color_discrete_map=custom_color_map
        )

        fig_peril.add_hline(y=total_mean_severity, line_dash="dash", line_color="grey")
        fig_peril.add_vline(x=peril_metrics['Rel_Frequency'].mean(), line_dash="dash", line_color="grey")

        fig_peril.add_annotation(x=0.05, y=0.9, text="⚠️ Rare but Disastrous Events", showarrow=False,
                                 xref="paper", yref="paper",
                                 bgcolor="rgba(255, 200, 200, 0.3)",
                                 font=dict(size=10, color="darkred"))
        fig_peril.add_annotation(x=0.85, y=0.9, text="🔴 High Risk Zone", showarrow=False,
                                 xref="paper", yref="paper",
                                 bgcolor="rgba(255, 100, 100, 0.3)",
                                 font=dict(size=10, color="#8B0000"))
        fig_peril.add_annotation(x=0.85, y=0.15, text="⚡ Frequent, Low-Impact Events", showarrow=False,
                                 xref="paper", yref="paper",
                                 bgcolor="rgba(255, 255, 150, 0.3)",
                                 font=dict(size=10, color="#A6A600"))
        fig_peril.add_annotation(x=0.05, y=0.15, text="✅ Minor Issues", showarrow=False,
                                 xref="paper", yref="paper",
                                 bgcolor="rgba(200, 255, 200, 0.3)",
                                 font=dict(size=10, color="darkgreen"))

        fig_peril.update_layout(height=450, showlegend=False, margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig_peril, use_container_width=True)
    else:
        st.info("Not enough data to generate the Risk Matrix.")

# --- Q1: Top 5 Deadliest Events (Table)
with col2:
    st.subheader("Top 5 Deadliest Events")
    if len(filtered_data) > 0 and 'Total Deaths' in filtered_data.columns:
        deadliest = filtered_data.nlargest(5, 'Total Deaths')[
            ['country' if 'country' in filtered_data.columns else 'Country', 'event_type' if 'event_type' in filtered_data.columns else 'Disaster Type', 'Start Year' if 'Start Year' in filtered_data.columns else 'year', 'Total Deaths', 'economic_impact_million_usd']]

        deadliest = deadliest.rename(columns={
            'country': 'Country',
            'event_type': 'Event Type',
            'Start Year': 'Year',
            'Total Deaths': 'Deaths',
            'economic_impact_million_usd': 'Impact ($M)'
        })

        def style_deadliest_dataframe(df):
            styled_df = df.style.format({
                'Impact ($M)': '${:,.0f}',
                'Deaths': '{:,.0f}'
            })

            styled_df = styled_df.set_properties(**{
                'font-weight': 'bold',
                'color': '#8B0000'
            }, subset=['Deaths'])
            return styled_df

        st.dataframe(style_deadliest_dataframe(deadliest), hide_index=True, use_container_width=True)
    else:
        st.info("No data available")

# --- Q2: Most Costly Events (Table)
with col3:
    st.subheader("Top 5 Most Costly Events")
    if len(filtered_data) > 0:
        costliest = filtered_data.nlargest(5, 'economic_impact_million_usd')[
            ['country' if 'country' in filtered_data.columns else 'Country', 'event_type' if 'event_type' in filtered_data.columns else 'Disaster Type', 'Start Year' if 'Start Year' in filtered_data.columns else 'year', 'economic_impact_million_usd', 'Total Affected' if 'Total Affected' in filtered_data.columns else None]]

        costliest = costliest.rename(columns={
            'country': 'Country',
            'event_type': 'Event Type',
            'Start Year': 'Year',
            'economic_impact_million_usd': 'Impact ($M)',
            'Total Affected': 'Affected'
        })

        def style_costliest_dataframe(df):
            styled_df = df.style.format({
                'Impact ($M)': '${:,.0f}',
                'Affected': '{:,.0f}'
            })

            if 'Impact ($M)' in df.columns:
                styled_df = styled_df.set_properties(**{
                    'font-weight': 'bold',
                    'color': '#1F78B4'
                }, subset=['Impact ($M)'])

            return styled_df

        st.dataframe(style_costliest_dataframe(costliest), hide_index=True, use_container_width=True)
    else:
        st.info("No data available")

st.markdown("---")

st.subheader("Executive Summary: COVID-Era Catastrophe Risk for Insurers")

st.info("""
**Final Analytical Commentary: Climate Risk in the COVID Period (2020-2022)**

The analysis of natural disasters between 2020 and 2022 reveals that **climate risk did not pause but was amplified** by concurrent systemic crises. For insurance carriers, this period exposed critical vulnerabilities:

1.  **Life & Health Portfolio Impact (Hyper-Amplified Mortality):**
    * **Finding:** Extreme Temperature (Heatwave) events were the primary drivers of human mortality.
    * **Implication:** This mortality was exponentially worse because healthcare systems were compromised by COVID-19. **Life and Health Catastrophe Models** must evolve beyond pure thermal physics to integrate proxies for **systemic stress** (e.g., hospital capacity, public health strain) to accurately estimate mortality spikes during concurrent crises. This is vital for robust reserving and Solvency II compliance.

2.  **Property & Casualty Claims Impact (Operational Strain):**
    * **Finding:** High Severity and Long Duration events persisted, requiring massive resource mobilization.
    * **Implication:** Pandemic-induced supply chain disruptions, labor shortages, and movement restrictions made the **claims handling process slower and more costly**. This directly translates to elevated **Claims Inflation** and greater volatility in the **Combined Ratio**. **Operational Risk** must now be formally integrated into the total **Cat Risk** profile.

**Strategic Mandate for EuroShield:**

The key lesson is that **operational resilience** is a critical component of the Total Cost of Risk. We must:
* **Model Enhancement:** Prioritize the refinement of models to capture the human impact of heat stress under systemic vulnerability.
* **Operational Contingency:** Accelerate investment in digitalization and automation of the claims lifecycle to ensure high-speed, cost-efficient claims settlement, mitigating the risk of amplified losses during future simultaneous crises.
""")
