import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# For XIRR — simple approximation since numpy-financial not available
def approximate_xirr(cashflows, dates=None):
    """Very rough monthly IRR approximation → annualized"""
    if len(cashflows) < 2 or sum(cashflows) <= 0:
        return 0.0
    try:
        from scipy.optimize import newton
        def npv(r):
            return sum(cf / (1 + r)**(t/12) for t, cf in enumerate(cashflows))
        monthly_irr = newton(npv, 0.01, tol=1e-6, maxiter=100)
        return ((1 + monthly_irr)**12 - 1) * 100
    except:
        return 0.0

st.set_page_config(page_title="Drone Financial Simulator", layout="wide")
st.title("🚁 Drone Startup Investor Finance Model (Annual Growth)")
st.markdown("**B2B Drone Hardware (AlgoX, AlgoBMS, AlgoPAD, AlgoDOCK)** — Annual growth version")

# ====================== SIDEBAR ======================
st.sidebar.header("Core Parameters")
col1, col2 = st.sidebar.columns(2)
with col1:
    initial_cash = st.number_input("Starting Cash (₹)", value=20_000_000, step=1_000_000, format="%d")
    fixed_annual = st.number_input("Annual Fixed Costs (₹)", value=20_000_000, step=500_000, format="%d")
    order_book = st.number_input("Order Book FY26-27 (₹)", value=170_000_000, step=1_000_000, format="%d")
    months = st.slider("Time Horizon (months)", 12, 60, 24)
    n_sims = st.slider("Simulations", 1000, 10000, 5000, step=1000)

with col2:
    unit_price = st.number_input("Avg Unit Price (₹)", value=500_000, step=10_000, format="%d")
    unit_cost = st.number_input("Base Manufacturing Cost (₹)", value=300_000, step=10_000, format="%d")

# Annual growth now
growth_base_annual = st.sidebar.slider("Base Annual Growth (%)", 0, 100, 40) / 100
growth_exp_annual = st.sidebar.slider("Expansion Annual Growth (%)", 0, 150, 70) / 100
geopol_prob = st.sidebar.slider("Geopolitical Shock Prob per month (%)", 0, 20, 5) / 100

enable_service = st.sidebar.checkbox("Enable AlgoDOCK Recurring Service", value=True)
service_annual_percent = st.sidebar.slider("Annual Service Fee (% of unit price)", 0, 30, 10)

# ====================== INVESTOR & ADVANCED ======================
with st.sidebar.expander("💰 Investment & Exit (Investor View)", expanded=True):
    investment_amount = st.number_input("Investment Amount (₹)", value=0, step=1_000_000, format="%d")
    investment_month = st.slider("Investment Month", 0, 60, 0)
    exit_multiple_ebitda = st.number_input("Exit Multiple on EBITDA", value=15.0, step=1.0)

with st.sidebar.expander("Advanced Finance Settings"):
    tax_rate = st.slider("Tax Rate (%)", 0, 40, 25) / 100
    learning_index = st.slider("Learning Curve Index (negative = cost ↓)", -0.40, 0.0, -0.15, step=0.01)
    wc_days = st.slider("Receivables Days", 0, 90, 45)
    capex_pct = st.slider("Capex % of Revenue", 0.0, 0.20, 0.05)
    monthly_noise_std = st.slider("Monthly Units Noise (± %)", 0, 30, 15) / 100

np.random.seed(42)

