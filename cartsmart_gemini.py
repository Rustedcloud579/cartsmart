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
    # Initialize the new 2026 Client
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    item_list = "\n".join(items)
    prompt = (
        f"Find current grocery prices in {location} for: {item_list}. "
        "Search Amazon Fresh, Costco, Walmart, Kroger, and Albertsons. "
        "Return ONLY a JSON object: {'items':[{'name':'item','prices':{'Store':0.00}}]}"
    )

    # New 2026 Grounding Syntax
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    with st.spinner("Searching live stores..."):
        try:
            # Using the stable 2026 Flash model
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            
            # Clean up JSON formatting
            text = response.text
            cleaned = re.sub(r"```json|```", "", text).strip()
            return json.loads(cleaned)
        except Exception as e:
            st.error(f"Search Error: {e}")
            return None

def main():
    st.title("🛒 CartSmart")
    st.caption("Updated for Google GenAI SDK (March 2026)")

    with st.sidebar:
        location = st.text_input("Location", value="83709")
        raw_input = st.text_area("List", value="Ground buffalo\nChicken breast\nPaper towels")
        items = [i.strip() for i in raw_input.splitlines() if i.strip()]
        search_btn = st.button("Compare Prices", type="primary")

    if search_btn:
        data = search_prices(items, location)
        if data:
            st.session_state["data"] = data

    # Display results
    if "data" in st.session_state:
        items_data = st.session_state["data"].get("items", [])
        df = pd.DataFrame([{"Item": i["name"], **i["prices"]} for i in items_data])
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()

