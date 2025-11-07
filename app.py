import streamlit as st
from datetime import datetime

from data_loader import load_data, country_centroids
from charts import render_q1_map, render_q2_q3_seasonal_and_trend, render_q4_peril_analyses, render_q5_growth_and_insights

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

# Load data via helper module

data, portfolio, premium_by_peril, merged_data = load_data()

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
render_q1_map(filtered_data, portfolio, country_centroids)

st.markdown("---")

# ============================================================================
# Q2 & Q3: SEASONAL PATTERNS AND TRENDS
# ============================================================================
render_q2_q3_seasonal_and_trend(filtered_data, year_range)

st.markdown("---")

# ============================================================================
# Q4 & Q5: STRATEGIC ANALYSIS
# ============================================================================
render_q4_peril_analyses(filtered_data, premium_by_peril)
render_q5_growth_and_insights(filtered_data, portfolio, year_range, peril_coverage)

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
