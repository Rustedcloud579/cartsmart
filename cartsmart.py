import streamlit as st
import anthropic
import json
import re
from io import BytesIO

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
page_title=“CartSmart – Grocery Price Comparison”,
page_icon=“🛒”,
layout=“wide”,
)

# ── Styling ────────────────────────────────────────────────────────────────────

st.markdown(”””

<style>
  .main { background-color: #0e0f0c; }
  h1 { color: #b8e04a !important; letter-spacing: 2px; }
  .store-card {
    background: #16180f;
    border: 1px solid #2a2e1a;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
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
  }
</style>

“””, unsafe_allow_html=True)

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

# ── Claude price search ────────────────────────────────────────────────────────

def search_prices(items: list[str], location: str) -> dict:
“””
Uses Claude with web search tool to find real current prices
for each item at each of the 5 stores.
Returns parsed price data dict.
“””
client = anthropic.Anthropic(api_key=st.secrets[“ANTHROPIC_API_KEY”])

```
item_list = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

system = (
    "You are a grocery price research assistant. "
    "Use web search to find CURRENT real prices for each grocery item at each store. "
    "Search each store individually for accuracy. "
    "After researching, respond ONLY with a valid JSON object — no markdown, no explanation. "
    "JSON structure: "
    '{"items":[{"name":"item","unit":"per lb/each/pack","prices":{'
    '"Amazon Fresh":4.99,"Costco":9.99,"Walmart":3.78,"Kroger":4.29,"Albertsons":4.49},'
    '"notes":"any relevant note"}],'
    '"location":"city, state","searched_at":"month year"} '
    "Use null if a store does not carry the item. All prices must be numbers."
)

user = (
    f"Location: {location}\n\n"
    f"Grocery list:\n{item_list}\n\n"
    "Search for current prices at all 5 stores and return the JSON."
)

messages = [{"role": "user", "content": user}]

# Agentic loop — handle web search tool calls
with st.spinner("🔍 Searching current prices across 5 stores…"):
    for _ in range(10):  # max 10 iterations
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            system=system,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        # Add assistant turn to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract text
            text = "".join(
                block.text for block in response.content
                if hasattr(block, "text")
            )
            return parse_price_json(text)

        if response.stop_reason == "tool_use":
            # Feed tool results back
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # The web_search tool auto-executes; result is in block.content
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": getattr(block, "content", "") or "",
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue

        break  # unexpected stop reason

raise ValueError("No price data returned from Claude after search.")
```

def parse_price_json(text: str) -> dict:
“”“Robustly extract JSON from Claude’s response text.”””
cleaned = re.sub(r”`json\s*", "", text, flags=re.IGNORECASE) cleaned = re.sub(r"`\s*”, “”, cleaned).strip()

```
# Try direct parse
try:
    return json.loads(cleaned)
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
        return json.loads(cleaned[start:end + 1])
    except Exception:
        pass

raise ValueError(f"Could not parse price JSON from response:\n{text[:500]}")
```

# ── Computation helpers ────────────────────────────────────────────────────────

def compute_store_totals(items: list) -> dict:
totals = {}
for store in STORES:
total, count = 0.0, 0
for item in items:
p = item[“prices”].get(store)
if p is not None:
total += p
count += 1
totals[store] = {“total”: total, “count”: count}
return totals

def compute_optimal_list(items: list) -> dict:
optimal = {}
for item in items:
best_price, best_store = float(“inf”), None
for store in STORES:
p = item[“prices”].get(store)
if p is not None and p < best_price:
best_price, best_store = p, store
if best_store:
optimal.setdefault(best_store, []).append(
{“name”: item[“name”], “price”: best_price, “unit”: item.get(“unit”, “”)}
)
return optimal

# ── Export helpers ─────────────────────────────────────────────────────────────

def build_text_export(data: dict, store_totals: dict, optimal: dict) -> str:
lines = [
“CARTSMART GROCERY PRICE COMPARISON”,
f”Location: {data.get(‘location’, ‘’)}”,
f”Searched: {data.get(‘searched_at’, ‘’)}”,
“=” * 60,
“”,
“STORE TOTALS”,
“-” * 40,
]
ranked = sorted(
[s for s in STORES if store_totals[s][“count”] > 0],
key=lambda s: store_totals[s][“total”]
)
for s in ranked:
lines.append(f”  {s:<20} ${store_totals[s][‘total’]:.2f}  ({store_totals[s][‘count’]}/{len(data[‘items’])} items)”)

```
lines += ["", "ITEM-BY-ITEM BREAKDOWN", "-" * 40]
header = f"{'Item':<35}" + "".join(f"{s.replace(' Fresh',''):<14}" for s in STORES) + "Best"
lines.append(header)
lines.append("-" * len(header))

for item in data["items"]:
    valid = [item["prices"].get(s) for s in STORES if item["prices"].get(s) is not None]
    min_p = min(valid) if valid else None
    best_s = next((s for s in STORES if item["prices"].get(s) == min_p), "") if min_p else ""
    row = f"{item['name'][:34]:<35}"
    for s in STORES:
        p = item["prices"].get(s)
        row += f"{'$'+f'{p:.2f}' if p is not None else '—':<14}"
    row += best_s.replace(" Fresh", "")
    lines.append(row)

lines += ["", "OPTIMIZED SHOPPING LISTS", "-" * 40]
opt_total = sum(i["price"] for items in optimal.values() for i in items)
max_total = store_totals[ranked[-1]]["total"] if ranked else 0

for store, items in optimal.items():
    subtotal = sum(i["price"] for i in items)
    lines += [f"\n  🛒 {store}", "  " + "-" * 30]
    for i in items:
        lines.append(f"  {i['name']:<35} ${i['price']:.2f}")
    lines.append(f"  {'SUBTOTAL':<35} ${subtotal:.2f}")

lines += [
    "",
    "=" * 60,
    f"OPTIMAL TOTAL (split across stores): ${opt_total:.2f}",
    f"MOST EXPENSIVE SINGLE STORE:         ${max_total:.2f}",
    f"YOU SAVE:                            ${max_total - opt_total:.2f}",
]
return "\n".join(lines)
```

# ── Main UI ────────────────────────────────────────────────────────────────────

def main():
st.title(“🛒 CartSmart”)
st.markdown(”**Grocery Price Intelligence — 5-Store Comparison**”)
st.markdown(”—”)

```
# ── Sidebar ──
with st.sidebar:
    st.header("⚙️ Settings")
    location = st.text_input("📍 ZIP Code or City", value="83709", help="Used to find local pricing")
    st.markdown("**Stores compared:**")
    for store, color in STORE_COLORS.items():
        st.markdown(f"<span style='color:{color}'>●</span> {store}", unsafe_allow_html=True)
    st.markdown("---")
    st.caption("Prices sourced via live web search using Claude AI.")

# ── Input ──
st.subheader("📋 Your Grocery List")
st.caption("One item per line. Include quantities where helpful (e.g. '4 lbs ground buffalo meat').")

raw_input = st.text_area(
    "Grocery list",
    value=PLACEHOLDER,
    height=250,
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 4])
with col1:
    search_clicked = st.button("🔍 Compare Prices", type="primary", use_container_width=True)

# ── Parse items ──
items_parsed = [line.strip() for line in raw_input.strip().splitlines() if line.strip()]

if items_parsed:
    st.caption(f"{len(items_parsed)} items ready to compare")

# ── Run search ──
if search_clicked:
    if not items_parsed:
        st.warning("Please enter at least one grocery item.")
        return

    try:
        data = search_prices(items_parsed, location)
        st.session_state["price_data"] = data
    except Exception as e:
        st.error(f"Search failed: {e}")
        return

# ── Display results ──
data = st.session_state.get("price_data")
if not data or not data.get("items"):
    st.info("Enter your grocery list above and click **Compare Prices** to get started.")
    return

items = data["items"]
store_totals = compute_store_totals(items)
optimal = compute_optimal_list(items)
opt_total = sum(i["price"] for store_items in optimal.values() for i in store_items)
ranked = sorted(
    [s for s in STORES if store_totals[s]["count"] > 0],
    key=lambda s: store_totals[s]["total"]
)
max_total = store_totals[ranked[-1]]["total"] if ranked else 0

st.markdown("---")
st.subheader("📊 Results")
st.caption(f"📍 {data.get('location', location)} · {data.get('searched_at', '')} · {len(items)} items")

# Savings callout
st.markdown(f"""
<div class="savings-box">
  <h3 style="color:#b8e04a;margin:0 0 6px 0">💰 Optimal split saves you ${max_total - opt_total:.2f}</h3>
  <p style="color:#7a8060;margin:0">Buy each item at its cheapest store vs. shopping everything at <strong style="color:#e8ead8">{ranked[-1] if ranked else ''}</strong> &nbsp;·&nbsp;
  Best single store: <strong style="color:#b8e04a">{ranked[0] if ranked else ''}</strong></p>
</div>
""", unsafe_allow_html=True)
st.markdown("")

# Store total cards
st.markdown("##### Store Totals")
cols = st.columns(len(ranked))
for col, store in zip(cols, ranked):
    t = store_totals[store]
    is_winner = store == ranked[0]
    color = STORE_COLORS[store]
    with col:
        badge = '<span class="winner-badge">BEST</span>' if is_winner else ""
        st.markdown(f"""
        <div class="store-card {'winner' if is_winner else ''}">
          {badge}
          <div style="color:{color};font-weight:800;font-size:12px;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">{store}</div>
          <div style="font-size:28px;font-weight:900;font-family:monospace;color:{'#b8e04a' if is_winner else '#e8ead8'}">${t['total']:.2f}</div>
          <div style="font-size:11px;color:#7a8060">{t['count']}/{len(items)} items</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("")

# Item breakdown table
st.markdown("##### Item-by-Item Breakdown")

import pandas as pd

rows = []
for item in items:
    valid = [item["prices"].get(s) for s in STORES if item["prices"].get(s) is not None]
    min_p = min(valid) if valid else None
    row = {"Item": item["name"], "Unit": item.get("unit", "")}
    for store in STORES:
        p = item["prices"].get(store)
        row[store.replace(" Fresh", "")] = f"${p:.2f}" if p is not None else "—"
    row["Best"] = next(
        (s.replace(" Fresh", "") for s in STORES if item["prices"].get(s) == min_p), "—"
    ) if min_p is not None else "—"
    if item.get("notes"):
        row["Notes"] = item["notes"]
    rows.append(row)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# Optimal shopping lists
st.markdown("##### 🛍️ Optimized Shopping Lists")
st.caption("Buy each item at its cheapest store")

list_cols = st.columns(min(len(optimal), 3))
for idx, (store, store_items) in enumerate(optimal.items()):
    subtotal = sum(i["price"] for i in store_items)
    color = STORE_COLORS[store]
    with list_cols[idx % 3]:
        st.markdown(f"**<span style='color:{color}'>{store}</span>**", unsafe_allow_html=True)
        list_df = pd.DataFrame([
            {"Item": i["name"], "Price": f"${i['price']:.2f}"}
            for i in store_items
        ])
        st.dataframe(list_df, use_container_width=True, hide_index=True)
        st.markdown(f"**Subtotal: ${subtotal:.2f}**")
        st.markdown("")

# Summary bar
st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("Optimal Total", f"${opt_total:.2f}", help="Shopping optimally across stores")
c2.metric("Most Expensive Single Store", f"${max_total:.2f}", help=f"Shopping only at {ranked[-1] if ranked else ''}")
c3.metric("You Save", f"${max_total - opt_total:.2f}", delta=f"-${max_total - opt_total:.2f}", delta_color="inverse")

# Export
st.markdown("---")
st.subheader("📥 Export")
export_text = build_text_export(data, store_totals, optimal)

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
    # CSV export
    import csv
    from io import StringIO
    csv_buf = StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["Item", "Unit"] + STORES + ["Best Store", "Notes"])
    for item in items:
        valid = [item["prices"].get(s) for s in STORES if item["prices"].get(s) is not None]
        min_p = min(valid) if valid else None
        best_s = next((s for s in STORES if item["prices"].get(s) == min_p), "") if min_p else ""
        writer.writerow(
            [item["name"], item.get("unit", "")]
            + [item["prices"].get(s, "") for s in STORES]
            + [best_s, item.get("notes", "")]
        )
    st.download_button(
        label="⬇️ Download as .csv",
        data=csv_buf.getvalue(),
        file_name="cartsmart_comparison.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption("⚠️ Prices are sourced via live web search and may vary by location and date. Always verify at checkout.")
```

if **name** == “**main**”:
main()
