import streamlit as st
import google.generativeai as genai
import json
import re
import csv
from io import StringIO

st.set_page_config(
page_title=“CartSmart - Grocery Price Comparison”,
page_icon=”:shopping_trolley:”,
layout=“wide”,
)

st.markdown(”””

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

“””, unsafe_allow_html=True)

STORES = [“Amazon Fresh”, “Costco”, “Walmart”, “Kroger”, “Albertsons”]

STORE_COLORS = {
“Amazon Fresh”: “#ff9900”,
“Costco”: “#e31837”,
“Walmart”: “#0071ce”,
“Kroger”: “#5b9bd5”,
“Albertsons”: “#00833e”,
}

PLACEHOLDER = “”“4 lbs ground buffalo meat
6 lbs chicken breast organic
Brawny paper towels
Charmin toilet paper
Fairlife whole milk
Almond milk
Bacon
Bananas
White rice
Green salsa
Cottage cheese single serve
Hummus single serve”””

def search_prices(items, location):
genai.configure(api_key=st.secrets[“GEMINI_API_KEY”])
model = genai.GenerativeModel(
model_name=“gemini-2.0-flash”,
tools=“google_search_retrieval”,
)
item_list = “\n”.join(str(i+1) + “. “ + item for i, item in enumerate(items))
prompt = (
“You are a grocery price research assistant.\n”
“Use Google Search to find CURRENT real retail prices for each item below “
“at each of these 5 stores: Amazon Fresh, Costco, Walmart, Kroger, Albertsons.\n\n”
“Location: “ + location + “\n\n”
“Grocery list:\n” + item_list + “\n\n”
“Respond ONLY with a valid JSON object. No markdown, no explanation. “
“Start with { and end with }.\n\n”
“{"items":[{"name":"item","unit":"per lb","prices":{"Amazon Fresh":4.99,"Costco":9.99,"Walmart":3.78,"Kroger":4.29,"Albertsons":4.49},"notes":""}],"location":"city, state","searched_at":"month year"}\n\n”
“Rules: prices must be numbers, use null if store does not carry item.”
)
with st.spinner(“Searching live prices via Google across 5 stores…”):
response = model.generate_content(prompt)
text = “”
if hasattr(response, “text”):
text = response.text
if not text:
try:
text = response.candidates[0].content.parts[0].text
except Exception:
pass
if not text:
raise ValueError(“Gemini returned empty response. Please try again.”)
return parse_price_json(text)

def parse_price_json(text):
cleaned = re.sub(r”`json\s*", "", text, flags=re.IGNORECASE) cleaned = re.sub(r"`\s*”, “”, cleaned).strip()
try:
data = json.loads(cleaned)
if “items” in data:
return data
except Exception:
pass
depth, start, end = 0, -1, -1
for i, ch in enumerate(cleaned):
if ch == “{”:
if depth == 0:
start = i
depth += 1
elif ch == “}”:
depth -= 1
if depth == 0 and start != -1:
end = i
break
if start != -1 and end != -1:
try:
data = json.loads(cleaned[start:end + 1])
if “items” in data:
return data
except Exception:
pass
raise ValueError(“Could not parse price data. Response: “ + text[:300])

def compute_store_totals(items):
totals = {}
for store in STORES:
total, count = 0.0, 0
for item in items:
p = item[“prices”].get(store)
if p is not None:
total += float(p)
count += 1
totals[store] = {“total”: total, “count”: count}
return totals

def compute_optimal_list(items):
optimal = {}
for item in items:
best_price, best_store = float(“inf”), None
for store in STORES:
p = item[“prices”].get(store)
if p is not None and float(p) < best_price:
best_price = float(p)
best_store = store
if best_store:
optimal.setdefault(best_store, []).append({
“name”: item[“name”],
“price”: best_price,
“unit”: item.get(“unit”, “”),
})
return optimal

