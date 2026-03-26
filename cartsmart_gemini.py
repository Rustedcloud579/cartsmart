import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re

# Page Setup
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

def search_prices(items, location):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    item_list = "\n".join(items)
    
    prompt = (
        f"You are a grocery expert in {location}. Search Amazon Fresh, Costco, Walmart, Kroger, and Albertsons.\n\n"
        f"Items:\n{item_list}\n\n"
        "TASK:\n"
        "1. Find the best price-per-unit (lb, oz, or each) for these items.\n"
        "2. Return ONLY JSON:\n"
        "{"
        "  'items': [{'name': 'item name', 'unit': 'lb', 'prices': {'Store': 0.00}}],"
        "  'overall_summary': 'Short strategy summary...',"
        "  'recommended_store': 'Store Name'"
        "}"
    )

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1
    )

    with st.spinner("Fetching unit prices..."):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            return json.loads(match.group()) if match else None
        except Exception as e:
            st.error(f"Search Error: {e}")
            return None

def main():
    st.title("🛒 CartSmart")
    st.caption("Live Prices + Manual Quantity Calculator")

    with st.sidebar:
        location = st.text_input("Location", value="83709")
        raw_input = st.text_area("List (One per line)", value="Ground buffalo\nChicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        if st.button("Compare Prices", type="primary"):
            data = search_prices(items, location)
            if data:
                st.session_state["data"] = data

    if "data" in st.session_state:
        res = st.session_state["data"]
        items_data = res.get("items", [])
        
        st.subheader("💡 Strategy")
        st.info(res.get("overall_summary", "Compare totals below to see the best value."))

        st.divider()
        st.subheader("Adjust Quantities & Calculate Totals")
        
        # Create a dictionary to hold quantities
        quantities = {}
        
        # UI for adjusting quantities
        col_list = st.columns(len(items_data))
        for idx, item in enumerate(items_data):
            with col_list[idx % len(col_list)]:
                quantities[item['name']] = st.number_input(
                    f"Qty: {item['name']} ({item.get('unit', 'unit')})", 
                    min_value=0.0, 
                    value=1.0, 
                    step=0.5,
                    key=f"qty_{idx}"
                )

        # Calculate Table and Totals
        STORES = ["Amazon Fresh", "Costco", "Walmart", "Kroger", "Albertsons"]
        calculated_rows = []
        store_totals = {store: 0.0 for store in STORES}

        for item in items_data:
            name = item['name']
            qty = quantities[name]
            row = {"Item": name, "Unit Price": item.get('unit', 'ea')}
            
            for store in STORES:
                unit_p = item['prices'].get(store, 0.0)
                # Ensure it's a number
                unit_p = float(unit_p) if unit_p else 0.0
                total_p = unit_p * qty
                row[store] = f"${total_p:.2f}"
                store_totals[store] += total_p
            
            calculated_rows.append(row)

        # Display Comparison Table
        st.dataframe(pd.DataFrame(calculated_rows), use_container_width=True, hide_index=True)

        # Final Totals Section
        st.divider()
        st.subheader("Final Basket Totals")
        total_cols = st.columns(len(STORES))
        
        # Identify the winner for a visual highlight
        valid_totals = {s: v for s, v in store_totals.items() if v > 0}
        winner = min(valid_totals, key=valid_totals.get) if valid_totals else None

        for i, store in enumerate(STORES):
            with total_cols[i]:
                is_winner = (store == winner)
                label = f"🏆 {store}" if is_winner else store
                st.metric(label, f"${store_totals[store]:.2f}", 
                          delta="Best Value" if is_winner else None)

if __name__ == "__main__":
    main()

