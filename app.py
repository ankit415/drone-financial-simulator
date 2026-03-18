import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Per-FY capacity & monthly growth | Delayed collection % | Raises per FY")

# Persistent basic product info
if 'products_basic' not in st.session_state:
    st.session_state.products_basic = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [30000, 8000, 350000, 800000],
        "Manufacturing Cost per unit (₹)": [15000, 3500, 170000, 350000],
    })

products = st.session_state.products_basic

# Per-Year Parameters
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

# Product prices & costs
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

# Company-wide
st.sidebar.header("Company-wide Assumptions")
initial_cash_cr = st.sidebar.number_input("Starting Cash (₹ Cr)", value=2.0, step=0.5, min_value=0.0)
fixed_opex_annual_cr = st.sidebar.number_input("Annual Fixed OpEx (₹ Cr)", value=2.0, step=0.2, min_value=0.0)
service_cost_annual_cr = st.sidebar.number_input("Annual Product Service Cost (₹ Cr)", value=0.8, step=0.1, min_value=0.0)
capex_annual_cr = st.sidebar.number_input("Annual Capex (₹ Cr)", value=1.5, step=0.5, min_value=0.0)

months = st.sidebar.slider("Forecast Horizon (months)", 12, 72, 36)
n_simulations = st.sidebar.slider("Monte Carlo Runs", 1000, 5000, 2000, step=500)
monthly_noise_pct = st.sidebar.slider("Monthly Volume Noise ±%", 0, 35, 12)

