import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Monthly capacity × price model | Monthly growth on capacity | Persistent inputs")

# ────────────────────────────────────────────────
# Initialize session state for persistent product table
# ────────────────────────────────────────────────
if 'products' not in st.session_state:
    st.session_state.products = pd.DataFrame({
        "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
        "Selling Price (₹)": [35000, 8000, 350000, 800000],
        "Manufacturing Cost per unit (₹)": [20000, 3500, 200000, 400000],
        "Monthly Manufacturing Capacity (units)": [400, 300, 10, 2],
        "Monthly Growth Rate %": [2.5, 3.0, 2.2, 3.5]
    })

# ────────────────────────────────────────────────
# SIDEBAR
# ────────────────────────────────────────────────
st.sidebar.header("Product Parameters")

edited_df = st.sidebar.data_editor(
    st.session_state.products,
    num_rows="fixed",
    use_container_width=True,
    key="product_editor",
    column_config={
        "Selling Price (₹)": st.column_config.NumberColumn(format="%d", min_value=0),
        "Manufacturing Cost per unit (₹)": st.column_config.NumberColumn(format="%d", min_value=0),
        "Monthly Manufacturing Capacity (units)": st.column_config.NumberColumn(format="%d", min_value=1, step=10),
        "Monthly Growth Rate %": st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=20.0, step=0.1)
    }
)

# Save back to session state only when changed
if not edited_df.equals(st.session_state.products):
    st.session_state.products = edited_df.copy()

products = st.session_state.products

# Company-wide inputs
st.sidebar.header("Company-wide Assumptions")
initial_cash_cr = st.sidebar.number_input("Starting Cash (₹ Cr)", value=2.0, step=0.5, min_value=0.0)
fixed_opex_annual_cr = st.sidebar.number_input("Annual Fixed OpEx (₹ Cr)", value=2.0, step=0.2, min_value=0.0)
service_cost_annual_cr = st.sidebar.number_input("Annual Product Service Cost (₹ Cr)", value=0.8, step=0.1, min_value=0.0)
capex_annual_cr = st.sidebar.number_input("Annual Capex (₹ Cr)", value=1.5, step=0.5, min_value=0.0)

months = st.sidebar.slider("Forecast Horizon (months)", 12, 60, 24)
n_simulations = st.sidebar.slider("Monte Carlo Runs", 1000, 5000, 2000, step=500)
monthly_noise_pct = st.sidebar.slider("Monthly Volume Noise ±%", 0, 35, 12)

# ────────────────────────────────────────────────
# SIMULATION
# ────────────────────────────────────────────────
def run_simulation():
    revenue_paths = []
    outflow_paths = []
    ending_cash_list = []

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        revenue_run = [0.0] * months
        outflow_run = [0.0] * months

        # Current capacity starts at initial value
        capacities = products["Monthly Manufacturing Capacity (units)"].values.copy()

        for m in range(months):
            rev_month = 0.0
            mfg_month = 0.0

            for i, row in products.iterrows():
                # Apply monthly growth to capacity
                if m > 0:
                    capacities[i] *= (1 + row["Monthly Growth Rate %"] / 100)

                # Apply noise around current capacity
                units = capacities[i] * np.random.normal(1.0, monthly_noise_pct / 100.0)
                units = max(0, units)

                rev = units * row["Selling Price (₹)"]
                mfg = units * row["Manufacturing Cost per unit (₹)"]

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
    with st.spinner("Running Monte Carlo simulation..."):
        median_rev, median_out, median_cash, all_rev_paths, all_out_paths = run_simulation()

    # Summary
    st.subheader("Summary Results (median outcome)")
    cols = st.columns(4)
    cols[0].metric("Ending Cash", f"₹{median_cash:.1f} Cr")
    cols[1].metric("Avg Monthly Revenue (last 6 mo)", f"₹{np.mean(median_rev[-6:]):.1f} Cr")
    cols[2].metric("Avg Monthly Outflow", f"₹{np.mean(median_out):.1f} Cr")
    cols[3].metric("Peak Monthly Burn", f"₹{max(median_out - median_rev):.1f} Cr" if max(median_out - median_rev) > 0 else "Positive")

    # Main chart
    st.subheader("Monthly Revenue vs Total Outflow (incl. Capex)")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(range(months)),
        y=median_rev,
        name="Revenue",
        line_color="#2ca02c",
        fill='tozeroy',
        fillcolor='rgba(44,160,44,0.18)'
    ))

    fig.add_trace(go.Scatter(
        x=list(range(months)),
        y=median_out,
        name="Expenses + Capex",
        line_color="#d62728",
        fill='tozeroy',
        fillcolor='rgba(214,39,40,0.18)'
    ))

    fig.update_layout(
        title="Revenue vs Total Costs (incl. Capex) — Median Path",
        xaxis_title="Month",
        yaxis_title="₹ Crores per month",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=550
    )

    st.plotly_chart(fig, use_container_width=True)

    # Yearly financial summary table
    st.subheader("Yearly Financial Summary (median values)")

    years = []
    yearly_data = []

    for y in range((months + 11) // 12):
        start_m = y * 12
        end_m = min(start_m + 12, months)

        rev_y = np.sum([np.sum(path[start_m:end_m]) for path in all_rev_paths]) / n_simulations
        out_y = np.sum([np.sum(path[start_m:end_m]) for path in all_out_paths]) / n_simulations
        gross_y = rev_y - (out_y - (fixed_opex_annual_cr + service_cost_annual_cr + capex_annual_cr))
        ebitda_y = gross_y - (fixed_opex_annual_cr + service_cost_annual_cr)

        fy_label = f"FY {26+y}-{27+y}" if y < 2 else f"FY {26+y}-{27+y}"

        yearly_data.append({
            "Fiscal Year": fy_label,
            "Revenue (₹ Cr)": round(rev_y, 1),
            "Manufacturing Expense (₹ Cr)": round(rev_y - gross_y, 1),
            "Gross Profit (₹ Cr)": round(gross_y, 1),
            "Fixed + Service Cost (₹ Cr)": round(fixed_opex_annual_cr + service_cost_annual_cr, 1),
            "Capex (₹ Cr)": round(capex_annual_cr, 1),
            "EBITDA approx (₹ Cr)": round(ebitda_y, 1)
        })

    yearly_df = pd.DataFrame(yearly_data)
    st.dataframe(yearly_df.style.format({
        col: "{:.1f}" for col in yearly_df.columns if col != "Fiscal Year"
    }), use_container_width=True, hide_index=True)

    with st.expander("Model logic notes"):
        st.markdown("""
        - Monthly revenue per product = current capacity × selling price  
        - Capacity compounds monthly: capacityₜ = capacityₜ₋₁ × (1 + monthly growth %)  
        - Noise is applied around current capacity  
        - Revenue & manufacturing cost recognized same month (no lead-time delay)  
        - Fixed OpEx + Service + Capex spread evenly every month  
        """)

else:
    st.info("Edit product table or assumptions → click **Run Simulation**")

st.caption("Model updated: monthly capacity × price | capacity grows monthly | inputs persist across reruns")