def build_text_export(data, store_totals, optimal):
ranked = sorted(
[s for s in STORES if store_totals[s][“count”] > 0],
key=lambda s: store_totals[s][“total”],
)
opt_total = sum(i[“price”] for si in optimal.values() for i in si)
max_total = store_totals[ranked[-1]][“total”] if ranked else 0
lines = [
“CARTSMART GROCERY PRICE COMPARISON”,
“Location: “ + data.get(“location”, “”),
“Searched: “ + data.get(“searched_at”, “”),
“=” * 60, “”,
“STORE TOTALS”, “-” * 40,
]
for s in ranked:
t = store_totals[s]
marker = “ <- BEST” if s == ranked[0] else “”
lines.append(”  “ + s.ljust(22) + “$” + str(round(t[“total”], 2)).rjust(7) + “  (” + str(t[“count”]) + “/” + str(len(data[“items”])) + “ items)” + marker)
lines += [””, “ITEM BREAKDOWN”, “-” * 60]
for item in data[“items”]:
valid = [float(item[“prices”].get(s)) for s in STORES if item[“prices”].get(s) is not None]
min_p = min(valid) if valid else None
best_s = next((s for s in STORES if item[“prices”].get(s) is not None and float(item[“prices”].get(s)) == min_p), “”) if min_p else “”
row = item[“name”][:30].ljust(32)
for s in STORES:
p = item[“prices”].get(s)
row += (”$” + str(round(float(p), 2)) if p is not None else “-”).ljust(12)
row += best_s.replace(” Fresh”, “”)
lines.append(row)
lines += [””, “OPTIMIZED SHOPPING LISTS”, “-” * 40]
for store, si in optimal.items():
subtotal = sum(i[“price”] for i in si)
lines += [””, “  “ + store, “  “ + “-” * 30]
for i in si:
lines.append(”  “ + i[“name”].ljust(35) + “$” + str(round(i[“price”], 2)))
lines.append(”  SUBTOTAL”.ljust(37) + “$” + str(round(subtotal, 2)))
lines += [””, “=” * 60,
“OPTIMAL TOTAL: $” + str(round(opt_total, 2)),
“PRICIEST STORE: $” + str(round(max_total, 2)) + “ (” + (ranked[-1] if ranked else “”) + “)”,
“YOU SAVE: $” + str(round(max_total - opt_total, 2)),
]
return “\n”.join(lines)

def build_csv_export(data):
buf = StringIO()
writer = csv.writer(buf)
writer.writerow([“Item”, “Unit”] + STORES + [“Best Store”, “Notes”])
for item in data[“items”]:
valid = [float(item[“prices”].get(s)) for s in STORES if item[“prices”].get(s) is not None]
min_p = min(valid) if valid else None
best_s = next((s for s in STORES if item[“prices”].get(s) is not None and float(item[“prices”].get(s)) == min_p), “”) if min_p else “”
writer.writerow([item[“name”], item.get(“unit”, “”)] + [item[“prices”].get(s, “”) for s in STORES] + [best_s, item.get(“notes”, “”)])
return buf.getvalue()