# ────────────────────────────────────────────────
# SIMULATION – Fixed version
# ────────────────────────────────────────────────
def run_simulation():
    rev_delivered_paths = []
    cash_in_paths = []
    outflow_paths = []
    ending_cash_list = []

    max_years = len(per_year_df)

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        rev_delivered_run = [0.0] * months
        cash_in_run = [0.0] * months
        outflow_run = [0.0] * months

        # Capacities will be reset each year
        capacities = None

        for m in range(months):
            year_idx = min(m // 12, max_years - 1)
            fy_row = per_year_df.iloc[year_idx]

            # Reset capacities at start of each new fiscal year
            if m % 12 == 0:
                capacities = np.array([
                    fy_row[f"{p} Monthly Capacity"] for p in products["Product"]
                ], dtype=float)

            # Apply monthly growth to current capacities
            rev_delivered_month = 0.0
            mfg_month = 0.0   # FIXED: initialize here every month

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

            # Investment raise (already handled above)

            rev_delivered_run[m] = rev_delivered_month / 1e7
            cash_in_run[m] = cash_in_month / 1e7
            outflow_run[m] = total_out / 1e7

        rev_delivered_paths.append(rev_delivered_run)
        cash_in_paths.append(cash_in_run)
        outflow_paths.append(outflow_run)
        ending_cash_list.append(cash / 1e7)

    median_rev_del = np.median(rev_delivered_paths, axis=0)
    median_cash_in = np.median(cash_in_paths, axis=0)
    median_out = np.median(outflow_paths, axis=0)
    median_ending = np.median(ending_cash_list)

    return median_rev_del, median_cash_in, median_out, median_ending, rev_delivered_paths, cash_in_paths, outflow_paths

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        med_rev_del, med_cash_in, med_out, med_ending, all_rev_del, all_cash_in, all_out = run_simulation()

    # Summary
    st.subheader("Summary (median outcome)")
    cols = st.columns(5)
    cols[0].metric("Ending Cash", f"₹{med_ending:.1f} Cr")
    cols[1].metric("Avg Monthly Cash Inflow (last 6 mo)", f"₹{np.mean(med_cash_in[-6:]):.1f} Cr")
    cols[2].metric("Avg Monthly Outflow", f"₹{np.mean(med_out):.1f} Cr")
    cols[3].metric("Peak Monthly Burn", f"₹{max(med_out - med_cash_in):.1f} Cr" if max(med_out - med_cash_in) > 0 else "Positive")
    cols[4].metric("Total Raises Planned", f"₹{per_year_df['Investment Raise (₹ Cr) this FY'].sum():.1f} Cr")

    # Monthly cash flow chart
    st.subheader("Monthly Cash Inflow vs Total Outflow")
    fig_monthly = go.Figure()
    months_axis = list(range(months))
    fig_monthly.add_trace(go.Scatter(x=months_axis, y=med_cash_in, name="Cash Inflow", line_color="#2ca02c", fill='tozeroy'))
    fig_monthly.add_trace(go.Scatter(x=months_axis, y=med_out, name="Outflow (incl. Capex)", line_color="#d62728", fill='tozeroy'))
    fig_monthly.update_layout(
        title="Monthly Cash Inflow vs Total Outflow — Median Path",
        xaxis_title="Month",
        yaxis_title="₹ Crores per month",
        hovermode="x unified",
        height=500
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    # Cumulative chart
    st.subheader("Cumulative Cash Inflow vs Cumulative Outflow")
    cum_in = np.cumsum(med_cash_in)
    cum_out = np.cumsum(med_out)

    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(x=months_axis, y=cum_in, name="Cumulative Cash Inflow", line_color="#2ca02c", fill='tozeroy'))
    fig_cum.add_trace(go.Scatter(x=months_axis, y=cum_out, name="Cumulative Outflow", line_color="#d62728", fill='tozeroy'))
    fig_cum.update_layout(
        title="Cumulative View",
        xaxis_title="Month",
        yaxis_title="Cumulative ₹ Crores",
        height=500
    )
    st.plotly_chart(fig_cum, use_container_width=True)

    # Yearly summary table
    st.subheader("Yearly Financial Summary (median values)")
    yearly_rows = []
    for y in range((months + 11) // 12):
        start = y * 12
        end = min(start + 12, months)
        rev_del_y = np.mean([sum(path[start:end]) for path in all_rev_del])
        cash_in_y = np.mean([sum(path[start:end]) for path in all_cash_in])
        out_y = np.mean([sum(path[start:end]) for path in all_out])

        raise_y = per_year_df.iloc[y]["Investment Raise (₹ Cr) this FY"] if y < len(per_year_df) else 0

        mfg_y = out_y - (fixed_opex_annual_cr + service_cost_annual_cr + capex_annual_cr)
        gross_y = rev_del_y - mfg_y
        ebitda_y = gross_y - (fixed_opex_annual_cr + service_cost_annual_cr)

        yearly_rows.append({
            "Fiscal Year": f"FY {26+y}-{27+y}",
            "Delivered Revenue (₹ Cr)": round(rev_del_y, 1),
            "Cash Inflow (₹ Cr)": round(cash_in_y, 1),
            "Investment Raised (₹ Cr)": round(raise_y, 1),
            "Manufacturing Expense (₹ Cr)": round(mfg_y, 1),
            "Gross Profit (₹ Cr)": round(gross_y, 1),
            "Fixed + Service (₹ Cr)": round(fixed_opex_annual_cr + service_cost_annual_cr, 1),
            "Capex (₹ Cr)": round(capex_annual_cr, 1),
            "EBITDA approx (₹ Cr)": round(ebitda_y, 1)
        })

    st.dataframe(pd.DataFrame(yearly_rows), use_container_width=True, hide_index=True)

    with st.expander("Model notes"):
        st.markdown("""
        - Each FY starts with its own base monthly capacity (edited per year)  
        - Capacity grows monthly within the FY using that year's growth rate  
        - Cash inflow = Delivered revenue × Collection % (per FY)  
        - Raises added at start of each FY  
        - All costs paid immediately → shows real cash pressure  
        """)

else:
    st.info("Adjust per-year parameters or other inputs → click **Run Simulation**")

st.caption("Stable version | FY-specific capacity & growth fully respected | Cash flow focus")
