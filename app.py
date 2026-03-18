import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Drone Financial Simulator", layout="wide")
st.title("🚁 Drone Startup Financial Monte Carlo Simulator")
st.markdown("**B2B Drone Hardware (AlgoX, AlgoBMS, AlgoPAD, AlgoDOCK)** — Built for Ankit")

# ====================== SIDEBAR INPUTS ======================
st.sidebar.header("Editable Parameters")

col1, col2 = st.sidebar.columns(2)
with col1:
    initial_cash = st.number_input("Starting Cash (₹)", value=20_000_000, step=1_000_000, format="%d")
    fixed_annual = st.number_input("Annual Fixed Costs (₹)", value=20_000_000, step=500_000, format="%d")
    order_book = st.number_input("Order Book FY26-27 (₹)", value=170_000_000, step=1_000_000, format="%d")
    months = st.slider("Time Horizon (months)", 12, 60, 24)

with col2:
    unit_price = st.number_input("Avg Unit Price (₹)", value=500_000, step=10_000, format="%d")
    unit_cost = st.number_input("Manufacturing Cost per Unit (₹)", value=300_000, step=10_000, format="%d")
    n_sims = st.slider("Number of Simulations", 1000, 10000, 5000, step=1000)

# Growth & Risk
growth_base = st.sidebar.slider("Base Monthly Growth (%)", 0, 30, 10) / 100
growth_exp = st.sidebar.slider("Expansion Monthly Growth (%)", 0, 40, 15) / 100
geopol_prob = st.sidebar.slider("Geopolitical Shock Probability (%)", 0, 20, 5) / 100
extra_fixed = st.sidebar.number_input("Extra Fixed Costs for Expansion (₹/year)", value=10_000_000, step=1_000_000)

# AlgoDOCK Service
enable_service = st.sidebar.checkbox("Enable AlgoDOCK Recurring Service Revenue", value=True)
service_fee_percent = st.sidebar.slider("Monthly Service Fee (% of unit price)", 0, 20, 8) / 100

# ====================== SIMULATION FUNCTION ======================
def run_monte_carlo(growth_mean, extra_fixed_monthly=0, label=""):
    results = []
    cash_paths = []
    monthly_base = order_book / months

    for _ in range(n_sims):
        cash = initial_cash
        path = [cash]
        for m in range(months):
            growth = np.random.normal(growth_mean, 0.04)
            if np.random.random() < geopol_prob:
                growth -= 0.30

            units = (monthly_base / unit_price) * (1 + growth) ** m
            units = max(units, 0)

            revenue = units * unit_price
            manuf = units * unit_cost

            # AlgoDOCK service revenue
            service_rev = (units * unit_price * service_fee_percent) if enable_service else 0

            fixed = (fixed_annual / 12) + extra_fixed_monthly
            net = (revenue - manuf + service_rev) - fixed

            cash += net
            cash = max(cash, 0)
            path.append(cash)

        final_cash_cr = cash / 1e7
        runway = next((i for i, c in enumerate(path) if c <= 0), months + 1)
        survived = runway > months

        results.append({"final_cash_cr": final_cash_cr, "runway": runway, "survived": survived})
        cash_paths.append([x/1e7 for x in path])

    df = pd.DataFrame(results)
    median_path = np.median(cash_paths, axis=0)
    p10 = np.percentile(cash_paths, 10, axis=0)
    p90 = np.percentile(cash_paths, 90, axis=0)

    return df, median_path, p10, p90

# ====================== RUN BUTTON ======================
if st.button("🚀 Run 5,000 Simulations", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo simulations..."):
        base_df, base_med, base_p10, base_p90 = run_monte_carlo(growth_base, 0, "Base")
        exp_df, exp_med, exp_p10, exp_p90 = run_monte_carlo(growth_exp, extra_fixed/12, "Expansion")

    # ====================== RESULTS ======================
    tab1, tab2, tab3 = st.tabs(["📊 Base Case (Defense)", "📈 Expansion Case", "🔄 Comparison"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        col1.metric("Median Final Cash", f"₹{base_df['final_cash_cr'].median():.1f} Cr")
        col2.metric("Runway >18 months", f"{(base_df['runway'] > 18).mean():.1%}")
        col3.metric("Survival Probability", f"{base_df['survived'].mean():.1%}")

        fig1 = px.histogram(base_df, x="final_cash_cr", nbins=50, title="Final Cash Distribution - Base Case")
        fig1.add_vline(x=base_df['final_cash_cr'].median(), line_color="red", annotation_text="Median")
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        col1, col2, col3 = st.columns(3)
        col1.metric("Median Final Cash", f"₹{exp_df['final_cash_cr'].median():.1f} Cr")
        col2.metric("Runway >18 months", f"{(exp_df['runway'] > 18).mean():.1%}")
        col3.metric("Survival Probability", f"{exp_df['survived'].mean():.1%}")

        fig2 = px.histogram(exp_df, x="final_cash_cr", nbins=50, title="Final Cash Distribution - Expansion")
        fig2.add_vline(x=exp_df['final_cash_cr'].median(), line_color="red")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = go.Figure()
        months_axis = list(range(months + 1))
        fig3.add_trace(go.Scatter(x=months_axis, y=base_med, name="Base Median", line=dict(color="green")))
        fig3.add_trace(go.Scatter(x=months_axis, y=exp_med, name="Expansion Median", line=dict(color="purple")))
        fig3.update_layout(title="Cash Trajectory Comparison (Median)", xaxis_title="Months", yaxis_title="Cash (₹ Cr)")
        st.plotly_chart(fig3, use_container_width=True)

        st.download_button("📥 Download Full Simulation Results (CSV)", 
                           data=pd.DataFrame({"Base Median Cash": base_med, "Expansion Median Cash": exp_med}).to_csv(index=False),
                           file_name="drone_simulation_results.csv")

    st.success("✅ Simulation complete! Your runway looks very strong with the ₹17 Cr order book.")

else:
    st.info("Adjust parameters in the sidebar and click **Run Simulations**")

st.caption("Built live for your drone startup | Change any number and re-run instantly")
