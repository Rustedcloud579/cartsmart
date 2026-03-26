import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import csv
import time
from io import StringIO

st.set_page_config(
    page_title="CartSmart - Grocery Price Comparison",
    page_icon=":shopping_trolley:",
    layout="wide",
)

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
.store-card.winner { border-color: #b8e04a; }
.winner-badge {
  background: #b8e04a;
  color: #0e0f0c;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 3px;
}
.savings-box {
  background: #0a1a00;
  border: 1px solid rgba(184,224,74,0.3);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
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

PLACEHOLDER = """4 lbs ground buffalo meat
6 lbs chicken breast organic
Brawny paper towels
Charmin toilet paper"""

def search_prices(items, location):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # Updated to the stable 2026 production model name
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        tools=[{"google_search_retrieval": {}}],
    )
    
    item_list = "\n".join(str(i+1) + ". " + item for i, item in enumerate(items))
    prompt = (
        "You are a grocery price research assistant.\n"
        "Use Google Search to find CURRENT real retail prices for each item below "
        "at each of these 5 stores: Amazon Fresh, Costco, Walmart, Kroger, Albertsons.\n\n"
        "Location: " + location + "\n\n"
        "Grocery list:\n" + item_list + "\n\n"
        "Respond ONLY with a valid JSON object. No markdown, no explanation.\n"
        '{"items":[{"name":"item","unit":"per lb","prices":{"Amazon Fresh":4.99,"Costco":9.99,"Walmart":3.78,"Kroger":4.29,"Albertsons":4.49},"notes":""}],"location":"city, state","searched_at":"month year"}'
    )

    with st.spinner("Searching live prices... this may take 20-30 seconds."):
        try:
            response = model.generate_content(prompt)
            # Basic retry if hitting immediate rate limit
            if not response.text:
                time.sleep(2)
                response = model.generate_content(prompt)
                
            return parse_price_json(response.text)
        except Exception as e:
            if "429" in str(e):
                raise ValueError("Rate limit hit. Please wait 60 seconds before clicking search again.")
            raise e

def parse_price_json(text):
    cleaned = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except:
        # Fallback to extract JSON if Gemini adds conversational text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
    raise ValueError("Could not parse the data returned from the search.")

def compute_store_totals(items):
    totals = {}
    for store in STORES:
        total, count = 0.0, 0
        for item in items:
            p = item["prices"].get(store)
            if p is not None:
                total += float(p)
                count += 1
        totals[store] = {"total": total, "count": count}
    return totals

def compute_optimal_list(items):
    optimal = {}
    for item in items:
        best_price, best_store = float("inf"), None
        for store in STORES:
            p = item["prices"].get(store)
            if p is not None and float(p) < best_price:
                best_price = float(p)
                best_store = store
        if best_store:
            optimal.setdefault(best_store, []).append({
                "name": item["name"],
                "price": best_price,
                "unit": item.get("unit", ""),
            })
    return optimal

def build_text_export(data, store_totals, optimal):
    ranked = sorted([s for s in STORES if store_totals[s]["count"] > 0], key=lambda s: store_totals[s]["total"])
    lines = ["CARTSMART EXPORT", "=" * 30]
    for s in ranked:
        t = store_totals[s]
        lines.append(f"{s}: ${round(t['total'], 2)} ({t['count']} items)")
    return "\n".join(lines)

def build_csv_export(data):
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Item"] + STORES)
    for item in data["items"]:
        writer.writerow([item["name"]] + [item["prices"].get(s, "") for s in STORES])
    return buf.getvalue()

def main():
    st.title("🛒 CartSmart")
    st.markdown("Comparing real-time prices across Amazon, Costco, Walmart, Kroger, and Albertsons.")
    
    with st.sidebar:
        st.header("Location")
        location = st.text_input("ZIP Code", value="83709")
        st.subheader("Your List")
        raw_input = st.text_area("One item per line", value=PLACEHOLDER, height=200)
        items_parsed = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
        search_clicked = st.button("Compare Prices", type="primary")

    if search_clicked:
        try:
            data = search_prices(items_parsed, location)
            st.session_state["price_data"] = data
        except Exception as e:
            st.error(f"Error: {str(e)}")

    data = st.session_state.get("price_data")
    if data:
        items = data["items"]
        totals = compute_store_totals(items)
        optimal = compute_optimal_list(items)
        ranked = sorted([s for s in STORES if totals[s]["count"] > 0], key=lambda s: totals[s]["total"])
        
        # Results Display
        st.subheader("Store Totals")
        cols = st.columns(len(STORES))
        for i, store in enumerate(STORES):
            with cols[i]:
                color = STORE_COLORS[store]
                amt = totals[store]["total"]
                st.markdown(f"<div class='store-card'><h4 style='color:{color}'>{store}</h4><h2>${round(amt, 2)}</h2></div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("Cheapest Split List")
        for store, s_items in optimal.items():
            with st.expander(f"Buy at {store}"):
                for si in s_items:
                    st.write(f"- {si['name']}: **${si['price']}**")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download CSV", build_csv_export(data), "prices.csv", "text/csv")
        with col2:
            st.download_button("Download TXT", build_text_export(data, totals, optimal), "prices.txt", "text/plain")

if __name__ == "__main__":
    main()

