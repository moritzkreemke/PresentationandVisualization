import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk


def render_q1_map(filtered_data: pd.DataFrame, portfolio: pd.DataFrame, country_centroids: dict):
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
        min_radius = 10000
        map_data['radius'] = (map_data['total_insured_value_eur_billion'] / map_data[
            'total_insured_value_eur_billion'].max()) * size_scale + 10000

        # Color by severity (green to red gradient)
        sev = map_data['average_severity']
        sev_norm = (sev - sev.min()) / (sev.max() - sev.min() + 1e-9)
        map_data['r'] = (255 - (sev_norm * 105)).astype(int).clip(0, 255)
        map_data['g'] = (125 - (sev_norm * 125)).astype(int).clip(0, 255)
        map_data['b'] = (125 - (sev_norm * 125)).astype(int).clip(0, 255)

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

        #        # Use columns for layout: map on one side, legends on the other
        col1, col2 = st.columns([3, 1])  # Map takes 3 parts, legend takes 1 part

        with col1:
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip=tooltip,
                map_style='light'  # or 'carto-dark' for a dark map
            ), use_container_width=True)

        with col2:
            # --- Legend for BUBBLE SIZE Total Insured Value ---
            st.markdown("**Bubble size** : Total Insured Value")

            # Display some example sizes
            max_val = map_data['total_insured_value_eur_billion'].max()
            min_val = map_data['total_insured_value_eur_billion'].min()

            # We want representative values, not necessarily min/max if they are outliers
            # Let's pick 3 representative values for the legend
            legend_values = [
                max_val,
                max_val / 2,  # Mid-point for example
                min_val if min_val > 0 else 0.1  # Ensure min is not zero for display
            ]

            # Sort in descending order for better display
            legend_values.sort(reverse=True)

            for val in legend_values:
                # Calculate radius for this specific value
                display_radius = (val / max_val) * size_scale + min_radius
                # Scale for display in Streamlit (e.g., divide by a factor for smaller SVG)
                display_size_svg = max(5, int(display_radius / 3000))  # Adjust divisor to fit your UI

                # Using HTML/SVG for a simple circle
                st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 5px;">
                            <svg height="{display_size_svg}" width="{display_size_svg}">
                                <circle cx="{display_size_svg / 2}" cy="{display_size_svg / 2}" r="{display_size_svg / 2}" fill="#808080" />
                            </svg>
                            <span style="margin-left: 10px;">€{val:.1f} Billions </span>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("---")  # Separator

            # --- Legend for COLOR: Average Event Severity ---
            st.markdown("**Color intensity** : Average Event Severity")

            # Generate a simple gradient bar
            st.markdown("""
                    <div style="
                background: linear-gradient(to right, 
                    rgb(255, 125, 125),   /* Light Red - Low severity */
                    rgb(150, 0, 0)        /* Dark Red - High severity */
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

            st.markdown("---")  # Separator


    else:
        st.warning("No data available for the selected filters.")


def render_q2_q3_seasonal_and_trend(filtered_data: pd.DataFrame, year_range: tuple):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Q2: When Should We Prepare for Seasonal Surges?")

        # Keep only climate-relevant perils
        key_events = ['Flood', 'Heatwave', 'Wildfire', 'Drought', 'Hurricane']
        seasonal_data = filtered_data[filtered_data['event_type'].isin(key_events)]

        # Aggregate monthly frequencies
        monthly_counts = (
            seasonal_data.groupby(['month', 'event_type'])
            .size()
            .reset_index(name='count')
        )

        # Smooth noise (rolling mean helps reveal seasonality)
        monthly_counts['count_smooth'] = monthly_counts.groupby('event_type')['count'].transform(
            lambda x: x.rolling(window=2, min_periods=1).mean()
        )

        # Month labels
        month_order = list(range(1, 12 + 1))
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        # Plot
        fig_season = px.line(
            monthly_counts,
            x='month',
            y='count_smooth',
            color='event_type',
            markers=True,
            labels={'month': 'Month', 'count_smooth': 'Number of Events (Smoothed)', 'event_type': 'Event Type'},
            title=f"Seasonal Patterns of Climate Events - {st.session_state.selected_country}",
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

        st.plotly_chart(fig_season, width="stretch")

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
            fig_trend = go.Figure()
            # Bars for event count
            fig_trend.add_trace(go.Bar(
                x=yearly_trends['year'],
                y=yearly_trends['event_count'],
                name='Event Count',
                marker_color='lightgray',
                yaxis='y'
            ))
            # Line for economic impact
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
                title=f'Climate Risk Trend - {st.session_state.selected_country} ({year_range[0]}-{year_range[1]})',
                xaxis=dict(title='Year'),
                yaxis=dict(title='Event Count', side='left'),
                yaxis2=dict(title='Avg. Economic Impact ($M)', overlaying='y', side='right'),
                hovermode='x unified',
                height=400
            )
            st.plotly_chart(fig_trend, use_container_width=True)

            if len(yearly_trends) > 1:
                freq_change = ((yearly_trends['event_count'].iloc[-1] - yearly_trends['event_count'].iloc[0]) / (
                        yearly_trends['event_count'].iloc[0] + 1) * 100)
                cost_change = ((yearly_trends['avg_economic_impact'].iloc[-1] - yearly_trends['avg_economic_impact'].iloc[
                    0]) / (yearly_trends['avg_economic_impact'].iloc[0] + 1) * 100)
                freq_icon = "↗️" if freq_change > 0 else "↘️"
                cost_icon = "↗️" if cost_change > 0 else "↘️"
                st.info(f"""
            **Trend Insight ({year_range[0]}–{year_range[1]}):**

            • **Event Frequency:** {abs(freq_change):.1f}% {'increase' if freq_change > 0 else 'decrease'}  
              Climate events are becoming **more frequent**, meaning insurers face **a higher number of claim-triggering events** over time.

            • **Average Economic Impact per Event:** {abs(cost_change):.1f}% {'increase' if cost_change > 0 else 'decrease'}  
             This reflects how the **typical financial severity** of each event has changed.

            **Why it matters:**  
            For insurance and risk planning, **more frequent events** can increase **overall portfolio exposure**, even when **average per-event cost decreases**.  
            Risk strategies should account for **both frequency trends and accumulated annual loss potential**, not just individual event severity.
            """)

        else:
            st.warning("No trend data available for the selected filters.")


def render_q4_peril_analyses(filtered_data: pd.DataFrame, premium_by_peril: pd.DataFrame):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Q4: Disaster Risk Profile: Frequency vs. Impact")

        # --- Prepare data ---
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

        # --- Plot if data exists ---
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

            # --- Reference lines & zone annotations ---
            fig_peril.add_hline(y=mean_severity, line_dash="dash", line_color="gray", opacity=0.5)
            fig_peril.add_vline(x=mean_frequency, line_dash="dash", line_color="gray", opacity=0.5)

            # 1.Rare but Disastrous Events
            fig_peril.add_annotation(x=0.05, y=0.9, text="Rare but Disastrous Events", showarrow=False,
                                     bgcolor="rgba(255, 200, 200, 0.3)",
                                     font=dict(size=10, color="darkred"))

            # 2. High Risk Zone
            fig_peril.add_annotation(x=4.5, y=0.9, text="High Risk Zone", showarrow=False,
                                     bgcolor="rgba(255, 100, 100, 0.3)",
                                     font=dict(size=10, color="#8B0000"))

            # 3. Frequent, Low-Impact Events
            fig_peril.add_annotation(x=4.5, y=0.15, text="Frequent, Low-Impact Events", showarrow=False,
                                     bgcolor="rgba(255, 255, 150, 0.3)",
                                     font=dict(size=10, color="#A6A600"))

            # 4.  Minor Issues
            fig_peril.add_annotation(x=0.05, y=0.15, text="Minor Issues", showarrow=False,
                                     bgcolor="rgba(200, 255, 200, 0.3)",
                                     font=dict(size=10, color="darkgreen"))

            fig_peril.update_layout(height=450, showlegend=True)

            # --- Display chart ---
            st.plotly_chart(fig_peril, use_container_width=True)


            # --- Dynamic summary below chart ---
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


def render_q5_growth_and_insights(filtered_data: pd.DataFrame, portfolio: pd.DataFrame, year_range: tuple, peril_coverage: str):
    col2 = st.container()  # maintain layout similar to original
    with col2:
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
            st.plotly_chart(fig_growth, use_container_width=True)

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
                #
                styled_deadliest = deadliest.style.map(
                    lambda v: 'color: red;', subset=['Deaths']
                )
                st.dataframe(styled_deadliest, hide_index=True, use_container_width=True)
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
                #
                styled_costliest = costliest.style.map(
                    lambda v: 'color: blue;', subset=['Impact ($M)']
                )
                st.dataframe(styled_costliest, hide_index=True, use_container_width=True)
            else:
                st.info("No data available")

        with col3:
            st.subheader("Event Type Distribution")
            if len(filtered_data) > 0:
                event_dist = filtered_data['event_type'].value_counts().reset_index()
                event_dist.columns = ['Event Type', 'Count']

                # Define your custom colors
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

                # Create pie chart with custom colors
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
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No data available")

        st.markdown("---")


        df_country = pd.read_csv('euroshield_portfolio_by_country.csv')
        df_disaster = pd.read_csv('data.csv')

        avg_market_share = df_country['market_share_percent'].mean()

        INSURED_DAMAGE_COL = "Insured Damage, Adjusted ('000 US$)"
        TOTAL_DAMAGE_COL = "Total Damage, Adjusted ('000 US$)"

        total_insured_damage_000_usd = df_disaster[INSURED_DAMAGE_COL].fillna(0).sum()

        total_economic_damage_000_usd = df_disaster[TOTAL_DAMAGE_COL].fillna(0).sum()

        if total_economic_damage_000_usd > 0:
            insurance_penetration_rate = (total_insured_damage_000_usd / total_economic_damage_000_usd) * 100
        else:
            insurance_penetration_rate = 0

        st.header("📈 Key Economic & Portfolio Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Avg Market Share",
                f"{avg_market_share:.2f}%"
            )

        with col2:
            # Insured Damage is formatted in Millions (M)
            st.metric(
                "Total Insured Damage",
                f"${total_insured_damage_000_usd / 1000:,.0f}M"
            )

        with col3:
            # Economic Damage is formatted in Billions (B) for scale
            st.metric(
                "Total Economic Damage",
                f"${total_economic_damage_000_usd / 1_000_000:,.1f}B"
            )

        with col4:
            st.metric(
                "Insurance Penetration",
                f"{insurance_penetration_rate:.2f}%"
            )
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
                st.plotly_chart(fig_corr1, use_container_width=True)
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
                st.plotly_chart(fig_corr2, use_container_width=True)

        st.markdown("---")

