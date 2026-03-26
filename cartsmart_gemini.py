import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re
import time

# Page Configuration
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

# Custom Styling
st.markdown("""
<style>
    .stMetric { background-color: #16180f; padding: 15px; border-radius: 10px; border: 1px solid #2a2e1a; }
    .stDataFrame { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

def get_local_stores(location, radius):
    """Phase 1: Find major grocery stores and their coordinates within a radius."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    prompt = (
        f"Find the major grocery store chains (e.g., Walmart, Costco, Fred Meyer, Albertsons, WinCo) "
        f"with physical locations strictly within {radius} miles of ZIP code {location}. "
        "Return ONLY a JSON list of objects: "
        "[{'name': 'Store Name', 'latitude': 43.6, 'longitude': -116.2}]"
    )
    
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1
    )
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception as e:
        st.error(f"Discovery Error: {e}")
        return []

def search_prices(items, location, selected_stores):
    """Phase 2: Search for price-per-unit at specifically selected stores."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    store_str = ", ".join(selected_stores)
    item_list = "\n".join(items)
    
    prompt = (
        f"You are a grocery expert in {location}. Search ONLY these stores: {store_str}.\n\n"
        f"Items to find:\n{item_list}\n\n"
        "TASK:\n"
        "1. Find the current price-per-unit (lb, oz, or each) for each item.\n"
        "2. If exact brand is missing, use a store-brand equivalent.\n"
        "3. Return ONLY a JSON object:\n"
        "{"
        "  'items': [{'name': 'item name', 'unit': 'lb', 'prices': {'StoreName': 0.00}}],"
        "  'overall_summary': 'Short strategy for these specific stores...',"
        "  'recommended_store': 'StoreName'"
        "}"
    )

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1
    )

    with st.spinner(f"Comparing prices across {len(selected_stores)} stores..."):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            return json.loads(match.group()) if match else None
        except Exception as e:
            st.error(f"Price Search Error: {e}")
            return None

def main():
    st.title("🛒 CartSmart")
    st.caption("2026 Edition: Dynamic Scouting, Live Mapping, and Apple Notes Integration")

    # --- SIDEBAR: INPUTS & SCOUTING ---
    with st.sidebar:
        st.header("1. Location & Radius")
        location = st.text_input("ZIP Code", value="83709")
        radius = st.slider("Search Radius (Miles)", min_value=1, max_value=50, value=10)
        
        if st.button("Scout Local Stores", use_container_width=True):
            with st.spinner("Mapping local area..."):
                stores = get_local_stores(location, radius)
                st.session_state["discovered_stores"] = stores
        
        st.divider()
        
        # Store Selection
        store_data = st.session_state.get("discovered_stores", [])
        if store_data:
            available_names = [s['name'] for s in store_data]
            selected_stores = st.multiselect("Select stores to compare:", available_names, default=available_names[:4])
        else:
            st.info("Scout stores first to see options.")
            selected_stores = []

        st.divider()
        st.header("2. Your List")
        raw_input = st.text_area("One item per line", value="4 lbs ground buffalo\n6 lbs chicken breast\nPaper towels", height=150)
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        
        search_btn = st.button("Compare Prices", type="primary", use_container_width=True)

    # --- MAIN UI: MAP & RESULTS ---
    
    # Show Map if stores are discovered
    if store_data and selected_stores:
        st.subheader(f"📍 Stores within {radius} miles")
        map_df = pd.DataFrame(store_data)
        # Rename columns for st.map compatibility
        map_df = map_df.rename(columns={'latitude': 'lat', 'longitude': 'lon'})
        # Filter map to only show selected stores
        map_filtered = map_df[map_df['name'].isin(selected_stores)]
        st.map(map_filtered)

    if search_btn:
        if not selected_stores:
            st.error("Please scout and select at least one store first.")
        else:
            data = search_prices(items, location, selected_stores)
            if data:
                st.session_state["price_data"] = data
                st.session_state["last_active_stores"] = selected_stores

    # Process and Display Results
    if "price_data" in st.session_state:
        res = st.session_state["price_data"]
        items_res = res.get("items", [])
        active_stores = st.session_state.get("last_active_stores", [])
        
        st.divider()
        st.subheader("💡 Shopping Strategy")
        st.info(res.get("overall_summary", "Calculating best route..."))

        # Step 1: Quantities
        st.subheader("Step 1: Set Your Quantities")
        quantities = {}
        q_cols = st.columns(4)
        for idx, item in enumerate(items_res):
            with q_cols[idx % 4]:
                quantities[item['name']] = st.number_input(
                    f"{item['name']} ({item.get('unit', 'unit')})", 
                    min_value=0.0, value=1.0, step=0.5, key=f"qty_{idx}"
                )

        # Step 2: Comparison Math
        calculated_rows = []
        store_totals = {store: 0.0 for store in active_stores}

        for item in items_res:
            name = item['name']
            qty = quantities[name]
            row = {"Item": name, "Unit": item.get('unit', 'ea')}
            for store in active_stores:
                # Use 0 if price not found
                unit_p = float(item['prices'].get(store, 0) or 0)
                total_p = unit_p * qty
                row[store] = f"${total_p:.2f}"
                store_totals[store] += total_p
            calculated_rows.append(row)

        st.subheader("Step 2: Price Comparison Table")
        st.dataframe(pd.DataFrame(calculated_rows), use_container_width=True, hide_index=True)

        # Step 3: Basket Totals
        st.subheader("Final Basket Totals")
        valid_totals = {s: v for s, v in store_totals.items() if v > 0}
        winner = min(valid_totals, key=valid_totals.get) if valid_totals else None
        
        t_cols = st.columns(len(active_stores))
        for i, store in enumerate(active_stores):
            with t_cols[i]:
                st.metric(store, f"${store_totals[store]:.2f}", 
                          delta="BEST VALUE" if store == winner else None)

        # Step 4: Apple Notes Export
        st.divider()
        st.subheader("📝 Copy to Apple Notes")
        st.caption("Perfectly formatted for your shared note.")
        
        export_text = f"🛒 **Grocery Trip: {winner or 'Comparison'}**\n"
        export_text += f"📍 Location: {location} ({radius} mi radius)\n"
        export_text += "--------------------------\n"
        for item in items_res:
            qty = quantities[item['name']]
            # Show price for the winning store in the note
            p_at_winner = float(item['prices'].get(winner, 0) or 0) * qty
            export_text += f"☐ {item['name']} ({qty} {item.get('unit', 'unit')}) - ${p_at_winner:.2f}\n"
        
        export_text += "--------------------------\n"
        export_text += f"💰 Grand Total: ${store_totals.get(winner, 0.0):.2f}\n"
        export_text += f"💡 Note: {res.get('overall_summary', '')}"

        st.text_area("Notes Output (Select All & Copy)", value=export_text, height=250)

if __name__ == "__main__":
    main()

