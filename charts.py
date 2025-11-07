import folium
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pydeck as pdk
from streamlit_folium import st_folium
import importlib

from streamlit_plotly_events import plotly_events


def render_q1_map(filtered_data: pd.DataFrame, portfolio: pd.DataFrame, country_centroids: dict):
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
        # Debug: Check severity values
        st.write("**Debug - Severity Statistics:**")
        st.write(
            f"Min: {map_data['average_severity'].min():.2f}, Max: {map_data['average_severity'].max():.2f}, Mean: {map_data['average_severity'].mean():.2f}")

        # --- Folium Map Creation ---
        m = folium.Map(location=[54, 10], zoom_start=4, tiles="cartodbpositron")

        # 1. CORRECTED: Smaller bubble sizes in meters (20km to 150km)
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

        # 2. Normalize color by severity
        sev = map_data['average_severity']
        sev_min = sev.min()
        sev_max = sev.max()

        # Handle case where all severities are the same
        if sev_max == sev_min:
            map_data['color'] = '#FFA500'  # Orange for uniform severity
        else:
            sev_norm = (sev - sev_min) / (sev_max - sev_min)
            map_data['r'] = (sev_norm * 255).astype(int)
            map_data['g'] = (255 - (sev_norm * 255)).astype(int)
            map_data['b'] = 80
            map_data['color'] = map_data.apply(lambda row: f"#{row['r']:02x}{row['g']:02x}{row['b']:02x}", axis=1)

        # 3. Add bubbles to the map
        for idx, row in map_data.iterrows():
            # CORRECTED: Complete tooltip HTML
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
                weight=2,  # Border thickness
                popup=row['country'],
                tooltip=tooltip_html
            ).add_to(m)

        map_output = st_folium(m, width='100%', height=500)

        st.caption(
            "💡 **Bubble size** represents Total Insured Value | **Color intensity** represents Average Event Severity (green=low, red=high)")

        return map_output

    else:
        st.warning("No data available for the selected filters.")
        return None


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
            st.plotly_chart(fig_trend, width='stretch')

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
            st.plotly_chart(fig_peril, width='stretch')
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
            st.plotly_chart(fig_peril, width='stretch')
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
            st.plotly_chart(fig_growth, width='stretch')

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
                st.dataframe(deadliest, hide_index=True, width='stretch')
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
                st.dataframe(costliest, hide_index=True, width='stretch')
            else:
                st.info("No data available")
        with col3:
            st.subheader("Event Type Distribution")
            if len(filtered_data) > 0:
                event_dist = filtered_data['event_type'].value_counts().reset_index()
                event_dist.columns = ['Event Type', 'Count']
                fig_pie = px.pie(event_dist, values='Count', names='Event Type', title='', hole=0.4)
                fig_pie.update_layout(height=300, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, width='stretch')
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
            st.dataframe(display_data, hide_index=True, width='stretch', height=400)
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



def render_country_deep_dive(data: pd.DataFrame, portfolio: pd.DataFrame, selected_country: str):
    st.markdown("---")
    # Back button and title
    top_cols = st.columns([1, 6, 3])
    with top_cols[0]:
        if st.button("← Back to Overview", width='stretch'):
            st.session_state.mode = 'overview'
            st.session_state.deep_dive_peril = 'All Perils'
            st.rerun()
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
                st.plotly_chart(fig_tree, width='stretch')
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
        st.plotly_chart(fig_combo, width='stretch')
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
        st.plotly_chart(fig_sc, width='stretch')
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
            width='stretch',
            hide_index=True,
            column_config={
                'Investigate': st.column_config.LinkColumn("Investigate", display_text="Search"),
                'Economic Impact (€M)': st.column_config.NumberColumn(format="%.0f")
            }
        )
    else:
        st.info("No events to display for the selected filters.")
