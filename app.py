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
    gm_paths = []               # for gross margin %
    ending_cash_list = []

    max_years = len(per_year_df)

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        net_cash_run = [initial_cash_cr]
        gm_run = [0.0] * months

        capacities = np.array([
            per_year_df.iloc[0][f"{p} Monthly Capacity"] for p in products["Product"]
        ], dtype=float)

        for m in range(months):
            year_idx = min(m // 12, max_years - 1)
            fy_row = per_year_df.iloc[year_idx]

            # Raise at start of FY
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

            # Gross margin %
            gm_run[m] = ((rev_delivered_month - mfg_month) / rev_delivered_month * 100) if rev_delivered_month > 0 else 0

            net_cash_run.append(cash / 1e7)

        net_cash_paths.append(net_cash_run)
        gm_paths.append(gm_run)
        ending_cash_list.append(cash / 1e7)

    median_net_cash = np.median(net_cash_paths, axis=0)
    median_gm = np.median(gm_paths, axis=0)
    median_ending = np.median(ending_cash_list)

    # Calculate KPIs
    avg_burn_last6 = np.mean(median_net_cash[-6:] - median_net_cash[-12:-6]) if len(median_net_cash) >= 12 else 0
    runway_months = (median_ending / abs(avg_burn_last6)) if avg_burn_last6 < 0 else float('inf')
    min_cash = np.min(median_net_cash)
    min_cash_month = np.argmin(median_net_cash)
    break_even_month = next((i for i, v in enumerate(median_net_cash) if v >= 0), None)

    return median_net_cash, median_gm, median_ending, runway_months, min_cash, min_cash_month, break_even_month

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        median_net, median_gm, med_ending, runway_mo, min_cash, min_mo, be_month = run_simulation()

    # KPI Cards
    st.subheader("Key Investor KPIs (median outcome)")
    cols = st.columns(5)
    cols[0].metric("Ending Cash", f"₹{med_ending:.1f} Cr")
    cols[1].metric("Months of Runway", f"{runway_mo:.1f}" if runway_mo != float('inf') else "∞", delta_color="normal")
    cols[2].metric("Lowest Cash Point", f"₹{min_cash:.1f} Cr (Month {min_mo})", delta_color="inverse" if min_cash < 0 else "normal")
    cols[3].metric("Break-even Month", f"Month {be_month}" if be_month is not None else "Not reached")
    cols[4].metric("Avg Monthly Burn (last 6 mo)", f"₹{abs(np.mean(median_net[-6:] - median_net[-12:-6])):.1f} Cr/mo" if len(median_net) >= 12 else "N/A")

    # Chart 1: Monthly cash flow (inflow vs outflow)
    st.subheader("Monthly Cash Inflow vs Outflow")
    fig_monthly = go.Figure()
    months_axis = list(range(months))
    fig_monthly.add_trace(go.Scatter(x=months_axis, y=med_cash_in, name="Cash Inflow", line_color="#2ca02c", fill='tozeroy'))
    fig_monthly.add_trace(go.Scatter(x=months_axis, y=med_out, name="Outflow", line_color="#d62728", fill='tozeroy'))
    fig_monthly.update_layout(title="Monthly Cash Flow", xaxis_title="Month", yaxis_title="₹ Crores per month", height=500)
    st.plotly_chart(fig_monthly, use_container_width=True)

    # Chart 2: Cumulative + Net Cash + Gross Margin
    st.subheader("Cumulative View + Net Cash & Gross Margin %")
    cum_in = np.cumsum(med_cash_in)
    cum_out = np.cumsum(med_out)

    fig_cum = go.Figure()

    fig_cum.add_trace(go.Scatter(x=months_axis, y=cum_in, name="Cumulative Cash Inflow", line_color="#2ca02c", fill='tozeroy'))
    fig_cum.add_trace(go.Scatter(x=months_axis, y=cum_out, name="Cumulative Outflow", line_color="#d62728", fill='tozeroy'))
    fig_cum.add_trace(go.Scatter(x=months_axis, y=median_net, name="Net Cash Position", line_color="black", line_width=3, mode='lines'))

    # Gross Margin on secondary y-axis
    fig_cum.add_trace(go.Scatter(x=months_axis, y=median_gm, name="Gross Margin %", line=dict(color='purple', dash='dot'), yaxis="y2"))

    fig_cum.update_layout(
        title="Cumulative Cash + Net Position + Gross Margin %",
        xaxis_title="Month",
        yaxis_title="Cumulative ₹ Crores",
        yaxis2=dict(title="Gross Margin %", overlaying="y", side="right", range=[0, 100]),
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_cum, use_container_width=True)

    # Yearly table
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
            "Gross Margin %": round(gross_y / rev_del_y * 100, 1) if rev_del_y > 0 else 0,
            "Fixed + Service (₹ Cr)": round(fixed_opex_annual_cr + service_cost_annual_cr, 1),
            "Capex (₹ Cr)": round(capex_annual_cr, 1),
            "EBITDA approx (₹ Cr)": round(ebitda_y, 1)
        })

    st.dataframe(pd.DataFrame(yearly_rows), use_container_width=True, hide_index=True)

else:
    st.info("Adjust parameters in sidebar → click **Run Simulation**")

st.caption("Investor dashboard: runway, lowest cash, break-even, gross margin trend, cumulative net cash")
