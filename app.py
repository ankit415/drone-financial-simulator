import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Per-FY capacity & monthly growth | Delayed cash collection % per FY")

# ────────────────────────────────────────────────
# Persistent basic product info
# ────────────────────────────────────────────────
if 'products_basic' not in st.session_state:
    st.session_state.products_basic = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [1000000, 500000, 300000, 800000],
        "Manufacturing Cost per unit (₹)": [550000, 280000, 170000, 450000],
    })

products = st.session_state.products_basic

# ────────────────────────────────────────────────
# Per-Year Inputs table (now includes Collection %)
# ────────────────────────────────────────────────
st.sidebar.header("Per-Year Parameters")

if 'per_year_data' not in st.session_state:
    st.session_state.per_year_data = pd.DataFrame({
        "Fiscal Year": ["FY26-27", "FY27-28", "FY28-29"],
        "AlgoX Monthly Capacity": [400, 600, 900],
        "AlgoX Monthly Growth %": [2.5, 2.0, 1.8],
        "AlgoBMS Monthly Capacity": [1000, 1500, 2200],
        "AlgoBMS Monthly Growth %": [3.0, 2.5, 2.0],
        "AlgoPAD Monthly Capacity": [1500, 2000, 2800],
        "AlgoPAD Monthly Growth %": [2.2, 1.8, 1.5],
        "AlgoDOCK Monthly Capacity": [500, 800, 1200],
        "AlgoDOCK Monthly Growth %": [3.5, 3.0, 2.5],
        "Collection % (this FY)": [60, 75, 85]   # NEW: per FY cash collection percentage
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
# Basic product prices & costs (still editable)
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
    revenue_delivered_paths = []   # what is produced/delivered
    cash_inflow_paths = []         # what is actually collected
    outflow_paths = []
    ending_cash_list = []

    max_years = len(per_year_df)

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        rev_delivered_run = [0.0] * months
        cash_in_run = [0.0] * months
        outflow_run = [0.0] * months

        capacities = np.array([
            per_year_df.iloc[0][f"{p} Monthly Capacity"] for p in products["Product"]
        ], dtype=float)

        for m in range(months):
            year_idx = min(m // 12, max_years - 1)
            fy_row = per_year_df.iloc[year_idx]

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

            gross = rev_delivered_month - mfg_month
            ebitda = gross - monthly_fixed
            tax = max(0, ebitda * 0.25)
            nopat = ebitda - tax

            # Cash flow: inflow from collections - full outflow
            fcf = cash_in_month - total_out
            cash += fcf
            cash = max(cash, 0)

            rev_delivered_run[m] = rev_delivered_month / 1e7
            cash_in_run[m] = cash_in_month / 1e7
            outflow_run[m] = total_out / 1e7

        revenue_delivered_paths.append(rev_delivered_run)
        cash_inflow_paths.append(cash_in_run)
        outflow_paths.append(outflow_run)
        ending_cash_list.append(cash / 1e7)

    median_delivered = np.median(revenue_delivered_paths, axis=0)
    median_cash_in = np.median(cash_inflow_paths, axis=0)
    median_out = np.median(outflow_paths, axis=0)
    median_ending = np.median(ending_cash_list)

    return median_delivered, median_cash_in, median_out, median_ending

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        med_delivered, med_cash_in, med_out, med_cash = run_simulation()

    # Summary
    st.subheader("Summary (median outcome)")
    cols = st.columns(5)
    cols[0].metric("Ending Cash", f"₹{med_cash:.1f} Cr")
    cols[1].metric("Avg Monthly Delivered Revenue (last 6 mo)", f"₹{np.mean(med_delivered[-6:]):.1f} Cr")
    cols[2].metric("Avg Monthly Cash Inflow (last 6 mo)", f"₹{np.mean(med_cash_in[-6:]):.1f} Cr")
    cols[3].metric("Avg Monthly Outflow", f"₹{np.mean(med_out):.1f} Cr")
    cols[4].metric("Peak Monthly Cash Burn", f"₹{max(med_out - med_cash_in):.1f} Cr" if max(med_out - med_cash_in) > 0 else "Positive")

    # Main chart – now shows cash inflow vs outflow
    st.subheader("Monthly Cash Inflow vs Total Outflow (incl. Capex)")

    fig = go.Figure()
    months_axis = list(range(months))

    fig.add_trace(go.Scatter(x=months_axis, y=med_cash_in,
                             name="Cash Inflow (after collection delay)",
                             line_color="#2ca02c",
                             fill='tozeroy',
                             fillcolor='rgba(44,160,44,0.18)'))

    fig.add_trace(go.Scatter(x=months_axis, y=med_out,
                             name="Expenses + Capex (paid immediately)",
                             line_color="#d62728",
                             fill='tozeroy',
                             fillcolor='rgba(214,39,40,0.18)'))

    fig.update_layout(
        title="Cash Inflow vs Total Cash Outflow — Median Path",
        xaxis_title="Month",
        yaxis_title="₹ Crores per month",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=550
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("How cash flow delay works"):
        st.markdown("""
        - **Delivered revenue** is calculated from grown capacity × price × noise  
        - Only **Collection %** of delivered revenue becomes cash in the current month  
        - The remaining portion is delayed (not collected yet) — creates realistic cash crunch  
        - All costs (mfg, fixed, service, capex) are paid in full in the current month  
        - Collection % changes per fiscal year (typical improvement as relationships mature)  
        """)

else:
    st.info("Adjust per-year collection %, capacity, growth or other inputs → click **Run Simulation**")

st.caption("Updated: cash collection delay per FY | Inputs persist | Bengaluru drone startup model")
