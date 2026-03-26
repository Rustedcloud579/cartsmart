import streamlit as st
import google.generativeai as genai
import json
import re
import csv
from io import StringIO

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
page_title=“CartSmart – Grocery Price Comparison”,
page_icon=“🛒”,
layout=“wide”,
)

# ── Styling ────────────────────────────────────────────────────────────────────

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
    letter-spacing: 0.1em;
  }
  .savings-box {
    background: linear-gradient(135deg, rgba(184,224,74,0.08), rgba(74,224,160,0.06));
    border: 1px solid rgba(184,224,74,0.3);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
  }
</style>

“””, unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────

STORES = [“Amazon Fresh”, “Costco”, “Walmart”, “Kroger”, “Albertsons”]

STORE_COLORS = {
“Amazon Fresh”: “#ff9900”,
“Costco”:       “#e31837”,
“Walmart”:      “#0071ce”,
“Kroger”:       “#5b9bd5”,
“Albertsons”:   “#00833e”,
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

# ── Gemini price search ────────────────────────────────────────────────────────

def search_prices(items: list, location: str) -> dict:
“””
Uses Gemini 2.0 Flash with Google Search grounding to find
real current prices for each item at each of the 5 stores.
Gemini’s free tier: 1,500 requests/day — no cost.
“””
genai.configure(api_key=st.secrets[“GEMINI_API_KEY”])

```
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools="google_search_retrieval",  # Google Search grounding — free
)

item_list = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

prompt = f"""You are a grocery price research assistant.
```

Use Google Search to find CURRENT real retail prices for each item below at each of these 5 stores: Amazon Fresh, Costco, Walmart, Kroger, Albertsons.

Location: {location}

Grocery list:
{item_list}

Search each store carefully for accurate current prices. Then respond ONLY with a valid JSON object — no markdown, no explanation, no code fences. Start your response with {{ and end with }}.

Required JSON structure:
{{
“items”: [
{{
“name”: “item name”,
“unit”: “per lb / each / per pack / etc”,
“prices”: {{
“Amazon Fresh”: 4.99,
“Costco”: 9.99,
“Walmart”: 3.78,
“Kroger”: 4.29,
“Albertsons”: 4.49
}},
“notes”: “optional note e.g. Costco sells in bulk 4lb pack”
}}
],
“location”: “city, state inferred from ZIP”,
“searched_at”: “month year”
}}

Rules:

- All price values must be numbers (not strings)
- Use null only if a store genuinely does not carry that item
- Costco prices should reflect their bulk pack sizing
- Be as accurate as possible using search results”””
  
  with st.spinner(“🔍 Searching live prices via Google Search across 5 stores…”):
  response = model.generate_content(prompt)
  
  # Extract text from response
  
  text = response.text if hasattr(response, “text”) else “”
  
  if not text:
  # Try candidates
  try:
  text = response.candidates[0].content.parts[0].text
  except Exception:
  pass
  
  if not text:
  raise ValueError(“Gemini returned an empty response. Please try again.”)
  
  return parse_price_json(text)

def parse_price_json(text: str) -> dict:
“”“Robustly extract JSON from Gemini’s response text.”””
# Strip markdown fences
cleaned = re.sub(r”`json\s*", "", text, flags=re.IGNORECASE) cleaned = re.sub(r"`\s*”, “”, cleaned).strip()

```
# Try direct parse first
try:
    data = json.loads(cleaned)
    if "items" in data:
        return data
except Exception:
    pass

# Find outermost { } by brace depth
depth, start, end = 0, -1, -1
for i, ch in enumerate(cleaned):
    if ch == "{":
        if depth == 0:
            start = i
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0 and start != -1:
            end = i
            break

if start != -1 and end != -1:
    try:
        data = json.loads(cleaned[start:end + 1])
        if "items" in data:
            return data
    except Exception:
        pass

raise ValueError(
    f"Could not parse price data from Gemini response.\n\n"
    f"Raw response (first 500 chars):\n{text[:500]}"
)
```

# ── Computation helpers ────────────────────────────────────────────────────────

def compute_store_totals(items: list) -> dict:
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

def compute_optimal_list(items: list) -> dict:
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

# ── Export helpers ─────────────────────────────────────────────────────────────

def build_text_export(data: dict, store_totals: dict, optimal: dict) -> str:
ranked = sorted(
[s for s in STORES if store_totals[s][“count”] > 0],
key=lambda s: store_totals[s][“total”],
)
opt_total = sum(i[“price”] for si in optimal.values() for i in si)
max_total = store_totals[ranked[-1]][“total”] if ranked else 0

```
lines = [
    "CARTSMART GROCERY PRICE COMPARISON",
    f"Location : {data.get('location', '')}",
    f"Searched : {data.get('searched_at', '')}",
    "=" * 62,
    "",
    "STORE TOTALS",
    "-" * 42,
]
for s in ranked:
    t = store_totals[s]
    marker = " ← BEST" if s == ranked[0] else ""
    lines.append(f"  {s:<22} ${t['total']:>7.2f}   ({t['count']}/{len(data['items'])} items){marker}")

lines += ["", "ITEM-BY-ITEM BREAKDOWN", "-" * 62]
col_w = 13
header = f"{'Item':<34}" + "".join(f"{s.replace(' Fresh',''):<{col_w}}" for s in STORES) + "Best"
lines += [header, "-" * len(header)]

for item in data["items"]:
    valid = [float(item["prices"].get(s)) for s in STORES if item["prices"].get(s) is not None]
    min_p = min(valid) if valid else None
    best_s = next((s for s in STORES if item["prices"].get(s) is not None and float(item["prices"].get(s)) == min_p), "")
    row = f"{item['name'][:33]:<34}"
    for s in STORES:
        p = item["prices"].get(s)
        cell = f"${float(p):.2f}" if p is not None else "—"
        row += f"{cell:<{col_w}}"
    row += best_s.replace(" Fresh", "")
    lines.append(row)

lines += ["", "OPTIMIZED SHOPPING LISTS (buy each item at its cheapest store)", "-" * 62]
for store, si in optimal.items():
    subtotal = sum(i["price"] for i in si)
    lines += [f"\n  🛒 {store}", "  " + "-" * 38]
    for i in si:
        lines.append(f"  {i['name']:<38} ${i['price']:.2f}")
    lines.append(f"  {'SUBTOTAL':<38} ${subtotal:.2f}")

lines += [
    "",
    "=" * 62,
    f"OPTIMAL TOTAL (across stores) : ${opt_total:.2f}",
    f"PRICIEST SINGLE STORE         : ${max_total:.2f}  ({ranked[-1] if ranked else ''})",
    f"YOU SAVE                      : ${max_total - opt_total:.2f}",
    "",
    "⚠  Prices sourced via Google Search. Verify at checkout.",
]
return "\n".join(lines)
```

def build_csv_export(data: dict, store_totals: dict) -> str:
buf = StringIO()
writer = csv.writer(buf)
writer.writerow([“Item”, “Unit”] + STORES + [“Best Store”, “Notes”])
for item in data[“items”]:
valid = [float(item[“prices”].get(s)) for s in STORES if item[“prices”].get(s) is not None]
min_p = min(valid) if valid else None
best_s = next((s for s in STORES if item[“prices”].get(s) is not None and float(item[“prices”].get(s)) == min_p), “”)
writer.writerow(
[item[“name”], item.get(“unit”, “”)]
+ [item[“prices”].get(s, “”) for s in STORES]
+ [best_s, item.get(“notes”, “”)]
)
return buf.getvalue()

# ── Main UI ────────────────────────────────────────────────────────────────────

def main():
# Header
st.title(“🛒 CartSmart”)
st.markdown(”**Grocery Price Intelligence — 5-Store Comparison · Powered by Google Gemini (Free)**”)
st.markdown(”—”)

```
# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    location = st.text_input(
        "📍 ZIP Code or City",
        value="83709",
        help="Enter your ZIP code for local pricing",
    )
    st.markdown("**Stores compared:**")
    for store, color in STORE_COLORS.items():
        st.markdown(f"<span style='color:{color}'>●</span> {store}", unsafe_allow_html=True)
    st.markdown("---")
    st.caption("🆓 Powered by Gemini 2.0 Flash free tier.\n1,500 searches/day at no cost.")

# Input
st.subheader("📋 Your Grocery List")
st.caption("One item per line. Include quantities where helpful (e.g. '4 lbs ground buffalo meat').")

raw_input = st.text_area(
    "Grocery list",
    value=PLACEHOLDER,
    height=260,
    label_visibility="collapsed",
)

items_parsed = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]

if items_parsed:
    st.caption(f"{len(items_parsed)} items ready · Location: {location}")

search_clicked = st.button("🔍 Compare Prices", type="primary")

# Run search
if search_clicked:
    if not items_parsed:
        st.warning("Please enter at least one grocery item.")
        st.stop()
    try:
        data = search_prices(items_parsed, location)
        st.session_state["price_data"] = data
        st.success("✅ Prices found!")
    except Exception as e:
        st.error(f"Search failed: {e}")
        st.stop()

# Display results
data = st.session_state.get("price_data")
if not data or not data.get("items"):
    st.info("👆 Enter your grocery list and click **Compare Prices** to get started.")
    return

import pandas as pd

items = data["items"]
store_totals = compute_store_totals(items)
optimal = compute_optimal_list(items)
opt_total = sum(i["price"] for si in optimal.values() for i in si)
ranked = sorted(
    [s for s in STORES if store_totals[s]["count"] > 0],
    key=lambda s: store_totals[s]["total"],
)
max_total = store_totals[ranked[-1]]["total"] if ranked else 0

st.markdown("---")
st.subheader("📊 Results")
st.caption(f"📍 {data.get('location', location)}  ·  {data.get('searched_at', '')}  ·  {len(items)} items")

# Savings callout
st.markdown(f"""
<div class="savings-box">
  <h3 style="color:#b8e04a;margin:0 0 6px 0">💰 Optimal split saves you ${max_total - opt_total:.2f}</h3>
  <p style="color:#555;margin:0">
    Buy each item at its cheapest store vs. shopping everything at
    <strong>{ranked[-1] if ranked else ''}</strong> &nbsp;·&nbsp;
    Best single store: <strong style="color:#b8e04a">{ranked[0] if ranked else ''}</strong>
  </p>
</div>
""", unsafe_allow_html=True)

# Store total cards
st.markdown("##### Store Totals")
cols = st.columns(len(ranked))
for col, store in zip(cols, ranked):
    t = store_totals[store]
    is_winner = store == ranked[0]
    color = STORE_COLORS[store]
    with col:
        badge = '<div><span class="winner-badge">BEST</span></div>' if is_winner else ""
        st.markdown(f"""
        <div class="store-card {'winner' if is_winner else ''}">
          {badge}
          <div style="color:{color};font-weight:800;font-size:11px;letter-spacing:0.1em;
                      text-transform:uppercase;margin:6px 0 8px">{store}</div>
          <div style="font-size:26px;font-weight:900;font-family:monospace;
                      color:{'#b8e04a' if is_winner else '#333'}">${t['total']:.2f}</div>
          <div style="font-size:11px;color:#888;margin-top:4px">{t['count']}/{len(items)} items</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")

# Item breakdown table
st.markdown("##### Item-by-Item Breakdown")
rows = []
for item in items:
    valid = [float(item["prices"].get(s)) for s in STORES if item["prices"].get(s) is not None]
    min_p = min(valid) if valid else None
    row = {"Item": item["name"], "Unit": item.get("unit", "")}
    for store in STORES:
        p = item["prices"].get(store)
        row[store.replace(" Fresh", "")] = f"${float(p):.2f}" if p is not None else "—"
    row["✅ Best"] = next(
        (s.replace(" Fresh", "") for s in STORES
         if item["prices"].get(s) is not None and float(item["prices"].get(s)) == min_p),
        "—"
    ) if min_p is not None else "—"
    if item.get("notes"):
        row["Notes"] = item["notes"]
    rows.append(row)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# Optimized shopping lists
st.markdown("##### 🛍️ Optimized Shopping Lists")
st.caption("Buy each item at its cheapest store")

num_cols = min(len(optimal), 3)
list_cols = st.columns(num_cols)
for idx, (store, store_items) in enumerate(optimal.items()):
    subtotal = sum(i["price"] for i in store_items)
    color = STORE_COLORS[store]
    with list_cols[idx % num_cols]:
        st.markdown(f"**<span style='color:{color}'>{store}</span>**", unsafe_allow_html=True)
        list_df = pd.DataFrame([
            {"Item": i["name"], "Price": f"${i['price']:.2f}"}
            for i in store_items
        ])
        st.dataframe(list_df, use_container_width=True, hide_index=True)
        st.markdown(f"**Subtotal: ${subtotal:.2f}**")

# Summary metrics
st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("🏆 Optimal Total", f"${opt_total:.2f}", help="Splitting across cheapest stores")
c2.metric("💸 Priciest Single Store", f"${max_total:.2f}", help=f"{ranked[-1] if ranked else ''}")
c3.metric("💰 You Save", f"${max_total - opt_total:.2f}",
          delta=f"-${max_total - opt_total:.2f}", delta_color="inverse")

# Export
st.markdown("---")
st.subheader("📥 Export Shopping Lists")

export_text = build_text_export(data, store_totals, optimal)
export_csv = build_csv_export(data, store_totals)

col_a, col_b = st.columns(2)
with col_a:
    st.download_button(
        label="⬇️ Download as .txt",
        data=export_text,
        file_name="cartsmart_comparison.txt",
        mime="text/plain",
        use_container_width=True,
    )
with col_b:
    st.download_button(
        label="⬇️ Download as .csv",
        data=export_csv,
        file_name="cartsmart_comparison.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption("⚠️ Prices sourced via live Google Search. May vary by location, membership (Costco), and date. Verify at checkout.")
```

if **name** == “**main**”:
main()
