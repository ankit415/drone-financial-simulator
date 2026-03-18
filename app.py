import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Per-financial-year capacity & monthly growth | Monthly capacity × price model")

# ────────────────────────────────────────────────
# Persistent product list (basic info)
# ────────────────────────────────────────────────
if 'products_basic' not in st.session_state:
    st.session_state.products_basic = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [30000, 8000, 350000, 800000],
        "Manufacturing Cost per unit (₹)": [15000, 3500, 170000, 400000],
    })

products_basic = st.session_state.products_basic

# ────────────────────────────────────────────────
# Per-Year Inputs (capacity + monthly growth per FY per product)
# ────────────────────────────────────────────────
st.sidebar.header("Per-Year Inputs (Capacity & Growth)")

# Default per-year data (can be extended by user)
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
    })

per_year_df = st.sidebar.data_editor(
    st.session_state.per_year_data,
    num_rows="dynamic",
    use_container_width=True,
    key="per_year_editor"
)

# Save changes
if not per_year_df.equals(st.session_state.per_year_data):
    st.session_state.per_year_data = per_year_df.copy()

# ────────────────────────────────────────────────
# Basic product info (prices & costs) – still editable
# ────────────────────────────────────────────────
st.sidebar.header("Product Prices & Costs")
edited_basic = st.sidebar.data_editor(
    products_basic,
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
    revenue_paths = []
    outflow_paths = []
    ending_cash_list = []

    # Convert per-year df to easier lookup
    year_list = per_year_df["Fiscal Year"].tolist()
    max_years = len(year_list)

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        revenue_run = [0.0] * months
        outflow_run = [0.0] * months

        # Current capacities (start with first year)
        capacities = np.array([
            per_year_df.iloc[0][f"{p} Monthly Capacity"] for p in products["Product"]
        ], dtype=float)

        for m in range(months):
            year_idx = min(m // 12, max_years - 1)  # use last year if beyond table
            fy_row = per_year_df.iloc[year_idx]

            rev_month = 0.0
            mfg_month = 0.0

            for i, prod in enumerate(products["Product"]):
                # Apply monthly growth (from the current fiscal year's rate)
                monthly_growth = fy_row[f"{prod} Monthly Growth %"] / 100
                capacities[i] *= (1 + monthly_growth)

                # Noisy units (capped by grown capacity)
                units = capacities[i] * np.random.normal(1.0, monthly_noise_pct / 100.0)
                units = max(0, units)

                rev = units * products.at[i, "Selling Price (₹)"]
                mfg = units * products.at[i, "Manufacturing Cost per unit (₹)"]

                rev_month += rev
                mfg_month += mfg

            monthly_fixed = (fixed_opex_annual_cr + service_cost_annual_cr) * 1e7 / 12
            monthly_capex = capex_annual_cr * 1e7 / 12
            total_out = mfg_month + monthly_fixed + monthly_capex

            gross = rev_month - mfg_month
            ebitda = gross - monthly_fixed
            tax = max(0, ebitda * 0.25)
            nopat = ebitda - tax
            fcf = nopat - monthly_capex

            cash += fcf
            cash = max(cash, 0)

            revenue_run[m] = rev_month / 1e7
            outflow_run[m] = total_out / 1e7

        revenue_paths.append(revenue_run)
        outflow_paths.append(outflow_run)
        ending_cash_list.append(cash / 1e7)

    median_rev = np.median(revenue_paths, axis=0)
    median_out = np.median(outflow_paths, axis=0)
    median_cash = np.median(ending_cash_list)

    return median_rev, median_out, median_cash, revenue_paths, outflow_paths

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        median_rev, median_out, median_cash, all_rev, all_out = run_simulation()

    # Summary
    st.subheader("Summary (median outcome)")
    cols = st.columns(4)
    cols[0].metric("Ending Cash", f"₹{median_cash:.1f} Cr")
    cols[1].metric("Avg Monthly Revenue (last 6 mo)", f"₹{np.mean(median_rev[-6:]):.1f} Cr")
    cols[2].metric("Avg Monthly Outflow", f"₹{np.mean(median_out):.1f} Cr")
    cols[3].metric("Peak Monthly Burn", f"₹{max(median_out - median_rev):.1f} Cr" if max(median_out - median_rev) > 0 else "Positive")

    # Main chart
    st.subheader("Monthly Revenue vs Total Outflow (incl. Capex)")

    fig = go.Figure()
    months_axis = list(range(months))

    fig.add_trace(go.Scatter(x=months_axis, y=median_rev,
                             name="Revenue", line_color="#2ca02c",
                             fill='tozeroy', fillcolor='rgba(44,160,44,0.18)'))

    fig.add_trace(go.Scatter(x=months_axis, y=median_out,
                             name="Expenses + Capex", line_color="#d62728",
                             fill='tozeroy', fillcolor='rgba(214,39,40,0.18)'))

    fig.update_layout(
        title="Revenue vs Total Costs (incl. Capex) — Median Path",
        xaxis_title="Month",
        yaxis_title="₹ Crores per month",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=550
    )
    st.plotly_chart(fig, use_container_width=True)

    # Yearly summary table
    st.subheader("Yearly Financial Summary (median values)")

    yearly_rows = []
    for y in range((months + 11) // 12):
        start = y * 12
        end = min(start + 12, months)
        rev_y = np.mean([sum(path[start:end]) for path in all_rev])
        out_y = np.mean([sum(path[start:end]) for path in all_out])
        mfg_y = out_y - (fixed_opex_annual_cr + service_cost_annual_cr + capex_annual_cr)
        gross_y = rev_y - mfg_y
        ebitda_y = gross_y - (fixed_opex_annual_cr + service_cost_annual_cr)

        fy = f"FY {26+y}-{27+y}" if y < 3 else f"FY {26+y}-{27+y}"

        yearly_rows.append({
            "Fiscal Year": fy,
            "Revenue (₹ Cr)": round(rev_y, 1),
            "Mfg Expense (₹ Cr)": round(mfg_y, 1),
            "Gross Profit (₹ Cr)": round(gross_y, 1),
            "Fixed + Service (₹ Cr)": round(fixed_opex_annual_cr + service_cost_annual_cr, 1),
            "Capex (₹ Cr)": round(capex_annual_cr, 1),
            "EBITDA approx (₹ Cr)": round(ebitda_y, 1)
        })

    st.dataframe(pd.DataFrame(yearly_rows), use_container_width=True, hide_index=True)

    with st.expander("Model notes"):
        st.markdown("""
        - Each product starts the year with the **Monthly Capacity** defined for that FY  
        - Capacity grows **monthly** using the **Monthly Growth %** of that FY  
        - Monthly revenue = grown capacity × selling price (after noise)  
        - All values persist across page refreshes until you edit them  
        """)

else:
    st.info("Edit per-year capacities/growth rates or other inputs → click **Run Simulation**")

st.caption("Per-FY capacity & monthly growth | Inputs persist | Bengaluru drone startup model")