# ====================== CORE SIMULATION ======================
def run_simulation(annual_growth, extra_fixed_monthly=0, label=""):
    results = []
    cash_paths = []
    ebitda_paths = []

    total_years = (months + 11) // 12
    monthly_base_units = order_book / months / unit_price

    for _ in range(n_sims):
        cash = initial_cash
        cum_units = 0.0
        prev_receivables = 0.0
        cash_history = [cash]
        ebitda_history = []
        gross_margins = []
        net_profits = []
        fcfs_list = []

        annual_growth_factor = 1 + annual_growth

        for m in range(months):
            year = m // 12
            month_in_year = m % 12

            # Annual growth applied at start of each year
            if month_in_year == 0 and year > 0:
                annual_factor_this_year = annual_growth_factor ** year
            else:
                annual_factor_this_year = annual_growth_factor ** year

            # Base units this month, adjusted by annual trend + monthly noise + shock
            base_this_month = monthly_base_units * annual_factor_this_year
            noise = np.random.normal(0, monthly_noise_std)
            units = base_this_month * (1 + noise)
            if np.random.random() < geopol_prob:
                units *= (1 - 0.30)  # 30% demand shock

            units = max(units, 0)
            cum_units += units

            # Learning curve
            effective_cost = unit_cost * (cum_units ** learning_index) if cum_units > 0 else unit_cost

            revenue = units * unit_price
            cogs = units * effective_cost
            gross_profit = revenue - cogs
            gm = gross_profit / revenue if revenue > 0 else 0
            gross_margins.append(gm)

            # Service revenue on installed base
            service_rev = (cum_units * unit_price * service_annual_percent / 100 / 12) if enable_service else 0

            # EBITDA
            opex = fixed_annual / 12 + extra_fixed_monthly
            ebitda = gross_profit + service_rev - opex
            ebitda_history.append(ebitda)

            # Taxes
            taxes = max(0, ebitda * tax_rate)
            net_profit = ebitda - taxes
            net_profits.append(net_profit)

            # WC & Capex
            receivables = revenue * (wc_days / 365.0)
            delta_wc = receivables - prev_receivables
            prev_receivables = receivables
            capex = revenue * capex_pct

            # FCF
            fcf = ebitda - taxes - delta_wc - capex
            fcfs_list.append(fcf)

            # Investment
            if m == investment_month:
                cash += investment_amount

            cash += fcf
            cash = max(cash, 0)
            cash_history.append(cash)

        # Final metrics
        final_cash_cr = cash / 1e7
        final_ebitda_cr = ebitda / 1e7
        avg_gross_margin = np.mean(gross_margins) * 100 if gross_margins else 0
        cum_net_profit_cr = sum(net_profits) / 1e7
        cum_fcf_cr = sum(fcfs_list) / 1e7

        runway = next((i for i, c in enumerate(cash_history) if c <= 0), months + 1)
        survived = runway > months

        # Rough XIRR
        if investment_amount > 0:
            investor_cf = [-investment_amount if t == investment_month else 0 for t in range(months + 1)]
            investor_cf[-1] += ebitda * exit_multiple_ebitda  # terminal at end
            investor_cf[investment_month] -= investment_amount  # ensure correct sign
            xirr_pct = approximate_xirr(investor_cf)
        else:
            xirr_pct = 0.0

        results.append({
            "final_cash_cr": final_cash_cr,
            "runway": runway,
            "survived": survived,
            "avg_gross_margin": avg_gross_margin,
            "final_ebitda_cr": final_ebitda_cr,
            "cum_net_profit_cr": cum_net_profit_cr,
            "cum_fcf_cr": cum_fcf_cr,
            "investor_xirr_pct": xirr_pct
        })
        cash_paths.append([x/1e7 for x in cash_history])
        ebitda_paths.append([x/1e7 for x in ebitda_history])

    df = pd.DataFrame(results)
    median_cash = np.median(cash_paths, axis=0)
    p10_cash = np.percentile(cash_paths, 10, axis=0)
    p90_cash = np.percentile(cash_paths, 90, axis=0)
    median_ebitda = np.median(ebitda_paths, axis=0)

    return df, median_cash, p10_cash, p90_cash, median_ebitda