def main():
st.title(“CartSmart”)
st.markdown(”**Grocery Price Intelligence - 5-Store Comparison - Powered by Google Gemini (Free)**”)
st.markdown(”—”)
with st.sidebar:
st.header(“Settings”)
location = st.text_input(“ZIP Code or City”, value=“83709”)
st.markdown(”**Stores compared:**”)
for store, color in STORE_COLORS.items():
st.markdown(”<span style='color:" + color + "'>*</span> “ + store, unsafe_allow_html=True)
st.markdown(”—”)
st.caption(“Free - 1,500 searches/day via Gemini 2.0 Flash”)
st.subheader(“Your Grocery List”)
st.caption(“One item per line. Include quantities like ‘4 lbs ground buffalo meat’.”)
raw_input = st.text_area(“Grocery list”, value=PLACEHOLDER, height=260, label_visibility=“collapsed”)
items_parsed = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]
if items_parsed:
st.caption(str(len(items_parsed)) + “ items ready - Location: “ + location)
search_clicked = st.button(“Compare Prices”, type=“primary”)
if search_clicked:
if not items_parsed:
st.warning(“Please enter at least one grocery item.”)
st.stop()
try:
data = search_prices(items_parsed, location)
st.session_state[“price_data”] = data
st.success(“Prices found!”)
except Exception as e:
st.error(“Search failed: “ + str(e))
st.stop()
data = st.session_state.get(“price_data”)
if not data or not data.get(“items”):
st.info(“Enter your grocery list and click Compare Prices to get started.”)
return
import pandas as pd
items = data[“items”]
store_totals = compute_store_totals(items)
optimal = compute_optimal_list(items)
opt_total = sum(i[“price”] for si in optimal.values() for i in si)
ranked = sorted([s for s in STORES if store_totals[s][“count”] > 0], key=lambda s: store_totals[s][“total”])
max_total = store_totals[ranked[-1]][“total”] if ranked else 0
st.markdown(”—”)
st.subheader(“Results”)
st.caption(“Location: “ + data.get(“location”, location) + “  |  “ + data.get(“searched_at”, “”) + “  |  “ + str(len(items)) + “ items”)
st.markdown(
“<div class='savings-box'><h3 style='color:#b8e04a;margin:0 0 6px 0'>”
+ “Optimal split saves you $” + str(round(max_total - opt_total, 2))
+ “</h3><p style='color:#aaa;margin:0'>Best single store: <strong style='color:#b8e04a'>”
+ (ranked[0] if ranked else “”)
+ “</strong></p></div>”,
unsafe_allow_html=True
)
st.markdown(””)
st.markdown(”##### Store Totals”)
cols = st.columns(len(ranked))
for col, store in zip(cols, ranked):
t = store_totals[store]
is_winner = store == ranked[0]
color = STORE_COLORS[store]
with col:
badge = “<div><span class='winner-badge'>BEST</span></div>” if is_winner else “”
st.markdown(
“<div class='store-card " + ("winner" if is_winner else "") + "'>”
+ badge
+ “<div style='color:" + color + ";font-weight:800;font-size:11px;text-transform:uppercase;margin:6px 0 8px'>” + store + “</div>”
+ “<div style='font-size:26px;font-weight:900;font-family:monospace;color:" + ("#b8e04a" if is_winner else "#333") + ";'>$” + str(round(t[“total”], 2)) + “</div>”
+ “<div style='font-size:11px;color:#888;margin-top:4px'>” + str(t[“count”]) + “/” + str(len(items)) + “ items</div>”
+ “</div>”,
unsafe_allow_html=True
)
st.markdown(””)
st.markdown(”##### Item-by-Item Breakdown”)
rows = []
for item in items:
valid = [float(item[“prices”].get(s)) for s in STORES if item[“prices”].get(s) is not None]
min_p = min(valid) if valid else None
row = {“Item”: item[“name”], “Unit”: item.get(“unit”, “”)}
for store in STORES:
p = item[“prices”].get(store)
row[store.replace(” Fresh”, “”)] = “$” + str(round(float(p), 2)) if p is not None else “-”
row[“Best”] = next((s.replace(” Fresh”, “”) for s in STORES if item[“prices”].get(s) is not None and float(item[“prices”].get(s)) == min_p), “-”) if min_p is not None else “-”
if item.get(“notes”):
row[“Notes”] = item[“notes”]
rows.append(row)
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.markdown(”##### Optimized Shopping Lists”)
st.caption(“Buy each item at its cheapest store”)
num_cols = min(len(optimal), 3)
list_cols = st.columns(num_cols)
for idx, (store, store_items) in enumerate(optimal.items()):
subtotal = sum(i[“price”] for i in store_items)
color = STORE_COLORS[store]
with list_cols[idx % num_cols]:
st.markdown(”**<span style='color:" + color + "'>” + store + “</span>**”, unsafe_allow_html=True)
st.dataframe(pd.DataFrame([{“Item”: i[“name”], “Price”: “$” + str(round(i[“price”], 2))} for i in store_items]), use_container_width=True, hide_index=True)
st.markdown(”**Subtotal: $” + str(round(subtotal, 2)) + “**”)
st.markdown(”—”)
c1, c2, c3 = st.columns(3)
c1.metric(“Optimal Total”, “$” + str(round(opt_total, 2)))
c2.metric(“Priciest Single Store”, “$” + str(round(max_total, 2)))
c3.metric(“You Save”, “$” + str(round(max_total - opt_total, 2)), delta=”-$” + str(round(max_total - opt_total, 2)), delta_color=“inverse”)
st.markdown(”—”)
st.subheader(“Export”)
export_text = build_text_export(data, store_totals, optimal)
export_csv = build_csv_export(data)
col_a, col_b = st.columns(2)
with col_a:
st.download_button(label=“Download as .txt”, data=export_text, file_name=“cartsmart.txt”, mime=“text/plain”, use_container_width=True)
with col_b:
st.download_button(label=“Download as .csv”, data=export_csv, file_name=“cartsmart.csv”, mime=“text/csv”, use_container_width=True)
st.caption(“Prices sourced via live Google Search. Verify at checkout. Costco requires membership.”)

if **name** == “**main**”:
main()
