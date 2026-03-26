import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re

# Page Setup
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

def get_local_stores(location, radius):
    """Phase 1: Find stores and their coordinates."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    prompt = (
        f"Find major grocery stores within {radius} miles of ZIP {location}. "
        "Return ONLY a JSON list of objects: "
        "[{'name': 'Store Name', 'lat': 43.6, 'lon': -116.2}]"
    )
    
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        return json.loads(match.group()) if match else []
    except:
        return []

def main():
    st.title("🛒 CartSmart")
    st.caption("Precision Scouting with Live Map Integration")

    with st.sidebar:
        location = st.text_input("Location (ZIP)", value="83709")
        radius = st.slider("Search Radius (Miles)", min_value=1, max_value=50, value=10)
        
        if st.button("Scout Local Stores"):
            with st.spinner("Mapping area..."):
                st.session_state["discovered_stores_data"] = get_local_stores(location, radius)
        
        # Extract names for the selector
        store_data = st.session_state.get("discovered_stores_data", [])
        available_names = [s['name'] for s in store_data] if store_data else ["Walmart", "Costco", "Kroger", "Albertsons"]
        selected_stores = st.multiselect("Select stores:", available_names, default=available_names[:4])
        
        st.divider()
        raw_input = st.text_area("List", value="Ground buffalo\nChicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        search_btn = st.button("Compare Prices", type="primary")

    # NEW MAP SECTION
    if store_data:
        st.subheader(f"📍 Stores within {radius} miles")
        map_df = pd.DataFrame(store_data)
        # Filter map to only show selected stores
        map_filtered = map_df[map_df['name'].isin(selected_stores)]
        if not map_filtered.empty:
            st.map(map_filtered)
        else:
            st.info("Select stores in the sidebar to see them on the map.")

    # (Price search and results logic continues here...)

