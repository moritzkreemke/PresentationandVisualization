import streamlit as st
import pandas as pd


@st.cache_data
def load_data():
    """Load and preprocess data used by the dashboard.

    Returns:
        tuple: (data, portfolio, premium_by_peril, merged_data)
    """
    # Load the three CSV files
    data = pd.read_csv("data.csv", encoding='utf-8')
    portfolio = pd.read_csv("euroshield_portfolio_by_country.csv")
    premium_by_peril = pd.read_csv("euroshield_premium_by_peril.csv")

    # Clean and prepare the main data
    # Convert numeric columns
    numeric_cols = ['Total Deaths', 'No. Injured', 'No. Affected', 'No. Homeless',
                    'Total Affected', "Total Damage ('000 US$)", "Total Damage, Adjusted ('000 US$)",
                    "Insured Damage ('000 US$)", "Insured Damage, Adjusted ('000 US$)",
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
    data['month_name'] = data['date'].dt.month_name()
    data['year'] = data['Start Year']

    # Calculate event duration in days
    data['duration_days'] = (
        pd.to_datetime(data[['End Year', 'End Month', 'End Day']].rename(
            columns={'End Year': 'year', 'End Month': 'month', 'End Day': 'day'}
        ), errors='coerce') - data['date']
    ).dt.days

    # Derived fields for deep dive analytics
    # Total casualties as deaths + injured
    data['total_casualties'] = data['Total Deaths'].fillna(0) + data['No. Injured'].fillna(0)

    # Proxy for response time (in hours): using event duration when available
    data['response_time_hours'] = (data['duration_days'].fillna(0) * 24).clip(lower=1)

    # Infrastructure damage score (0–10) based on normalized adjusted total damage
    max_adj_damage = data["Total Damage, Adjusted ('000 US$)"].max() if data["Total Damage, Adjusted ('000 US$)"].max() > 0 else 1
    data['infrastructure_damage_score'] = (data["Total Damage, Adjusted ('000 US$)"].fillna(0) / max_adj_damage) * 10

    # Create severity score based on multiple factors (0-10 scale)
    # Normalize deaths, affected, and damage
    max_deaths = data['Total Deaths'].max() if data['Total Deaths'].max() > 0 else 1
    max_affected = data['Total Affected'].max() if data['Total Affected'].max() > 0 else 1
    max_damage = data["Total Damage, Adjusted ('000 US$)"].max() if data[
        "Total Damage, Adjusted ('000 US$)"].max() > 0 else 1

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
        'Landslide': 'Landslide'
    }

    data['event_type'] = data['Disaster Type'].map(disaster_type_mapping).fillna(data['Disaster Type'])

    # Convert economic impact to millions (data is in thousands)
    data['economic_impact_million_usd'] = data["Total Damage, Adjusted ('000 US$)"].fillna(0) / 1000

    # Create unique event ID
    data['event_id'] = data.index

    # Keep only European countries that are in the portfolio
    data = data[data['Country'].isin(portfolio['country'])]

    # Rename Country to country for consistency
    data = data.rename(columns={'Country': 'country'})

    # Merge data with portfolio data
    merged_data = pd.merge(data, portfolio, on='country', how='inner')

    return data, portfolio, premium_by_peril, merged_data


# Country centroids (approximate) for European countries used for the map
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
