# streamlit_weather_app_v2.py
# Open‑Meteo Weather Dashboard (robust version, English UI)
# - Handles missing deps with a clear message
# - Safer plotting when some variables are missing
# - Uses the *latest available* hour for metrics
#
# Run locally:
#   pip install -r requirements.txt
#   streamlit run streamlit_weather_app_v2.py

import sys
import importlib
import requests
import pandas as pd
import streamlit as st

# ---- Dependencies check (folium / streamlit-folium) ----
_missing = []
try:
    folium = importlib.import_module("folium")
except Exception:
    folium = None
    _missing.append("folium")
try:
    st_folium_mod = importlib.import_module("streamlit_folium")
    st_folium = getattr(st_folium_mod, "st_folium")
except Exception:
    st_folium = None
    _missing.append("streamlit-folium")

st.set_page_config(page_title="Open‑Meteo Interactive Weather Dashboard", page_icon="🌦️", layout="wide")

if _missing:
    st.error(
        "Missing required packages: **%s**.\n\n"
        "Please add them to your `requirements.txt` and redeploy:\n"
        "```\nstreamlit\nrequests\npandas\nfolium\nstreamlit-folium\n```\n" % (", ".join(_missing))
    )
    st.stop()

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_REVERSE_GEOCODE = "https://geocoding-api.open-meteo.com/v1/reverse"

DEFAULT_LAT, DEFAULT_LON = 37.5665, 126.9780  # Seoul
DEFAULT_ZOOM = 5

# ------------------------ Helpers ------------------------
@st.cache_data(ttl=3600)
def reverse_geocode(lat: float, lon: float) -> str:
    try:
        r = requests.get(OPEN_METEO_REVERSE_GEOCODE,
                         params={"latitude": lat, "longitude": lon, "language": "en"},
                         timeout=20)
        r.raise_for_status()
        js = r.json() or {}
        results = js.get("results") or []
        if results:
            item = results[0]
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
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,windspeed_10m,relative_humidity_2m",
        "forecast_days": 7,
        "timezone": "auto",
    }
    r = requests.get(OPEN_METEO_FORECAST, params=params, timeout=25)
    r.raise_for_status()
    js = r.json() or {}
    hourly = js.get("hourly") or {}
    df = pd.DataFrame(hourly)
    if "time" not in df.columns or df.empty:
        return pd.DataFrame()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).set_index("time").sort_index()
    if hours > 0:
        df = df.iloc[:hours]
    rename_map = {
        "temperature_2m": "Temperature (°C)",
        "precipitation": "Precipitation (mm)",
        "windspeed_10m": "Wind Speed (km/h)",
        "relative_humidity_2m": "Relative Humidity (%)",
    }
    cols_present = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=cols_present)
    return df

# ------------------------ UI ------------------------
st.title("🌦️ Open‑Meteo Interactive Weather Dashboard")
st.caption("Click on the map to choose a location. The app fetches hourly weather from Open‑Meteo (no API key required).")

with st.sidebar:
    st.header("Controls")
    st.write("1) Click a point on the map.\n\n2) Choose how many hours to display.")
    hours = st.slider("Hours to display", min_value=12, max_value=120, value=48, step=6)

st.subheader("1) Pick a region (click on the map)")
m = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=DEFAULT_ZOOM, control_scale=True, tiles="OpenStreetMap")
folium.Marker([DEFAULT_LAT, DEFAULT_LON], tooltip="Default: Seoul").add_to(m)
map_state = st_folium(m, height=520, returned_objects=[], key="map")

if isinstance(map_state, dict) and map_state.get("last_clicked"):
    lat, lon = map_state["last_clicked"]["lat"], map_state["last_clicked"]["lng"]
else:
    lat, lon = DEFAULT_LAT, DEFAULT_LON

st.info("Click anywhere on the map to fetch weather data for that location.")

st.subheader("2) Hourly Weather")
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

# Latest available (last row)
latest = df.iloc[-1]

# Summary cards (guard against missing columns)
c1, c2, c3, c4 = st.columns(4)
if "Temperature (°C)" in df:
    c1.metric("Temperature (latest)", f"{latest['Temperature (°C)']:.1f} °C")
else:
    c1.metric("Temperature (latest)", "N/A")

if "Wind Speed (km/h)" in df:
    c2.metric("Wind Speed (latest)", f"{latest['Wind Speed (km/h)']:.0f} km/h")
else:
    c2.metric("Wind Speed (latest)", "N/A")

if "Precipitation (mm)" in df:
    c3.metric("Precipitation (latest)", f"{latest['Precipitation (mm)']:.2f} mm")
else:
    c3.metric("Precipitation (latest)", "N/A")

if "Relative Humidity (%)" in df:
    c4.metric("RH (latest)", f"{latest['Relative Humidity (%)']:.0f} %")
else:
    c4.metric("RH (latest)", "N/A")

tab1, tab2, tab3 = st.tabs(["Temperature", "Precipitation", "Wind & Humidity"])

with tab1:
    if "Temperature (°C)" in df:
        st.line_chart(df[["Temperature (°C)"]])
    else:
        st.info("Temperature not available for this location/time.")

with tab2:
    if "Precipitation (mm)" in df:
        st.area_chart(df[["Precipitation (mm)"]])
    else:
        st.info("Precipitation not available for this location/time.")

with tab3:
    cols = [c for c in ["Wind Speed (km/h)", "Relative Humidity (%)"] if c in df]
    if cols:
        st.line_chart(df[cols])
    else:
        st.info("Wind/Humidity not available for this location/time.")

st.markdown("---")
st.caption("Data Source: Open‑Meteo.com (Forecast & Geocoding). Map tiles © OpenStreetMap contributors.")
