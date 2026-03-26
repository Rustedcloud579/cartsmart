import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import csv
import time
from io import StringIO

# Page Configuration
st.set_page_config(
    page_title="CartSmart - Grocery Price Comparison",
    page_icon="🛒",
    layout="wide",
)

# Custom CSS for the 2026 "Dark Mode" aesthetic
st.markdown("""
<style>
.store-card {
  background: #16180f;
  border: 1px solid #2a2e1a;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  margin-bottom: 8px;
}
.store-card h4 { margin: 0; padding-bottom: 8px; }
.store-card h2 { margin: 0; color: #ffffff; }
</style>
""", unsafe_allow_html=True)

STORES = ["Amazon Fresh", "Costco", "Walmart", "Kroger", "Albertsons"]
STORE_COLORS = {
    "Amazon Fresh": "#ff9900",
    "Costco": "#e31837",
    "Walmart": "#0071ce",
    "Kroger": "#5b9bd5",
    "Albertsons": "#00833e",
}

def search_prices(items, location):
    """Uses Gemini 2.5 Flash with Google Search to find current prices."""
    # Ensure the API key is set from Streamlit Secrets
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("API Key missing! Add GEMINI_API_KEY to your Streamlit Secrets.")
        st.stop()
        
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # MARCH 2026 UPDATE: Using gemini-2.5-flash and the updated tool name 'google_search'
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        tools=[{"google_search": {}}], 
    )
    
    item_list = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    prompt = (
        f"You are a professional grocery price researcher in {location}.\n"
        "Find the CURRENT real retail prices for these items at: Amazon Fresh, Costco, Walmart, Kroger, Albertsons.\n\n"
        f"List:\n{item_list}\n\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"items":[{"name":"item","unit":"pkg","prices":{"Walmart":1.00...},"notes":""}]}'
    )

    with st.spinner("Searching live web data via Gemini 2.5..."):
        try:
            # Small 1-second pause to prevent the 'Quota Exceeded' 429 error
            time.sleep(1) 
            response = model.generate_content(prompt)
            
            # Clean and parse the JSON response
            raw_text = response.text
            cleaned_json = re.sub(r"```json|```", "", raw_text).strip()
            return json.loads(cleaned_json)
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg:
                st.error("Too many requests! Wait 60 seconds and try again.")
            elif "404" in err_msg:
                st.error("Model Error: Please ensure your requirements.txt has 'google-generativeai>=0.8.0'")
            else:
                st.error(f"Search Failed: {err_msg}")
            st.stop()

def main():
    st.title("🛒 CartSmart")
    st.caption("Real-time price comparison powered by Gemini 2.5 Flash (March 2026 Edition)")
    
    # Sidebar for Inputs
    with st.sidebar:
        st.header("Shopping Details")
        location = st.text_input("ZIP Code or City", value="83709")
        raw_input = st.text_area("List (One item per line)", 
                                value="4 lbs ground buffalo meat\n6 lbs chicken breast organic\nBrawny paper towels", 
                                height=200)
        items_parsed = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
        
        search_clicked = st.button("Compare Prices", type="primary")

    # If user clicks the button, run the search
    if search_clicked:
        if not items_parsed:
            st.warning("Please enter at least one item.")
        else:
            data = search_prices(items_parsed, location)
            st.session_state["price_data"] = data

    # Display Results
    data = st.session_state.get("price_data")
    if data:
        items = data.get("items", [])
        
        # Calculate Totals
        st.subheader("Store Totals")
        cols = st.columns(len(STORES))
        store_totals = {}
        
        for i, store in enumerate(STORES):
            total = sum(item["prices"].get(store, 0) for item in items if isinstance(item["prices"].get(store), (int, float)))
            store_totals[store] = total
            with cols[i]:
                color = STORE_COLORS.get(store, "#ffffff")
                st.markdown(f"""
                    <div class='store-card'>
                        <h4 style='color:{color}'>{store}</h4>
                        <h2>${total:,.2f}</h2>
                    </div>
                """, unsafe_allow_html=True)

        # Detailed Table
        st.divider()
        st.subheader("Price Breakdown")
        df_data = []
        for item in items:
            row = {"Item": item["name"]}
            for store in STORES:
                row[store] = item["prices"].get(store, "N/A")
            df_data.append(row)
        
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)

if __name__ == "__main__":
    main()

