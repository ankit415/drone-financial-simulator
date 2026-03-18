import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Simplified investor view — 4 products | Annual growth | Fixed costs & capex")

# ────────────────────────────────────────────────
# SIDEBAR – Product table + core assumptions
# ────────────────────────────────────────────────
st.sidebar.header("Product Parameters (FY26-27 base year)")

default_products = pd.DataFrame({
    "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
    "Selling Price (₹)": [1000000, 500000, 300000, 800000],
    "Units in FY26-27": [4000, 10000, 15000, 5000],
    "Manufacturing Cost per unit (₹)": [550000, 280000, 170000, 450000],
    "Annual Sales Growth %": [35, 40, 30, 50]
})

products = st.sidebar.data_editor(
    default_products,
    num_rows="fixed",
    use_container_width=True,
    column_config={
        "Selling Price (₹)": st.column_config.NumberColumn(format="%d"),
        "Units in FY26-27": st.column_config.NumberColumn(format="%d", min_value=0),
        "Manufacturing Cost per unit (₹)": st.column_config.NumberColumn(format="%d", min_value=0),
        "Annual Sales Growth %": st.column_config.NumberColumn(format="%d", min_value=0, max_value=200)
    }
)

# Auto-calculated totals
products["Revenue FY26-27 (₹ Cr)"] = (products["Selling Price (₹)"] * products["Units in FY26-27"]) / 1e7
products["Manufacturing Expense FY26-27 (₹ Cr)"] = (products["Manufacturing Cost per unit (₹)"] * products["Units in FY26-27"]) / 1e7

total_rev_base = products["Revenue FY26-27 (₹ Cr)"].sum()
total_mfg_base = products["Manufacturing Expense FY26-27 (₹ Cr)"].sum()

st.sidebar.metric("Total Revenue FY26-27", f"₹{total_rev_base:.1f} Cr")
st.sidebar.metric("Total Manufacturing Expense FY26-27", f"₹{total_mfg_base:.1f} Cr")

# Other core assumptions
st.sidebar.header("Company-wide Assumptions")
initial_cash_cr = st.sidebar.number_input("Starting Cash (₹ Cr)", value=2.0, step=0.5, min_value=0.0)
fixed_opex_annual_cr = st.sidebar.number_input("Annual Fixed OpEx (₹ Cr)", value=2.0, step=0.2, min_value=0.0)
service_cost_annual_cr = st.sidebar.number_input("Annual Product Service Cost (₹ Cr)", value=0.8, step=0.1, min_value=0.0)
capex_annual_cr = st.sidebar.number_input("Annual Capex (₹ Cr)", value=1.5, step=0.5, min_value=0.0)

months = st.sidebar.slider("Forecast Horizon (months)", 12, 60, 24)
n_simulations = st.sidebar.slider("Monte Carlo Runs", 1000, 10000, 3000, step=500)
monthly_noise_pct = st.sidebar.slider("Monthly Volume Noise ±%", 0, 35, 12)

# ────────────────────────────────────────────────
# SIMULATION LOGIC
# ────────────────────────────────────────────────
def run_simulation():
    results = []
    cash_paths = []

    # Prepare monthly base per product
    products["Monthly Base Units"] = products["Units in FY26-27"] / 12   # spread evenly over 12 months

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        cash_history = [cash / 1e7]

        for m in range(months):
            year = m // 12
            total_rev = 0.0
            total_mfg = 0.0

            for _, row in products.iterrows():
                growth_factor = (1 + row["Annual Sales Growth %"] / 100) ** year
                trend_units = row["Monthly Base Units"] * growth_factor
                actual_units = trend_units * np.random.normal(1.0, monthly_noise_pct / 100)
                actual_units = max(0, actual_units)

                rev = actual_units * row["Selling Price (₹)"]
                mfg = actual_units * row["Manufacturing Cost per unit (₹)"]

                total_rev += rev
                total_mfg += mfg

            gross_profit = total_rev - total_mfg

            opex = (fixed_opex_annual_cr + service_cost_annual_cr) * 1e7 / 12
            ebitda = gross_profit - opex

            tax = max(0, ebitda * 0.25)           # simple 25% effective rate
            nopat = ebitda - tax

            capex_month = (capex_annual_cr * 1e7) / 12
            fcf = nopat - capex_month               # simplified (no WC lag for now)

            cash +=