# ====================== RUN BUTTON ======================
if st.button("🚀 Run Simulations", type="primary", use_container_width=True):
    with st.spinner("Running Monte Carlo simulations..."):
        base_df, base_cash, base_p10, base_p90, base_ebitda = run_simulation(growth_base_annual, 0, "Base")
        exp_df, exp_cash, exp_p10, exp_p90, exp_ebitda = run_simulation(growth_exp_annual, (10_000_000 / 12), "Expansion")

    with st.expander("📐 Key Mathematical Formulas", expanded=False):
        st.latex(r"\text{Annual Growth Factor} = 1 + g_{\text{annual}}")
        st.latex(r"\text{Trend Units}_{m} = \text{Base Monthly} \times (\text{Annual Factor})^{\lfloor m/12 \rfloor}")
        st.latex(r"\text{Actual Units}_{m} = \text{Trend Units}_{m} \times (1 + \epsilon) \times (1 - s \cdot \mathbb{I}_{\text{shock}})")
        st.latex(r"\text{Unit Cost} = \text{Base Cost} \times (\text{Cumulative Units})^{b}")
        st.latex(r"\text{FCF}_t = \text{EBITDA}_t - \text{Tax} - \Delta\text{WC} - \text{Capex}")
        st.caption("XIRR approximated via root-finding on discounted cash flows")

    tab1, tab2, tab3 = st.tabs(["📊 Base Case", "📈 Expansion Case", "🔄 Comparison"])

    with tab1:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Avg Gross Margin", f"{base_df['avg_gross_margin'].median():.1f}%")
        c2.metric("Final EBITDA", f"₹{base_df['final_ebitda_cr'].median():.1f} Cr")
        c3.metric("Cum. Net Profit", f"₹{base_df['cum_net_profit_cr'].median():.1f} Cr")
        c4.metric("Ending Free Cash", f"₹{base_df['final_cash_cr'].median():.1f} Cr")
        c5.metric("Cum. FCF", f"₹{base_df['cum_fcf_cr'].median():.1f} Cr")
        c6.metric("Investor XIRR", f"{base_df['investor_xirr_pct'].median():.1f}%" if investment_amount > 0 else "N/A")

        fig_hist = px.histogram(base_df, x="final_cash_cr", nbins=50, title="Final Free Cash Distribution - Base")
        fig_hist.add_vline(x=base_df['final_cash_cr'].median(), line_color="red")
        st.plotly_chart(fig_hist, use_container_width=True)

    with tab2:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Avg Gross Margin", f"{exp_df['avg_gross_margin'].median():.1f}%")
        c2.metric("Final EBITDA", f"₹{exp_df['final_ebitda_cr'].median():.1f} Cr")
        c3.metric("Cum. Net Profit", f"₹{exp_df['cum_net_profit_cr'].median():.1f} Cr")
        c4.metric("Ending Free Cash", f"₹{exp_df['final_cash_cr'].median():.1f} Cr")
        c5.metric("Cum. FCF", f"₹{exp_df['cum_fcf_cr'].median():.1f} Cr")
        c6.metric("Investor XIRR", f"{exp_df['investor_xirr_pct'].median():.1f}%" if investment_amount > 0 else "N/A")

        fig_hist2 = px.histogram(exp_df, x="final_cash_cr", nbins=50, title="Final Free Cash Distribution - Expansion")
        fig_hist2.add_vline(x=exp_df['final_cash_cr'].median(), line_color="red")
        st.plotly_chart(fig_hist2, use_container_width=True)

    with tab3:
        months_axis = list(range(months + 1))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months_axis, y=base_cash, name="Base Cash (median)", line=dict(color="green")))
        fig.add_trace(go.Scatter(x=months_axis, y=exp_cash, name="Expansion Cash (median)", line=dict(color="purple")))
        fig.add_trace(go.Scatter(x=months_axis, y=base_ebitda, name="Base EBITDA", line=dict(color="green", dash="dot")))
        fig.add_trace(go.Scatter(x=months_axis, y=exp_ebitda, name="Expansion EBITDA", line=dict(color="purple", dash="dot")))
        fig.update_layout(title="Cash & EBITDA Trajectory (Median Paths)", xaxis_title="Months", yaxis_title="₹ Cr")
        st.plotly_chart(fig, use_container_width=True)

        csv_data = pd.concat([base_df.add_prefix("Base_"), exp_df.add_prefix("Exp_")], axis=1).to_csv(index=False)
        st.download_button("📥 Download Results CSV", csv_data, "drone_model_results.csv")

    st.success("Simulation complete. Annual growth makes the trajectory more realistic for hardware.")

else:
    st.info("Adjust parameters (especially annual growth rates) then click Run Simulations")

st.caption("Annual growth version | Investor-focused model for your drone startup")
