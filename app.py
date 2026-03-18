import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Model", layout="wide")
st.title("🚁 Drone Hardware Startup — Core Financial Simulator")
st.markdown("Investor-focused | Product-level lead-time delay | Revenue vs Outflow view")

# ────────────────────────────────────────────────
# SIDEBAR – Product table with lead-time
# ────────────────────────────────────────────────
st.sidebar.header("Product Parameters (FY26-27 committed units)")

default_products = pd.DataFrame({
    "Product": ["AlgoX", "AlgoBMS", "AlgoPAD", "AlgoDOCK"],
    "Selling Price (₹)": [1000000, 500000, 300000, 800000],
    "Committed Units FY26-27": [4000, 10000, 15000, 5000],
    "Manufacturing Cost per unit (₹)": [550000, 280000, 170000, 450000],
    "Annual Sales Growth %": [35, 40, 30, 50],
    "Lead-time (months)": [3, 2, 4, 6]   # NEW column
})

products = st.sidebar.data_editor(
    default_products,
    num_rows="fixed",
    use_container_width=True,
    column_config={
        "Selling Price (₹)": st.column_config.NumberColumn(format="%d", min_value=0),
        "Committed Units FY26-27": st.column_config.NumberColumn(format="%d", min_value=0),
        "Manufacturing Cost per unit (₹)": st.column_config.NumberColumn(format="%d", min_value=0),
        "Annual Sales Growth %": st.column_config.NumberColumn(format="%d", min_value=0, max_value=200),
        "Lead-time (months)": st.column_config.NumberColumn(format="%d", min_value=0, max_value=24)
    }
)

# Auto-calculated base year totals (for display only)
products["Revenue FY26-27 (₹ Cr)"] = (products["Selling Price (₹)"] * products["Committed Units FY26-27"]) / 1e7
products["Manufacturing Expense FY26-27 (₹ Cr)"] = (products["Manufacturing Cost per unit (₹)"] * products["Committed Units FY26-27"]) / 1e7

st.sidebar.metric("Total Committed Revenue FY26-27", f"₹{products['Revenue FY26-27 (₹ Cr)'].sum():.1f} Cr")
st.sidebar.metric("Total Committed Mfg Expense FY26-27", f"₹{products['Manufacturing Expense FY26-27 (₹ Cr)'].sum():.1f} Cr")

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

    # Pre-compute monthly committed inflow per product (spread over 12 months)
    products["Monthly Committed Units"] = products["Committed Units FY26-27"] / 12

    for _ in range(n_simulations):
        cash = initial_cash_cr * 1e7
        revenue_this_run = [0.0] * months
        outflow_this_run = [0.0] * months

        for m in range(months):
            year = m // 12
            rev_month = 0.0
            mfg_month = 0.0

            for _, row in products.iterrows():
                lt = int(row["Lead-time (months)"])

                # Only products with lead-time already passed can deliver this month
                if m >= lt:
                    # How much backlog becomes deliverable this month
                    # Simple model: spread original committed units after lead-time
                    monthly_deliverable = row["Monthly Committed Units"] * (1 + row["Annual Sales Growth %"]/100) ** year
                    monthly_deliverable *= np.random.normal(1.0, monthly_noise_pct / 100.0)
                    monthly_deliverable = max(0, monthly_deliverable)

                    rev = monthly_deliverable * row["Selling Price (₹)"]
                    mfg = monthly_deliverable * row["Manufacturing Cost per unit (₹)"]

                    rev_month += rev
                    mfg_month += mfg

            # Fixed costs (OpEx + Service)
            monthly_fixed = (fixed_opex_annual_cr + service_cost_annual_cr) * 1e7 / 12

            # Capex
            monthly_capex = capex_annual_cr * 1e7 / 12

            # Total outflow this month
            total_outflow = mfg_month + monthly_fixed + monthly_capex

            # EBITDA ≈ Gross profit - fixed
            gross = rev_month - mfg_month
            ebitda = gross - monthly_fixed

            # Simplified tax
            tax = max(0, ebitda * 0.25)
            nopat = ebitda - tax

            # Free cash flow ≈ nopat - capex
            fcf = nopat - monthly_capex

            cash += fcf
            cash = max(cash, 0)

            revenue_this_run[m] = rev_month / 1e7
            outflow_this_run[m] = total_outflow / 1e7

        revenue_paths.append(revenue_this_run)
        outflow_paths.append(outflow_this_run)
        ending_cash_list.append(cash / 1e7)

    # Median paths
    median_rev = np.median(revenue_paths, axis=0)
    median_out = np.median(outflow_paths, axis=0)
    median_ending_cash = np.median(ending_cash_list)

    return median_rev, median_out, median_ending_cash

# ────────────────────────────────────────────────
# RUN BUTTON & OUTPUT
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo simulation..."):
        median_revenue, median_outflow, median_cash = run_simulation()

    # ── KEY METRICS ──
    st.subheader("Summary Results (median outcome)")
    cols = st.columns(4)
    cols[0].metric("Ending Cash", f"₹{median_cash:.1f} Cr")
    cols[1].metric("Avg Monthly Revenue (later months)", f"₹{np.mean(median_revenue[-6:]):.1f} Cr")
    cols[2].metric("Avg Monthly Outflow", f"₹{np.mean(median_outflow):.1f} Cr")
    cols[3].metric("Peak Monthly Burn", f"₹{max(median_outflow - median_revenue):.1f} Cr" if max(median_outflow - median_revenue) > 0 else "Positive")

    # ── MAIN CHART ──
    st.subheader("Monthly Revenue vs Total Outflow (incl. Capex)")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(range(months)),
        y=median_revenue,
        name="Revenue",
        line_color="#2ca02c",
        fill='tozeroy',
        fillcolor='rgba(44,160,44,0.18)'
    ))

    fig.add_trace(go.Scatter(
        x=list(range(months)),
        y=median_outflow,
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

    with st.expander("How revenue and costs are timed"):
        st.markdown("""
        - Committed units are spread evenly across the 12 months of each year.
        - Revenue and manufacturing cost are only recognized **after the lead-time** for each product.
        - This creates realistic cash lag: early months often show high fixed + capex outflow with little/no revenue.
        - Monthly volume noise adds variability around the trend.
        - Capex is spread evenly each month (annual amount / 12).
        """)

else:
    st.info("Adjust the product table (especially lead-times) and company assumptions, then click **Run Simulation**.")

st.caption("Updated model — lead-time delay + Revenue vs Outflow chart | Bengaluru drone startup — 2026")
