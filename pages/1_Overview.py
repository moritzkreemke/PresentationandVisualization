import folium
import streamlit as st
from datetime import datetime

from streamlit_folium import st_folium

from data_loader import load_data, country_centroids
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk


def render_q1_map(filtered_data: pd.DataFrame, portfolio: pd.DataFrame, country_centroids: dict):
    """Render interactive Folium map with clickable bubbles and PyDeck-style legends"""

    # --- Data preparation ---
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

    map_data = pd.merge(map_data, portfolio, on='country', how='inner')
    map_data['lat'] = map_data['country'].map(lambda c: country_centroids.get(c, {}).get('lat'))
    map_data['lon'] = map_data['country'].map(lambda c: country_centroids.get(c, {}).get('lon'))
    map_data = map_data.dropna(subset=['lat', 'lon'])

    if len(map_data) > 0:
        # Use columns for layout: map on one side, legends on the other
        col1, col2 = st.columns([3, 1])

        with col1:
            # --- Folium Map Creation ---
            m = folium.Map(location=[54, 10], zoom_start=4, tiles="cartodbpositron")

            # Bubble sizes in meters
            min_radius_meters = 20000  # 20 km
            max_radius_meters = 150000  # 150 km

            max_tiv = map_data['total_insured_value_eur_billion'].max()
            min_tiv = map_data['total_insured_value_eur_billion'].min()

            if max_tiv == min_tiv:
                map_data['radius_meters'] = (min_radius_meters + max_radius_meters) / 2
            else:
                map_data['radius_meters'] = map_data['total_insured_value_eur_billion'].apply(
                    lambda tiv: min_radius_meters + ((tiv - min_tiv) / (max_tiv - min_tiv)) * (
                            max_radius_meters - min_radius_meters)
                )

            # Normalize color by severity
            sev = map_data['average_severity']
            sev_min = sev.min()
            sev_max = sev.max()

            # Handle case where all severities are the same
            if sev_max == sev_min:
                map_data['color'] = '#FFA500'  # Orange for uniform severity
            else:
                sev_norm = (sev - sev_min) / (sev_max - sev_min)
                map_data['r'] = (255 - (sev_norm * 105)).astype(int).clip(0, 255)
                map_data['g'] = (125 - (sev_norm * 125)).astype(int).clip(0, 255)
                map_data['b'] = (125 - (sev_norm * 125)).astype(int).clip(0, 255)
                map_data['color'] = map_data.apply(lambda row: f"#{row['r']:02x}{row['g']:02x}{row['b']:02x}", axis=1)

            # Add bubbles
            for _, row in map_data.iterrows():
                tooltip_html = f"""
                <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 250px;">
                    <b style="font-size: 14px;">{row['country']}</b><br/>
                    <hr style="margin: 5px 0; border: none; border-top: 1px solid #ccc;">
                    <b>Event Statistics:</b><br/>
                    Avg. Event Severity: <b>{row['average_severity']:.1f}/10</b><br/>
                    Total Events: <b>{int(row['total_events']):,}</b><br/>
                    Total Deaths: <b>{int(row['Total Deaths']):,}</b><br/>
                    People Affected: <b>{int(row['Total Affected']):,}</b><br/>
                    Economic Impact: <b>${row['economic_impact_million_usd']:,.0f}M</b><br/>
                    <br/>
                    <b>EuroShield Portfolio:</b><br/>
                    Policies: <b>{int(row['policy_count']):,}</b><br/>
                    Total Insured Value: <b>€{row['total_insured_value_eur_billion']:.1f}B</b><br/>
                    Annual Premium: <b>€{row['annual_premium_eur_million']:.1f}M</b><br/>
                    Market Share: <b>{row['market_share_percent']:.1f}%</b>
                </div>
                """

                folium.Circle(
                    location=[row['lat'], row['lon']],
                    radius=row['radius_meters'],
                    color=row['color'],
                    fill=True,
                    fill_color=row['color'],
                    fill_opacity=0.6,
                    weight=2,
                    popup=row['country'],
                    tooltip=tooltip_html
                ).add_to(m)

            map_output = st_folium(m, width='100%', height=500)

        with col2:
            # --- Legend for BUBBLE SIZE: Total Insured Value ---
            st.markdown("**Bubble size**: Total Insured Value")

            max_val = map_data['total_insured_value_eur_billion'].max()
            min_val = map_data['total_insured_value_eur_billion'].min()

            legend_values = [
                max_val,
                max_val / 2,
                min_val if min_val > 0 else 0.1
            ]

            legend_values.sort(reverse=True)

            for val in legend_values:
                # Calculate radius for this specific value
                if max_tiv == min_tiv:
                    display_radius = (min_radius_meters + max_radius_meters) / 2
                else:
                    display_radius = min_radius_meters + ((val - min_tiv) / (max_tiv - min_tiv)) * (
                            max_radius_meters - min_radius_meters)

                # Scale for display in Streamlit
                display_size_svg = max(5, int(display_radius / 3000))

                st.markdown(f"""
                    <div style="display: flex; align-items: center; margin-bottom: 5px;">
                        <svg height="{display_size_svg}" width="{display_size_svg}">
                            <circle cx="{display_size_svg / 2}" cy="{display_size_svg / 2}" r="{display_size_svg / 2}" fill="#808080" />
                        </svg>
                        <span style="margin-left: 10px;">€{val:.1f} Billions</span>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # --- Legend for COLOR: Average Event Severity ---
            st.markdown("**Color intensity**: Average Event Severity")

            st.markdown("""
                <div style="
                    background: linear-gradient(to right, 
                        rgb(255, 125, 125),
                        rgb(150, 0, 0)
                    );
                    height: 20px;
                    width: 100%;
                    border-radius: 5px;
                    margin-top: 5px;
                "></div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; margin-top: 5px;">
                    <span>Low (1/10)</span>
                    <span>High (10/10)</span>
                </div>
            """, unsafe_allow_html=True)

        # Check if a bubble was clicked
        if map_output and map_output.get("last_object_clicked_popup"):
            clicked_country = map_output["last_object_clicked_popup"]

            # Update session state only if a *new* country is clicked to avoid loops
            if st.session_state.selected_country != clicked_country:
                st.session_state.selected_country = clicked_country
                st.switch_page("pages/2_Deep_Dive.py")

        return map_output
    else:
        st.warning("No data available for the selected filters.")
        return None


def render_q2_q3_seasonal_and_trend(filtered_data: pd.DataFrame, year_range: tuple):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Q2: When Should We Prepare for Seasonal Surges?")

        key_events = ['Flood', 'Heatwave', 'Wildfire', 'Drought', 'Hurricane']
        seasonal_data = filtered_data[filtered_data['event_type'].isin(key_events)]

        monthly_counts = (
            seasonal_data.groupby(['month', 'event_type'])
            .size()
            .reset_index(name='count')
        )

        monthly_counts['count_smooth'] = monthly_counts.groupby('event_type')['count'].transform(
            lambda x: x.rolling(window=2, min_periods=1).mean()
        )

        month_order = list(range(1, 13))
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        fig_season = px.line(
            monthly_counts,
            x='month',
            y='count_smooth',
            color='event_type',
            markers=True,
            labels={'month': 'Month', 'count_smooth': 'Number of Events (Smoothed)', 'event_type': 'Event Type'},
            title=f"Seasonal Patterns of Climate Events - All Europe",
            color_discrete_map={
                'Flood': 'blue',
                'Heatwave': 'darkorange',
                'Wildfire': 'brown',
                'Drought': 'yellow',
                'Hurricane': 'darkorchid',
                'Landslide': 'slategray'
            }
        )

        fig_season.update_layout(
            height=400,
            template="simple_white",
            xaxis=dict(
                tickmode='array',
                tickvals=month_order,
                ticktext=month_names
            )
        )

        st.plotly_chart(fig_season, width='stretch')

        if len(monthly_counts) > 0:
            top = monthly_counts.sort_values('count', ascending=False).iloc[0]
            peak_month = month_names[int(top['month']) - 1]
            st.info(f"""
        **Seasonal Insight:**  
        The most pronounced seasonal pattern is **{top['event_type']}**, which reaches its highest activity in **{peak_month}**.  
        This reflects **{int(top['count'])} recorded events** during that month in the selected region and timeframe.

        Seasonality matters: different hazards peak at different times of year, so preparedness and resource planning should **adapt to the seasonal cycle** rather than stay constant.
        """)

    with col2:
        st.subheader("Q3: Are Key Perils Becoming More Frequent or Costly?")

        yearly_trends = filtered_data.groupby('year').agg({
            'event_id': 'count',
            'economic_impact_million_usd': 'mean'
        }).reset_index()

        yearly_trends.rename(columns={
            'event_id': 'event_count',
            'economic_impact_million_usd': 'avg_economic_impact'
        }, inplace=True)

        if len(yearly_trends) > 0:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=yearly_trends['year'],
                y=yearly_trends['event_count'],
                name='Event Count',
                marker_color='lightgray',
                yaxis='y'
            ))
            fig_trend.add_trace(go.Scatter(
                x=yearly_trends['year'],
                y=yearly_trends['avg_economic_impact'],
                name='Avg. Economic Impact ($M)',
                mode='lines+markers',
                marker=dict(size=8, color='red'),
                line=dict(color='red', width=3),
                yaxis='y2'
            ))
            fig_trend.update_layout(
                title=f'Climate Risk Trend - All Europe ({year_range[0]}-{year_range[1]})',
                xaxis=dict(title='Year'),
                yaxis=dict(title='Event Count', side='left'),
                yaxis2=dict(title='Avg. Economic Impact ($M)', overlaying='y', side='right'),
                hovermode='x unified',
                height=400
            )
            st.plotly_chart(fig_trend, width='stretch')

            if len(yearly_trends) > 1:
                freq_change = ((yearly_trends['event_count'].iloc[-1] - yearly_trends['event_count'].iloc[0]) / (
                        yearly_trends['event_count'].iloc[0] + 1) * 100)
                cost_change = (
                            (yearly_trends['avg_economic_impact'].iloc[-1] - yearly_trends['avg_economic_impact'].iloc[
                                0]) / (yearly_trends['avg_economic_impact'].iloc[0] + 1) * 100)
                freq_icon = "↗️" if freq_change > 0 else "↘️"
                cost_icon = "↗️" if cost_change > 0 else "↘️"
                st.info(f"""
            **Trend Insight ({year_range[0]}–{year_range[1]}):**

            • **Event Frequency:** {abs(freq_change):.1f}% {'increase' if freq_change > 0 else 'decrease'}  
              Climate events are becoming **{'more' if freq_change > 0 else 'less'} frequent**, meaning insurers face **a {'higher' if freq_change > 0 else 'lower'} number of claim-triggering events** over time.

            • **Average Economic Impact per Event:** {abs(cost_change):.1f}% {'increase' if cost_change > 0 else 'decrease'}  
             This reflects how the **typical financial severity** of each event has changed.

            **Why it matters:**  
            For insurance and risk planning, **more frequent events** can increase **overall portfolio exposure**, even when **average per-event cost decreases**.  
            Risk strategies should account for **both frequency trends and accumulated annual loss potential**, not just individual event severity.
            """)
        else:
            st.warning("No trend data available for the selected filters.")


def render_q4_peril_analyses(filtered_data: pd.DataFrame, premium_by_peril: pd.DataFrame):
    st.subheader("Q4: Disaster Risk Profile: Frequency vs. Impact")

    peril_data = filtered_data.groupby('event_type').agg({
        'severity': 'mean',
        'event_id': 'count'
    }).reset_index()

    years_in_data = filtered_data['year'].nunique()
    if years_in_data > 0:
        peril_data['average_annual_frequency'] = peril_data['event_id'] / years_in_data
    else:
        peril_data['average_annual_frequency'] = 0

    peril_analysis = pd.merge(peril_data, premium_by_peril, on='event_type', how='left')
    peril_analysis['annual_premium_eur_million'] = peril_analysis['annual_premium_eur_million'].fillna(0)

    custom_color_map = {
        "Drought": "yellow",
        "Earthquake": "limegreen",
        "Epidemic": "hotpink",
        "Flood": "blue",
        "Glacial Lake Outburst Flood": "aqua",
        "Heatwave": "darkorange",
        "Hurricane": "darkorchid",
        "Landslide": "slategray",
        "Volcanic": "red",
        "Wildfire": "brown"
    }

    if len(peril_analysis) > 0:
        mean_frequency = peril_analysis['average_annual_frequency'].mean()
        mean_severity = peril_analysis['severity'].mean()

        fig_peril = px.scatter(
            peril_analysis,
            x='average_annual_frequency',
            y='severity',
            size='annual_premium_eur_million',
            color='event_type',
            hover_name='event_type',
            color_discrete_map=custom_color_map,
            hover_data={
                'average_annual_frequency': ':.1f',
                'severity': ':.1f',
                'annual_premium_eur_million': ':,.1f'
            },
            title='Risk Matrix: Frequency vs. Severity',
            labels={
                'average_annual_frequency': 'Avg. Annual Frequency (events/year)',
                'severity': 'Avg. Severity'
            }
        )

        fig_peril.add_hline(y=mean_severity, line_dash="dash", line_color="gray", opacity=0.5)
        fig_peril.add_vline(x=mean_frequency, line_dash="dash", line_color="gray", opacity=0.5)

        fig_peril.add_annotation(x=0.05, y=0.9, text="Rare but Disastrous Events", showarrow=False,
                                 bgcolor="rgba(255, 200, 200, 0.3)",
                                 font=dict(size=10, color="darkred"))

        fig_peril.add_annotation(x=4.5, y=0.9, text="High Risk Zone", showarrow=False,
                                 bgcolor="rgba(255, 100, 100, 0.3)",
                                 font=dict(size=10, color="#8B0000"))

        fig_peril.add_annotation(x=4.5, y=0.15, text="Frequent, Low-Impact Events", showarrow=False,
                                 bgcolor="rgba(255, 255, 150, 0.3)",
                                 font=dict(size=10, color="#A6A600"))

        fig_peril.add_annotation(x=0.05, y=0.15, text="Minor Issues", showarrow=False,
                                 bgcolor="rgba(200, 255, 200, 0.3)",
                                 font=dict(size=10, color="darkgreen"))

        fig_peril.update_layout(height=450, showlegend=True)

        st.plotly_chart(fig_peril, width='stretch')

        most_frequent = peril_analysis.loc[peril_analysis['average_annual_frequency'].idxmax(), 'event_type']
        most_risky = peril_analysis.loc[peril_analysis['severity'].idxmax(), 'event_type']

        st.info(
            "This chart compares how often each disaster occurs (x-axis) and its average impact (y-axis).  \n"
            "Bubble size reflects the insurance premium collected, showing financial exposure.  \n"
            "Perils in the upper-right are both frequent and severe, representing the highest overall risk.  \n\n"
            "---  \n"
            "**Summary:**  \n"
            f"- **Most frequent event:** {most_frequent}  \n"
            f"- **Highest severity event:** {most_risky}"
        )
    else:
        st.warning("No peril data available for the selected filters.")


def render_q5_growth_and_insights(filtered_data: pd.DataFrame, portfolio: pd.DataFrame, year_range: tuple,
                                  peril_coverage: str):
    st.subheader("Q5: Where Are Our Safest Markets for Profitable Growth?")

    growth_data = filtered_data.groupby('country').agg({
        'event_id': 'count',
        'severity': 'mean',
    }).reset_index()
    growth_data.rename(columns={'event_id': 'total_events'}, inplace=True)
    growth_data = pd.merge(growth_data, portfolio, on='country', how='inner')

    if len(growth_data) > 0:
        mean_events = growth_data['total_events'].mean()
        mean_severity_growth = growth_data['severity'].mean()

        fig_growth = px.scatter(
            growth_data,
            x='total_events',
            y='severity',
            color='market_share_percent',
            color_continuous_scale=["#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08306b"],
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
        fig_growth.update_traces(marker=dict(size=20))
        fig_growth.add_hline(y=mean_severity_growth, line_dash="dash", line_color="gray", opacity=0.5)
        fig_growth.add_vline(x=mean_events, line_dash="dash", line_color="gray", opacity=0.5)
        fig_growth.add_annotation(
            x=mean_events * 0.3, y=mean_severity_growth * 0.7,
            text="Safe Harbor Markets",
            showarrow=False,
            bgcolor="rgba(150, 255, 150, 0.3)",
            font=dict(size=12, color="darkgreen")
        )
        fig_growth.update_layout(height=450)
        st.plotly_chart(fig_growth, width='stretch')

        safe_markets = growth_data[
            (growth_data['total_events'] < mean_events) &
            (growth_data['severity'] < mean_severity_growth) &
            (growth_data['market_share_percent'] < 5)
            ].nsmallest(3, 'market_share_percent')

        if len(safe_markets) > 0:
            st.success(f"""
                **GROWTH OPPORTUNITIES:**  
                The countries where we see growth opportunities are the ones with low risk and low market share, so consider expansion in:
                {chr(10).join([f"• **{row['country']}** ({row['market_share_percent']:.1f}% share, {int(row['total_events'])} events, severity {row['severity']:.1f})" for _, row in safe_markets.iterrows()])}
            """)
    else:
        st.warning("No growth opportunity data available for the selected filters.")

    st.markdown("---")
    st.header("📊 Additional Insights")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Top 5 Deadliest Events")
        if len(filtered_data) > 0:
            deadliest = filtered_data.nlargest(5, 'Total Deaths')[
                ['country', 'event_type', 'Start Year', 'Total Deaths', 'economic_impact_million_usd']]
            deadliest = deadliest.rename(columns={
                'country': 'Country',
                'event_type': 'Event Type',
                'Start Year': 'Year',
                'Total Deaths': 'Deaths',
                'economic_impact_million_usd': 'Impact ($M)'
            })
            styled_deadliest = deadliest.style.map(
                lambda v: 'color: red;', subset=['Deaths']
            )
            st.dataframe(styled_deadliest, hide_index=True, width='stretch')
        else:
            st.info("No data available")

    with col2:
        st.subheader("Most Costly Events")
        if len(filtered_data) > 0:
            costliest = filtered_data.nlargest(5, 'economic_impact_million_usd')[
                ['country', 'event_type', 'Start Year', 'economic_impact_million_usd', 'Total Affected']]
            costliest = costliest.rename(columns={
                'country': 'Country',
                'event_type': 'Event Type',
                'Start Year': 'Year',
                'economic_impact_million_usd': 'Impact ($M)',
                'Total Affected': 'Affected'
            })
            styled_costliest = costliest.style.map(
                lambda v: 'color: blue;', subset=['Impact ($M)']
            )
            st.dataframe(styled_costliest, hide_index=True, width='stretch')
        else:
            st.info("No data available")

    with col3:
        st.subheader("Event Type Distribution")
        if len(filtered_data) > 0:
            event_dist = filtered_data['event_type'].value_counts().reset_index()
            event_dist.columns = ['Event Type', 'Count']

            custom_color_map = {
                "Drought": "yellow",
                "Earthquake": "limegreen",
                "Epidemic": "hotpink",
                "Flood": "blue",
                "Glacial Lake Outburst Flood": "aqua",
                "Heatwave": "darkorange",
                "Hurricane": "darkorchid",
                "Landslide": "slategray",
                "Volcanic": "red",
                "Wildfire": "brown"
            }

            fig_pie = px.pie(
                event_dist,
                values='Count',
                names='Event Type',
                title='',
                hole=0.4,
                color='Event Type',
                color_discrete_map=custom_color_map
            )
            fig_pie.update_layout(height=300, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, width='stretch')
        else:
            st.info("No data available")

    st.markdown("---")

    # Key Economic & Portfolio Statistics
    st.header("📈 Key Economic & Portfolio Statistics")

    INSURED_DAMAGE_COL = "Insured Damage, Adjusted ('000 US$)"
    TOTAL_DAMAGE_COL = "Total Damage, Adjusted ('000 US$)"

    total_insured_damage_000_usd = filtered_data[INSURED_DAMAGE_COL].fillna(0).sum()
    total_economic_damage_000_usd = filtered_data[TOTAL_DAMAGE_COL].fillna(0).sum()

    if total_economic_damage_000_usd > 0:
        insurance_penetration_rate = (total_insured_damage_000_usd / total_economic_damage_000_usd) * 100
    else:
        insurance_penetration_rate = 0

    avg_market_share = portfolio['market_share_percent'].mean()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Avg Market Share", f"{avg_market_share:.2f}%")

    with col2:
        st.metric("Total Insured Damage", f"${total_insured_damage_000_usd / 1000:,.0f}M")

    with col3:
        st.metric("Total Economic Damage", f"${total_economic_damage_000_usd / 1_000_000:,.1f}B")

    with col4:
        st.metric("Insurance Penetration", f"{insurance_penetration_rate:.2f}%")

    st.markdown("---")
    st.subheader("Risk Correlations")

    col1, col2 = st.columns(2)

    with col1:
        if len(filtered_data) > 5:
            fig_corr1 = px.scatter(
                filtered_data,
                x='severity',
                y='economic_impact_million_usd',
                color='event_type',
                title='Severity vs. Economic Impact',
                labels={'severity': 'Severity Score (1-10)', 'economic_impact_million_usd': 'Economic Impact ($M)'},
                trendline="ols"
            )
            fig_corr1.update_layout(height=350)
            st.plotly_chart(fig_corr1, width='stretch')

    with col2:
        if 'duration_days' in filtered_data.columns and len(filtered_data) > 5:
            fig_corr2 = px.scatter(
                filtered_data[filtered_data['duration_days'] > 0],
                x='duration_days',
                y='Total Affected',
                color='event_type',
                title='Event Duration vs. People Affected',
                labels={'duration_days': 'Duration (days)', 'Total Affected': 'People Affected'},
                trendline="ols"
            )
            fig_corr2.update_layout(height=350)
            st.plotly_chart(fig_corr2, width='stretch')


# Set page configuration
st.set_page_config(layout="wide", page_title="Overview - EuroShield")

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
st.markdown('<div class="main-header">📊 Portfolio Overview</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Last Updated: {datetime.now().strftime("%B %Y")} | Data Source: EM-DAT International Disaster Database</div>',
    unsafe_allow_html=True)

# Get available years from data
available_years = sorted(data['year'].dropna().unique())
min_year = int(available_years[0]) if len(available_years) > 0 else 1950
max_year = int(available_years[-1]) if len(available_years) > 0 else 2025

# Top filter bar (NO COUNTRY FILTER)
col_f1, col_f2, col_f3 = st.columns([2, 2, 1])

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
    year_range = st.select_slider(
        "Year Range",
        options=list(range(min_year, max_year + 1)),
        value=(min_year, max_year)
    )

with col_f3:
    if st.button("🔄 Reset All", width='stretch'):
        st.session_state.selected_country = "All Europe"
        st.session_state.selected_peril = "All Perils"
        st.session_state.selected_month = None
        st.rerun()

# Breadcrumb trail
breadcrumbs = []
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

# Always show All Europe portfolio stats
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
# Q4: STRATEGIC ANALYSIS
# ============================================================================
render_q4_peril_analyses(filtered_data, premium_by_peril)

st.markdown("---")

# ============================================================================
# Q5: GROWTH AND INSIGHTS
# ============================================================================
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
            2. Click on map bubbles to drill down into country details
            3. Hover over charts for details
            4. Use the Deep Dive page for country-specific analysis

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
    st.write(f"**Region**: All Europe")
    st.write(f"**Peril Coverage**: {peril_coverage}")
    st.write(f"**Year Range**: {year_range[0]} - {year_range[1]}")
    st.write(f"**Events Shown**: {len(filtered_data):,}")
