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
                'Flood': '#1f78b4',
                'Heatwave': '#e31a1c',
                'Wildfire': '#ff7f00',
                'Drought': '#b15928',
                'Hurricane': '#6a3d9a',
                'Landslide': '#33a02c'
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
        • **{top['event_type']}** peaks in **{peak_month}**  
        • with **{int(top['count'])} recorded events historically**
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
            {freq_icon} **Frequency:** {abs(freq_change):.1f}% {'increase' if freq_change > 0 else 'decrease'} since {year_range[0]}  
            {cost_icon} **Avg. Cost:** {abs(cost_change):.1f}% {'increase' if cost_change > 0 else 'decrease'} since {year_range[0]}
            """)
        else:
            st.warning("No trend data available for the selected filters.")


def render_q4_peril_analyses(filtered_data: pd.DataFrame, premium_by_peril: pd.DataFrame):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Q4: Which Perils Are 'Chronic Headaches' vs. 'Sleeping Giants'?")
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
            fig_peril.add_hline(y=mean_severity, line_dash="dash", line_color="gray", opacity=0.5)
            fig_peril.add_vline(x=mean_frequency, line_dash="dash", line_color="gray", opacity=0.5)
            fig_peril.add_annotation(x=0.05, y=0.9, text="⚠️ Sleeping Giants", showarrow=False,
                                     bgcolor="rgba(255, 200, 200, 0.3)", font=dict(size=10))
            fig_peril.add_annotation(x=4.5, y=0.9, text="🔴 DANGER ZONE", showarrow=False,
                                     bgcolor="rgba(255, 100, 100, 0.3)", font=dict(size=10, color="darkred"))
            fig_peril.add_annotation(x=4.5, y=0.15, text="⚡ Chronic Headaches", showarrow=False,
                                     bgcolor="rgba(255, 255, 150, 0.3)", font=dict(size=10))
            fig_peril.add_annotation(x=0.05, y=0.15, text="✓ Nuisance", showarrow=False,
                                     bgcolor="rgba(200, 255, 200, 0.3)", font=dict(size=10))
            fig_peril.update_layout(height=450, showlegend=True)
            st.plotly_chart(fig_peril, use_container_width=True)
            st.caption("💡 **Bubble size** represents Annual Premium collected by EuroShield")
        else:
            st.warning("No peril data available for the selected filters.")

    with col1:
        st.subheader("Q42: Which Perils Are 'Chronic Headaches' vs. 'Sleeping Giants'?")
        peril_data = filtered_data.groupby(['year', 'event_type']).agg({
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
        if len(peril_analysis) > 0:
            mean_frequency = peril_analysis['average_annual_frequency'].mean()
            mean_severity = peril_analysis['severity'].mean()
            fig_peril = px.scatter(
                peril_analysis,
                x='average_annual_frequency',
                y='severity',
                animation_frame='year',
                animation_group='event_type',
                size='annual_premium_eur_million',
                color='event_type',
                hover_name='event_type',
                hover_data={
                    'average_annual_frequency': ':.2f',
                    'severity': ':.2f',
                    'annual_premium_eur_million': ':,.1f'
                },
                title="Evolution of Peril Risk Positioning (Frequency vs. Severity)"
            )
            fig_peril.update_yaxes(
                tickvals=[0, 0.05, 0.10, 0.15, 0.20, 0.25],
                ticktext=['0', '0.05', '0.10', '0.15', '0.20', '0.25'],
                range=[0, 0.26],
                title_text="Avg. Severity (1–10)"
            )
            fig_peril.add_hline(y=mean_severity, line_dash="dash", line_color="gray", opacity=0.5)
            fig_peril.add_vline(x=mean_frequency, line_dash="dash", line_color="gray", opacity=0.5)
            fig_peril.add_annotation(x=mean_frequency * 0.3, y=mean_severity * 1.3,
                                     text="⚠️ Sleeping Giants", showarrow=False,
                                     bgcolor="rgba(255, 200, 200, 0.3)", font=dict(size=10))
            fig_peril.add_annotation(x=mean_frequency * 1.7, y=mean_severity * 1.3,
                                     text="🔴 DANGER ZONE", showarrow=False,
                                     bgcolor="rgba(255, 100, 100, 0.3)", font=dict(size=10, color="darkred"))
            fig_peril.add_annotation(x=mean_frequency * 1.7, y=mean_severity * 0.7,
                                     text="⚡ Chronic Headaches", showarrow=False,
                                     bgcolor="rgba(255, 255, 150, 0.3)", font=dict(size=10))
            fig_peril.add_annotation(x=mean_frequency * 0.3, y=mean_severity * 0.7,
                                     text="✓ Nuisance", showarrow=False,
                                     bgcolor="rgba(200, 255, 200, 0.3)", font=dict(size=10))
            fig_peril.update_layout(
                height=500,
                showlegend=True,
                xaxis_title="Avg. Annual Frequency (events/year)",
                yaxis_title="Avg. Severity (1–10)",
                hovermode="closest"
            )
            st.plotly_chart(fig_peril, use_container_width=True)
            st.caption(
                "💡 **Bubble size** represents Annual Premium collected by EuroShield | Animation shows yearly evolution")
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
            fig_growth.add_hline(y=mean_severity_growth, line_dash="dash", line_color="gray", opacity=0.5)
            fig_growth.add_vline(x=mean_events, line_dash="dash", line_color="gray", opacity=0.5)
            fig_growth.add_annotation(
                x=mean_events * 0.3, y=mean_severity_growth * 0.7,
                text="🎯 Safe Harbor Markets",
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
                        💡 **GROWTH OPPORTUNITIES:**  
                        Based on low risk + low market share, consider expansion in:
                        {chr(10).join([f"• **{row['country']}** ({row['market_share_percent']:.1f}% share, {int(row['total_events'])} events, severity {row['severity']:.1f})" for _, row in safe_markets.iterrows()])}
                        """)
            st.caption("💡 **Darker blue** = Higher market share (established) | **Lighter blue** = Lower market share (opportunity)")
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
                fig_pie = px.pie(event_dist, values='Count', names='Event Type', title='', hole=0.4)
                fig_pie.update_layout(height=300, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No data available")

        st.markdown("---")
        st.header("📋 Detailed Event Records")
        if len(filtered_data) > 0:
            display_cols = [
                'country', 'event_type', 'Start Year', 'Start Month',
                'severity', 'Total Deaths', 'Total Affected',
                'economic_impact_million_usd', 'duration_days', 'Location'
            ]
            display_cols = [col for col in display_cols if col in filtered_data.columns]
            display_data = filtered_data[display_cols].copy()
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
            if 'Severity' in display_data.columns:
                display_data['Severity'] = display_data['Severity'].round(1)
            if 'Impact ($M)' in display_data.columns:
                display_data['Impact ($M)'] = display_data['Impact ($M)'].round(1)
            if 'Deaths' in display_data.columns:
                display_data['Deaths'] = display_data['Deaths'].fillna(0).astype(int)
            if 'Affected' in display_data.columns:
                display_data['Affected'] = display_data['Affected'].fillna(0).astype(int)
            if 'Severity' in display_data.columns:
                display_data = display_data.sort_values('Severity', ascending=False)
            st.dataframe(display_data, hide_index=True, use_container_width=True, height=400)
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
        st.header("📈 Summary Statistics")
        if len(filtered_data) > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Average Event Duration",
                    f"{filtered_data['duration_days'].mean():.1f} days" if 'duration_days' in filtered_data.columns else "N/A"
                )
            with col2:
                st.metric("Median Severity", f"{filtered_data['severity'].median():.1f}/10")
            insured_damage_col = "Insured Damage, Adjusted ('000 US$)"
            with col3:
                st.metric(
                    "Total Insured Damage",
                    f"${filtered_data[insured_damage_col].sum() / 1000:,.0f}M" if insured_damage_col in filtered_data.columns else "N/A"
                )
            with col4:
                st.metric("Events per Year", f"{len(filtered_data) / max(1, filtered_data['year'].nunique()):.1f}")

            st.subheader("🔗 Risk Correlations")
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
        st.header("⚠️ Risk Alerts & Strategic Recommendations")
        if len(filtered_data) > 0:
            alerts = []
            if len(filtered_data) > 10:
                recent_years = filtered_data[filtered_data['year'] >= max(filtered_data['year']) - 2]
                older_years = filtered_data[filtered_data['year'] < max(filtered_data['year']) - 2]
                if len(recent_years) > 0 and len(older_years) > 0:
                    recent_freq = len(recent_years) / max(1, recent_years['year'].nunique())
                    older_freq = len(older_years) / max(1, older_years['year'].nunique())
                    if recent_freq > older_freq * 1.3:
                        alerts.append({
                            'type': '🔴 HIGH ALERT',
                            'message': f'Event frequency has increased by {((recent_freq / older_freq - 1) * 100):.0f}%' \
                                       f' in recent years',
                            'recommendation': 'Consider increasing reserves and reviewing premium structures'
                        })
            high_severity = filtered_data[filtered_data['severity'] > 7]
            if len(high_severity) > 0:
                alerts.append({
                    'type': '⚠️ WARNING',
                    'message': f'{len(high_severity)} high-severity events (>7/10) detected',
                    'recommendation': 'Review coverage limits and reinsurance arrangements for affected regions'
                })
            # peril_coverage variable is passed for parity with original checks
            total_impact = filtered_data['economic_impact_million_usd'].sum()
            if peril_coverage == "Uncovered Perils" and total_impact > 1000:
                alerts.append({
                    'type': '💡 OPPORTUNITY',
                    'message': f'Uncovered perils show ${total_impact:,.0f}M in economic impact',
                    'recommendation': 'Consider developing new insurance products for these emerging risks'
                })
            growth_data = filtered_data.groupby('country').agg({'event_id': 'count', 'severity': 'mean'}).reset_index()
            growth_data = pd.merge(growth_data, portfolio, on='country', how='inner')
            if st.session_state.selected_country != "All Europe":
                country_data = growth_data[growth_data['country'] == st.session_state.selected_country]
                if len(country_data) > 0:
                    ms = country_data['market_share_percent'].iloc[0]
                    sev = country_data['severity'].iloc[0]
                    if ms < 5 and sev < 5:
                        alerts.append({
                            'type': '🎯 GROWTH OPPORTUNITY',
                            'message': f"{st.session_state.selected_country} shows low risk (severity {sev:.1f}) with low market share ({ms:.1f}%)",
                            'recommendation': 'Prioritize market expansion efforts in this region'
                        })
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
