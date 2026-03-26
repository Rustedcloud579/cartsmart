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
    st.caption("Live Prices + Apple Notes Export")

    with st.sidebar:
        location = st.text_input("Location", value="83709")
        raw_input = st.text_area("List (One per line)", value="4 lbs ground buffalo\n6 lbs chicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        if st.button("Compare Prices", type="primary"):
            data = search_prices(items, location)
            if data:
                st.session_state["data"] = data

    if "data" in st.session_state:
        res = st.session_state["data"]
        items_data = res.get("items", [])
        
        st.subheader("💡 Shopping Strategy")
        st.info(res.get("overall_summary", "Compare totals below."))

        st.divider()
        
        # 1. Quantity Adjustments
        st.subheader("Step 1: Adjust Quantities")
        quantities = {}
        q_cols = st.columns(4) # Grid layout for quantities
        for idx, item in enumerate(items_data):
            with q_cols[idx % 4]:
                quantities[item['name']] = st.number_input(
                    f"{item['name']} ({item.get('unit', 'unit')})", 
                    min_value=0.0, value=1.0, step=0.5, key=f"q_{idx}"
                )

        # 2. Math Processing
        STORES = ["Amazon Fresh", "Costco", "Walmart", "Kroger", "Albertsons"]
        calculated_rows = []
        store_totals = {store: 0.0 for store in STORES}

        for item in items_data:
            name = item['name']
            qty = quantities[name]
            row = {"Item": name}
            for store in STORES:
                up = float(item['prices'].get(store, 0) or 0)
                total_p = up * qty
                row[store] = f"${total_p:.2f}"
                store_totals[store] += total_p
            calculated_rows.append(row)

        st.subheader("Step 2: Compare Totals")
        st.dataframe(pd.DataFrame(calculated_rows), use_container_width=True, hide_index=True)

        # 3. Final Totals Metrics
        valid_totals = {s: v for s, v in store_totals.items() if v > 0}
        winner = min(valid_totals, key=valid_totals.get) if valid_totals else None
        
        t_cols = st.columns(len(STORES))
        for i, store in enumerate(STORES):
            with t_cols[i]:
                st.metric(store, f"${store_totals[store]:.2f}", 
                          delta="WINNER" if store == winner else None)

        # 4. APPLE NOTES EXPORT SECTION
        st.divider()
        st.subheader("📝 Copy to Apple Notes")
        st.caption("Highlight and copy the text below into your shared note.")
        
        # Format the text for Apple Notes
        export_text = f"🛒 **Grocery Trip: {winner or 'Best Value'}**\n"
        export_text += f"📍 Location: {location}\n"
        export_text += "--------------------------\n"
        for item in items_data:
            name = item['name']
            qty = quantities[name]
            best_p = float(item['prices'].get(winner, 0) or 0) * qty
            export_text += f"☐ {name} ({qty} {item.get('unit', 'unit')}) - ${best_p:.2f}\n"
        
        export_text += "--------------------------\n"
        export_text += f"💰 Est. Total: ${store_totals.get(winner, 0.0):.2f}\n"
        export_text += f"💡 Strategy: {res.get('overall_summary', '')}"

        st.text_area("Notes Output", value=export_text, height=300)

if __name__ == "__main__":
    main()

