# streamlit_weather_app.py
# Interactive Weather Dashboard (English UI)
# - Click on the map to choose a location
# - Fetches hourly weather from Open-Meteo
# - Shows temperature, precipitation and wind in tabs
#
# Local run:
#   pip install streamlit requests pandas folium streamlit-folium
#   streamlit run streamlit_weather_app.py
#
# Streamlit Cloud:
#   push this file to GitHub and set the file path to streamlit_weather_app.py

import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Open-Meteo Interactive Weather Dashboard", page_icon="🌦️", layout="wide")

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_REVERSE_GEOCODE = "https://geocoding-api.open-meteo.com/v1/reverse"

DEFAULT_LAT, DEFAULT_LON = 37.5665, 126.9780   # Seoul
DEFAULT_ZOOM = 5

# ------------------------ Helpers ------------------------
@st.cache_data(ttl=3600)
def reverse_geocode(lat: float, lon: float) -> str:
    """Return a human-readable place name using Open-Meteo reverse geocoding API."""
    try:
        r = requests.get(OPEN_METEO_REVERSE_GEOCODE,
                         params={"latitude": lat, "longitude": lon, "language": "en"},
                         timeout=20)
        r.raise_for_status()
        js = r.json() or {}
        results = js.get("results") or []
        if results:
            item = results[0]
            # Try to compose a readable name
            city = item.get("name")
            admin = item.get("admin1") or item.get("admin2") or ""
            country = item.get("country") or ""
            parts = [p for p in [city, admin, country] if p]
            return ", ".join(parts)
    except Exception:
        pass
    return f"{lat:.3f}, {lon:.3f}"

@st.cache_data(ttl=900, show_spinner=False)
def fetch_hourly_weather(lat: float, lon: float, hours: int = 48) -> pd.DataFrame:
    """Fetch hourly weather for the next N hours from Open-Meteo and return a tidy DataFrame."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,windspeed_10m,relative_humidity_2m",
        "forecast_days": 7,  # enough to cover 48+ hours
        "timezone": "auto",
    }
    r = requests.get(OPEN_METEO_FORECAST, params=params, timeout=25)
    r.raise_for_status()
    js = r.json() or {}
    hourly = js.get("hourly") or {}
    df = pd.DataFrame(hourly)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
        # Limit to desired horizon
        df = df.iloc[:hours]
    # Rename columns for nicer labels
    rename_map = {
        "temperature_2m": "Temperature (°C)",
        "precipitation": "Precipitation (mm)",
        "windspeed_10m": "Wind Speed (km/h)",
        "relative_humidity_2m": "Relative Humidity (%)",
    }
    df = df.rename(columns=rename_map)
    return df

# ------------------------ UI ------------------------
st.title("🌦️ Open-Meteo Interactive Weather Dashboard")
st.caption("Click on the map to choose a location. The app fetches hourly weather from Open-Meteo (no API key required).")

with st.sidebar:
    st.header("Controls")
    st.write("1) Click a point on the map.\n\n2) Choose how many hours to display.")
    hours = st.slider("Hours to display", min_value=12, max_value=120, value=48, step=6)
    st.write("Tip: enable 'wide' layout for more chart space (already set by default).")

st.subheader("1️⃣ Pick a region (click on the map)")
m = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=DEFAULT_ZOOM, control_scale=True, tiles="OpenStreetMap")
folium.Marker([DEFAULT_LAT, DEFAULT_LON], tooltip="Default: Seoul").add_to(m)
map_state = st_folium(m, height=520, returned_objects=[])

clicked = None
if isinstance(map_state, dict) and "last_clicked" in map_state and map_state["last_clicked"]:
    clicked = map_state["last_clicked"]
    lat, lon = clicked.get("lat"), clicked.get("lng")
else:
    lat, lon = DEFAULT_LAT, DEFAULT_LON

st.info("Click anywhere on the map to fetch weather data for that location.")

st.subheader("2️⃣ Hourly Weather")
place_name = reverse_geocode(lat, lon)
st.caption(f"Location: **{place_name}**  (lat: {lat:.4f}, lon: {lon:.4f})")

try:
    with st.spinner("Fetching hourly weather…"):
        df = fetch_hourly_weather(lat, lon, hours=hours)
except Exception as e:
    st.error(f"Failed to fetch weather data: {e}")
    st.stop()

if df.empty:
    st.warning("No data returned. Try clicking another location or reducing the time window.")
    st.stop()

# Summary cards
latest = df.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temperature (now)", f"{latest['Temperature (°C)']:.1f} °C")
c2.metric("Wind Speed (now)", f"{latest['Wind Speed (km/h)']:.0f} km/h")
c3.metric("Precipitation (now)", f"{latest['Precipitation (mm)']:.2f} mm")
c4.metric("RH (now)", f"{latest['Relative Humidity (%)']:.0f} %")

# Charts in tabs
tab1, tab2, tab3 = st.tabs(["Temperature", "Precipitation", "Wind & Humidity"])

with tab1:
    st.line_chart(df[["Temperature (°C)"]])

with tab2:
    st.area_chart(df[["Precipitation (mm)"]])

with tab3:
    st.line_chart(df[["Wind Speed (km/h)", "Relative Humidity (%)"]])

st.markdown("---")
st.caption("Data Source: Open‑Meteo.com (Forecast & Geocoding). Map tiles © OpenStreetMap contributors.")
