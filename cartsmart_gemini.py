import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re

# Page Setup
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

# Updated 2026 Model
LATEST_MODEL = "gemini-3-flash-preview" 

def get_local_stores(location, radius):
    """Phase 1: Find stores and coordinates."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    prompt = (
        f"Find major grocery stores within {radius} miles of ZIP {location}. "
        "Return ONLY a JSON list of objects: "
        "[{'name': 'Store Name', 'lat': 43.6, 'lon': -116.2}]"
    )
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    try:
        response = client.models.generate_content(model=LATEST_MODEL, contents=prompt, config=config)
        if not response.text: return []
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
        "Return ONLY JSON: {'items': [{'name': 'item', 'unit': 'lb', 'prices': {'StoreName': 0.00}}], "
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
    st.caption("2026 Edition: Live Mapping & Price Intelligence")

    with st.sidebar:
        st.header("1. Location & Radius")
        location = st.text_input("ZIP Code", value="83709")
        radius = st.slider("Search Radius (Miles)", 1, 50, 10)
        
        if st.button("Scout Local Stores", use_container_width=True):
            st.session_state["discovered_stores"] = get_local_stores(location, radius)
        
        store_data = st.session_state.get("discovered_stores", [])
        available_names = [s['name'] for s in store_data]
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
        map_df = df[df['name'].isin(selected_stores)]
        if not map_df.empty:
            st.map(map_df)

    # --- SEARCH EXECUTION ---
    if search_btn:
        if not selected_stores:
            st.error("Select stores first!")
        else:
            data = search_prices(items, location, selected_stores)
            if data:
                st.session_state["results"] = data
                st.session_state["active_stores"] = selected_stores

    # --- RESULTS DASHBOARD ---
    if "results" in st.session_state:
        res = st.session_state["results"]
        items_res = res.get("items", [])
        active_stores = st.session_state.get("active_stores", [])

        st.divider()
        st.subheader("💡 Shopping Strategy")
        st.info(res.get("overall_summary", "Calculating best value..."))

        # Step 1: Quantities
        st.subheader("Step 1: Set Quantities")
        quantities = {}
        q_cols = st.columns(min(len(items_res), 4))
        for idx, item in enumerate(items_res):
            with q_cols[idx % 4]:
                quantities[item['name']] = st.number_input(
                    f"{item['name']} ({item.get('unit', 'unit')})", 
                    min_value=0.0, value=1.0, step=0.5, key=f"q_{idx}"
                )

        # Step 2: Comparison Table
        st.subheader("Step 2: Compare Prices")
        calculated_rows = []
        store_totals = {store: 0.0 for store in active_stores}

        for item in items_res:
            row = {"Item": item['name']}
            qty = quantities[item['name']]
            for store in active_stores:
                price = float(item['prices'].get(store, 0) or 0)
                total = price * qty
                row[store] = f"${total:.2f}"
                store_totals[store] += total
            calculated_rows.append(row)

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
        export_text = f"🛒 **Grocery Trip: {winner}**\n📍 ZIP: {location}\n" + "-"*20 + "\n"
        for item in items_res:
            qty = quantities[item['name']]
            best_p = float(item['prices'].get(winner, 0) or 0) * qty
            export_text += f"☐ {item['name']} ({qty} {item.get('unit', 'unit')}) - ${best_p:.2f}\n"
        export_text += "-"*20 + f"\n💰 Total: ${store_totals.get(winner, 0.0):.2f}"
        st.text_area("Notes Output", value=export_text, height=200)

if __name__ == "__main__":
    main()

