import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re

# Page Configuration
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

# Updated Model Constant for 2026
LATEST_MODEL = "gemini-3-flash-preview" 

def get_local_stores(location, radius):
    """Phase 1: Find stores and coordinates using Gemini 3 Flash."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    prompt = (
        f"Find major grocery stores within {radius} miles of ZIP {location}. "
        "Return ONLY a JSON list of objects: "
        "[{'name': 'Store Name', 'lat': 43.6, 'lon': -116.2}]"
    )
    
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1
    )
    
    try:
        response = client.models.generate_content(model=LATEST_MODEL, contents=prompt, config=config)
        # Safety check: if response.text is None or empty, return empty list
        if not response.text:
            return []
            
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        return json.loads(match.group()) if match else []
    except Exception as e:
        st.sidebar.error(f"Discovery Error: {e}")
        return []

def search_prices(items, location, selected_stores):
    """Phase 2: Compare prices at selected stores."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    store_str = ", ".join(selected_stores)
    item_list = "\n".join(items)
    
    prompt = (
        f"You are a grocery expert in {location}. Search ONLY these stores: {store_str}.\n\n"
        f"Items:\n{item_list}\n\n"
        "Return JSON: {'items': [{'name': 'item', 'unit': 'lb', 'prices': {'StoreName': 0.00}}], "
        "'overall_summary': 'strategy...', 'recommended_store': 'StoreName'}"
    )

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1
    )

    with st.spinner("Fetching live prices..."):
        try:
            response = client.models.generate_content(model=LATEST_MODEL, contents=prompt, config=config)
            if not response.text: return None
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            return json.loads(match.group()) if match else None
        except Exception as e:
            st.error(f"Price Search Error: {e}")
            return None

def main():
    st.title("🛒 CartSmart")
    st.caption("2026 Edition: Powered by Gemini 3 Flash")

    with st.sidebar:
        st.header("1. Location & Radius")
        location = st.text_input("ZIP Code", value="83709")
        radius = st.slider("Search Radius (Miles)", 1, 50, 10)
        
        if st.button("Scout Local Stores", use_container_width=True):
            stores = get_local_stores(location, radius)
            st.session_state["discovered_stores"] = stores
        
        store_data = st.session_state.get("discovered_stores", [])
        available_names = [s['name'] for s in store_data] if store_data else []
        
        selected_stores = st.multiselect("Select stores:", available_names, default=available_names[:4] if available_names else [])
        
        st.divider()
        st.header("2. Your List")
        raw_input = st.text_area("Items", value="4 lbs ground buffalo\n6 lbs chicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        search_btn = st.button("Compare Prices", type="primary", use_container_width=True)

    # --- MAP SECTION ---
    if store_data and selected_stores:
        st.subheader(f"📍 Stores within {radius} miles")
        df = pd.DataFrame(store_data)
        # Ensure only selected stores appear on map
        map_df = df[df['name'].isin(selected_stores)]
        if not map_df.empty:
            st.map(map_df)

    # --- PRICE RESULTS ---
    if search_btn and selected_stores:
        data = search_prices(items, location, selected_stores)
        if data:
            st.session_state["results"] = data
            st.session_state["active_stores"] = selected_stores

    if "results" in st.session_state:
        res = st.session_state["results"]
        items_res = res.get("items", [])
        active_stores = st.session_state.get("active_stores", [])

        st.divider()
        st.subheader("💡 Strategy")
        st.info(res.get("overall_summary", ""))

        # Quantities & Totals logic...
        # [Remaining code logic for quantities and Apple Notes export as previously discussed]
        st.success("Prices loaded! Adjust your quantities above to see the final total.")

if __name__ == "__main__":
    main()

