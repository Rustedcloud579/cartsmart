import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import json
import re
import time

# Page Setup
st.set_page_config(page_title="CartSmart", page_icon="🛒", layout="wide")

def search_prices(items, location):
    # Initialize the 2026 Client
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    item_list = "\n".join(items)
    
    # IMPROVED PROMPT: Focused on price-per-pound and equivalent items
    prompt = (
        f"You are a grocery price expert in {location}. Search Amazon Fresh, Costco, Walmart, Kroger, and Albertsons.\n\n"
        f"Items to find:\n{item_list}\n\n"
        "CRITICAL RULES:\n"
        "1. If a specific brand is unavailable, use the closest store-brand equivalent.\n"
        "2. If the item is not sold in the exact weight requested, CALCULATE the price-per-pound or price-per-unit.\n"
        "3. Ensure all 'prices' in the JSON are numbers (float). Use 0.0 only if the store absolutely does not carry a similar category.\n"
        "4. Return ONLY a JSON object: {'items':[{'name':'item name','unit':'lb','prices':{'Store Name':0.00},'notes':'found 16oz at $X'}]}"
    )

    # Grounding Configuration
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.1 # Low temperature for more factual, less "creative" numbers
    )

    with st.spinner("Searching and calculating unit prices..."):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            
            # Extract and Clean JSON
            text = response.text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return None
        except Exception as e:
            st.error(f"Search Error: {e}")
            return None

def main():
    st.title("🛒 CartSmart")
    st.caption("Price Normalization Active: Calculating Price-per-Pound & Equivalents")

    with st.sidebar:
        location = st.text_input("Location", value="83709")
        st.info("Tip: Use general names (e.g., 'Ground Buffalo') for better results.")
        raw_input = st.text_area("List", value="4 lbs ground buffalo meat\n6 lbs chicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        search_btn = st.button("Compare Prices", type="primary")

    if search_btn:
        data = search_prices(items, location)
        if data:
            st.session_state["data"] = data

    if "data" in st.session_state:
        items_data = st.session_state["data"].get("items", [])
        
        # Build Table
        rows = []
        for i in items_data:
            row = {"Item": i["name"], "Unit": i.get("unit", "ea")}
            row.update(i["prices"])
            rows.append(row)
            
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Comparison logic
        st.success("Prices normalized to best available unit sizes.")

if __name__ == "__main__":
    main()

