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

            cash += fcf
            cash = max(cash, 0)
            cash_history.append(cash / 1e7)

        final_cash_cr = cash / 1e7
        avg_gross_margin = ((total_rev - total_mfg) / total_rev * 100) if total_rev > 0 else 0
        final_ebitda_cr = ebitda / 1e7
        cum_fcf_cr = (cash - initial_cash_cr * 1e7) / 1e7   # cumulative FCF proxy

        results.append({
            "Ending Cash (₹ Cr)": final_cash_cr,
            "Avg Gross Margin %": avg_gross_margin,
            "Final EBITDA (₹ Cr)": final_ebitda_cr,
            "Cum. FCF (₹ Cr)": cum_fcf_cr,
            "Survived": final_cash_cr > 0
        })

        cash_paths.append(cash_history)

    df = pd.DataFrame(results)
    median_path = np.median(cash_paths, axis=0)
    p10_path = np.percentile(cash_paths, 10, axis=0)
    p90_path = np.percentile(cash_paths, 90, axis=0)

    return df, median_path, p10_path, p90_path

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("Run Simulation", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo..."):
        df, median_cash, p10_cash, p90_cash = run_simulation()

    st.subheader("Core Investor Metrics (Median outcome)")

    cols = st.columns(5)
    cols[0].metric("Ending Cash", f"₹{df['Ending Cash (₹ Cr)'].median():.1f} Cr")
    cols[1].metric("Avg Gross Margin", f"{df['Avg Gross Margin %'].median():.1f}%")
    cols[2].metric("Final EBITDA", f"₹{df['Final EBITDA (₹ Cr)'].median():.1f} Cr")
    cols[3].metric("Cumulative FCF", f"₹{df['Cum. FCF (₹ Cr)'].median():.1f} Cr")
    cols[4].metric("Survival Probability", f"{df['Survived'].mean():.0%}")

    # Charts
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig_hist = px.histogram(
            df, x="Ending Cash (₹ Cr)", nbins=40,
            title="Distribution of Ending Cash Position",
            labels={"Ending Cash (₹ Cr)": "Ending Cash (₹ Cr)"}
        )
        fig_hist.add_vline(x=df['Ending Cash (₹ Cr)'].median(), line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_chart2:
        fig_path = go.Figure()
        months_axis = list(range(months + 1))
        fig_path.add_trace(go.Scatter(x=months_axis, y=median_cash, name="Median Cash", line_color="#2ca02c"))
        fig_path.add_trace(go.Scatter(x=months_axis, y=p10_cash, name="10th %ile", line_color="#ff7f0e", line_dash="dot"))
        fig_path.add_trace(go.Scatter(x=months_axis, y=p90_cash, name="90th %ile", line_color="#1f77b4", line_dash="dot", fill='tonexty'))
        fig_path.update_layout(
            title="Cash Balance Trajectory (with 10–90% range)",
            xaxis_title="Months",
            yaxis_title="Cash (₹ Cr)"
        )
        st.plotly_chart(fig_path, use_container_width=True)

    with st.expander("How the model calculates revenue & expenses"):
        st.markdown("""
        **Revenue per month** = Σ over products (actual units sold × selling price)  
        **Manufacturing expense per month** = Σ over products (actual units sold × mfg cost per unit)  
        **Gross profit** = Revenue − Manufacturing expense  
        **EBITDA** = Gross profit − Fixed OpEx/12 − Service cost/12  
        **FCF (simplified)** = EBITDA − estimated tax − monthly capex portion  
        Growth is applied annually per product; monthly volume has realistic noise.
        """)

else:
    st.info("Adjust product parameters or company assumptions in the sidebar, then click **Run Simulation**.")

st.caption("Simplified core model — Bengaluru drone hardware startup — March 2026")
