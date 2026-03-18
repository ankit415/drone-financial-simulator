import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Investor Financial Simulator")
st.markdown("Per-FY parameters | Delayed collection | Raises per FY | Full KPI dashboard")

# ────────────────────────────────────────────────
# Persistent basic product info
# ────────────────────────────────────────────────
if 'products_basic' not in st.session_state:
    st.session_state.products_basic = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [30000, 8000, 350000, 800000],
        "Manufacturing Cost per unit (₹)": [15000, 3500, 170000, 350000],
    })

if 'products_basic' not in st.session_state:
    st.session_state.products_basic = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [30000, 8000, 350000, 800000],
        "Manufacturing Cost per unit (₹)": [15000, 3500, 170000, 350000],
    })

products = st.session_state.products_basic

# ────────────────────────────────────────────────
# Per-Year Parameters
# ────────────────────────────────────────────────
st.sidebar.header("Per-Year Parameters")

if 'per_year_data' not in st.session_state:
    st.session_state.per_year_data = pd.DataFrame({
        "Fiscal Year": ["FY26-27", "FY27-28", "FY28-29"],
        "AlgoX Monthly Capacity": [275, 600, 1000],
        "AlgoX Monthly Growth %": [5, 5, 5],
        "AlgoBMS Monthly Capacity": [150, 400, 1000],
        "AlgoBMS Monthly Growth %": [2, 3, 10],
        "AlgoPAD Monthly Capacity": [2, 4, 10],
        "AlgoPAD Monthly Growth %": [2, 2, 3],
        "AlgoDOCK Monthly Capacity": [1, 4, 7],
        "AlgoDOCK Monthly Growth %": [3, 3.0, 3.0],
        "Collection % (this FY)": [80, 80, 80],
        "Investment Raise (₹ Cr) this FY": [0, 0, 0]
    })

per_year_df = st.sidebar.data_editor(
    st.session_state.per_year_data,
    num_rows="dynamic",
    use_container_width=True,
    key="per_year_editor"
)

if not per_year_df.equals(st.session_state.per_year_data):
    st.session_state.per_year_data = per_year_df.copy()

# ────────────────────────────────────────────────
# Product prices & costs
# ────────────────────────────────────────────────
st.sidebar.header("Product Prices & Costs")
edited_basic = st.sidebar.data_editor(
    products,
    num_rows="fixed",
    use_container_width=True,
    key="basic_editor"
)
if not edited_basic.equals(st.session_state.products_basic):
    st.session_state.products_basic = edited_basic.copy()

products = edited_basic

# ────────────────────────────────────────────────
# Company-wide
# ────────────────────────────────────────────────
st.sidebar.header("Company-wide Assumptions")
initial_cash_cr = st.sidebar.number_input("Starting Cash (₹ Cr)", value=2.0, step=0.5, min_value=0.0)
fixed_opex_annual_cr = st.sidebar.number_input("Annual Fixed OpEx (₹ Cr)", value=2.0, step=0.2, min_value=0.0)
service_cost_annual_cr = st.sidebar.number_input("Annual Product Service Cost (₹ Cr)", value=0.8, step=0.1, min_value=0.0)
capex_annual_cr = st.sidebar.number_input("Annual Capex (₹ Cr)", value=1.5, step=0.5, min_value=0.0)

months = st.sidebar.slider("Forecast Horizon (months)", 12, 72, 36)
n_simulations = st.sidebar.slider("Monte Carlo Runs", 1000, 5000, 2000, step=500)
monthly_noise_pct = st.sidebar.slider("Monthly Volume Noise ±%", 0, 35, 12)

# ────────────────────────────────────────────────
# SIMULATION
# ────────────────────────────────────────────────
def run_simulation():
    net_cash_paths = []
    gm_paths = []
    cash_in_paths = []
    outflow_paths = []
    ending_cash_list = []

    max_years = len(per_year_df)

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        net_cash_run = [initial_cash_cr]
        gm_run = [0.0] * months
        cash_in_run = [0.0] * months
        outflow_run = [0.0] * months

        capacities = np.array([
            per_year_df.iloc[0][f"{p} Monthly Capacity"] for p in products["Product"]
        ], dtype=float)

        for m in range(months):
            year_idx = min(m // 12, max_years - 1)
            fy_row = per_year_df.iloc[year_idx]

            if m % 12 == 0 and year_idx < max_years:
                raise_this_year = fy_row["Investment Raise (₹ Cr) this FY"] * 1e7
                cash += raise_this_year

            rev_delivered_month = 0.0
            mfg_month = 0.0

            for i, prod in enumerate(products["Product"]):
                monthly_growth = fy_row[f"{prod} Monthly Growth %"] / 100
                capacities[i] *= (1 + monthly_growth)

                units = capacities[i] * np.random.normal(1.0, monthly_noise_pct / 100.0)
                units = max(0, units)

                rev_delivered = units * products.at[i, "Selling Price (₹)"]
                mfg = units * products.at[i, "Manufacturing Cost per unit (₹)"]

                rev_delivered_month += rev_delivered
                mfg_month += mfg

            collection_pct = fy_row["Collection % (this FY)"] / 100
            cash_in_month = rev_delivered_month * collection_pct

            monthly_fixed = (fixed_opex_annual_cr + service_cost_annual_cr) * 1e7 / 12
            monthly_capex = capex_annual_cr * 1e7 / 12
            total_out = mfg_month + monthly_fixed + monthly_capex

            fcf = cash_in_month - total_out
            cash += fcf
            cash = max(cash, 0)

            net_cash_run.append(cash / 1e7)
            gm_run[m] = ((rev_delivered_month - mfg_month) / rev_delivered_month * 100) if rev_delivered_month > 0 else 0
            cash_in_run[m] = cash_in_month / 1e7
            outflow_run[m] = total_out / 1e7

        net_cash_paths.append(net_cash_run)
        gm_paths.append(gm_run)
        cash_in_paths.append(cash_in_run)
        outflow_paths.append(outflow_run)
        ending_cash_list.append(cash / 1e7)

    median_net_cash = np.median(net_cash_paths, axis=0)
    median_gm = np.median(gm_paths, axis=0)
    median_cash_in = np.median(cash_in_paths, axis=0)
    median_out = np.median(outflow_paths, axis=0)
    median_ending = np.median(ending_cash_list)

    # KPIs
    avg_burn_last6 = np.mean(median_net_cash[-6:] - median_net_cash[-12:-6]) if len(median_net_cash) >= 12 else 0
    runway_months = (median_ending / abs(avg_burn_last6)) if avg_burn_last6 < 0 else float('inf')
    min_cash = np.min(median_net_cash)
    min_cash_month = np.argmin(median_net_cash)
    break_even_month = next((i for i, v in enumerate(median_net_cash) if v >= 0), None)

    return (
        median_net_cash, median_gm, median_cash_in, median_out,
        median_ending, runway_months, min_cash, min_cash_month, break_even_month
    )

# ────────────────────────────────────────────────
# RUN BUTTON & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        (
            median_net, median_gm, med_cash_in, med_out,
            med_ending, runway_mo, min_cash, min_mo, be_month
        ) = run_simulation()

    # ── KPI Cards ──
    st.subheader("Key Investor KPIs (median outcome)")
    cols = st.columns(5)
    cols[0].metric("Ending Cash", f"₹{med_ending:.1f} Cr")
    cols[1].metric("Months of Runway", f"{runway_mo:.1f}" if runway_mo != float('inf') else "∞")
    cols[2].metric("Lowest Cash Point", f"
