import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Simple XIRR approximation (no external lib needed)
def approx_xirr(cashflows):
    if len(cashflows) < 2 or sum(cashflows) <= 0:
        return 0.0
    # Very basic Newton-style IRR finder (monthly)
    def npv(r):
        return sum(cf / (1 + r)**(t/12.0) for t, cf in enumerate(cashflows))
    try:
        r = 0.01
        for _ in range(50):
            npv_val = npv(r)
            deriv = sum(-cf * (t/12.0) / (1 + r)**((t/12.0)+1) for t, cf in enumerate(cashflows) if cf != 0)
            if abs(deriv) < 1e-10:
                break
            r -= npv_val / deriv if deriv != 0 else 0
        return ((1 + r)**12 - 1) * 100
    except:
        return 0.0

st.set_page_config(page_title="Drone Investor Simulator", layout="wide")
st.title("🚁 Drone Hardware Startup — Investor Monte Carlo Simulator")
st.markdown("Order-book driven | Annual growth | Learning curve | Service ramp | XIRR focus")

# ────────────────────────────────────────────────
# SIDEBAR – Clean & Grouped
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("🎛️ Assumptions")

    st.subheader("Starting Point")
    initial_cash = st.number_input("Starting Cash (₹ Cr)", value=2.0, step=0.5, format="%.1f") * 1e7
    fixed_annual = st.number_input("Annual Fixed OpEx (₹ Cr)", value=2.0, step=0.2, format="%.1f") * 1e7
    order_book_cr = st.number_input("Order Book FY26-27 (₹ Cr)", value=17.0, step=1.0, format="%.1f")
    order_book = order_book_cr * 1e7

    st.subheader("Time & Runs")
    months = st.slider("Forecast Horizon (months)", 12, 60, 24)
    n_sims = st.slider("Monte Carlo Runs", 1000, 10000, 5000, step=1000)

    st.subheader("Unit Economics")
    unit_price = st.number_input("Avg Selling Price per Unit (₹)", value=500000, step=10000)
    unit_cost_base = st.number_input("Base Mfg Cost per Unit (₹)", value=300000, step=10000)

    st.subheader("Growth & Risk")
    growth_base_annual = st.slider("Base Annual Growth %", 0, 100, 40) / 100
    growth_exp_annual = st.slider("Expansion Annual Growth %", 0, 150, 70) / 100
    geopol_monthly_prob = st.slider("Geopolitical Shock Prob (per month) %", 0, 20, 5) / 100
    monthly_noise = st.slider("Monthly Demand Noise ±%", 0, 40, 15) / 100

    enable_service = st.checkbox("AlgoDOCK Recurring Service Revenue", value=True)
    service_annual_pct = st.slider("Annual Service Fee (% of hardware price)", 0, 30, 10)

with st.sidebar.expander("💼 Investor & Advanced", expanded=True):
    investment_cr = st.number_input("New Investment (₹ Cr)", value=0.0, step=1.0) * 1e7
    investment_month = st.slider("Investment Received in Month", 0, 60, 0)
    exit_ebitda_multiple = st.number_input("Exit Multiple (× Final EBITDA)", value=15.0, step=1.0, min_value=5.0)

    tax_rate = st.slider("Corporate Tax Rate %", 0, 40, 25) / 100
    learning_b = st.slider("Learning Curve Exponent (negative = cost reduction)", -0.5, 0.0, -0.15, step=0.01)
    wc_days = st.slider("Receivables Collection Days", 0, 120, 60)
    capex_pct_rev = st.slider("Capex as % of Revenue", 0.0, 0.30, 0.08)

# ────────────────────────────────────────────────
# SIMULATION ENGINE
# ────────────────────────────────────────────────
def run_mc(g_annual, extra_opex_monthly=0, label=""):
    results = []
    cash_paths = []
    ebitda_paths = []

    monthly_base_rev = order_book / months
    monthly_base_units = monthly_base_rev / unit_price

    for _ in range(n_sims):
        cash = initial_cash
        cum_units = 0
        receivables_prev = 0
        cash_hist = [cash / 1e7]
        ebitda_hist = []

        for m in range(months):
            yr = m // 12
            annual_trend = (1 + g_annual) ** yr

            trend_units = monthly_base_units * annual_trend
            noise_factor = np.random.normal(1.0, monthly_noise)
            units = trend_units * noise_factor
            if np.random.random() < geopol_monthly_prob:
                units *= 0.70  # -30% shock

            units = max(0, units)
            cum_units += units

            # Learning curve on cost
            cost_eff = unit_cost_base * (cum_units ** learning_b) if cum_units > 0 else unit_cost_base

            rev = units * unit_price
            cogs = units * cost_eff
            gross = rev - cogs
            gm_pct = (gross / rev * 100) if rev > 0 else 0

            serv_rev = (cum_units * unit_price * service_annual_pct / 100 / 12) if enable_service else 0

            opex = (fixed_annual / 12) + extra_opex_monthly
            ebitda = gross + serv_rev - opex
            ebitda_hist.append(ebitda / 1e7)

            tax = max(0, ebitda * tax_rate)
            nopat = ebitda - tax

            # WC change
            recv = rev * (wc_days / 365)
            dwc = recv - receivables_prev
            receivables_prev = recv

            capex = rev * capex_pct_rev

            fcf = ebitda - tax - dwc - capex

            # Investment inflow
            if m == investment_month:
                cash += investment_cr

            cash += fcf
            cash = max(cash, 0)
            cash_hist.append(cash / 1e7)

        final_cash_cr = cash / 1e7
        final_ebitda_cr = ebitda / 1e7
        avg_gm = np.mean([g for g in [gm_pct] if g > 0]) if any(g > 0 for g in [gm_pct]) else 0
        cum_profit_cr = sum(nopat for nopat in [nopat]) / 1e7   # simplistic cum; improve if needed
        cum_fcf_cr = sum(fcf for fcf in [fcf]) / 1e7

        # Investor XIRR
        if investment_cr > 0:
            cf_list = [0] * (months + 1)
            cf_list[investment_month] = -investment_cr / 1e7
            cf_list[-1] += final_ebitda_cr * exit_ebitda_multiple
            xirr = approx_xirr(cf_list)
        else:
            xirr = 0.0

        results.append({
            'Final Free Cash (₹ Cr)': final_cash_cr,
            'Avg Gross Margin %': avg_gm,
            'Final EBITDA (₹ Cr)': final_ebitda_cr,
            'Cum Net Profit (₹ Cr)': cum_profit_cr,
            'Cum FCF (₹ Cr)': cum_fcf_cr,
            'Investor XIRR %': xirr,
            'Survived': cash_hist[-1] > 0
        })

        cash_paths.append(cash_hist)
        ebitda_paths.append(ebitda_hist)

    df = pd.DataFrame(results)
    median_cash = np.median(cash_paths, axis=0)
    p10_cash = np.percentile(cash_paths, 10, axis=0)
    p90_cash = np.percentile(cash_paths, 90, axis=0)
    median_ebitda = np.median(ebitda_paths, axis=0)

    return df, median_cash, p10_cash, p90_cash, median_ebitda

# ────────────────────────────────────────────────
# RUN & DISPLAY
# ────────────────────────────────────────────────
if st.button("▶️ Run Monte Carlo Simulation", type="primary", use_container_width=True):
    with st.spinner("Simulating 5,000 futures..."):
        base_df, base_cash, base_p10, base_p90, base_ebitda = run_mc(growth_base_annual, 0)
        exp_df, exp_cash, exp_p10, exp_p90, exp_ebitda = run_mc(growth_exp_annual, 8333333)  # ~₹1 Cr/yr extra

    # Formulas
    with st.expander("📐 Model Formulas & Logic"):
        st.markdown("""
        - **Annual Trend** → Units_m = Base × (1 + g)^⌊m/12⌋  
        - **Actual Units** → Trend × (1 + noise) × (shock if triggered)  
        - **Cost Learning** → C_eff = C_base × (Cum Units)^b  
        - **EBITDA** → Gross + Service - OpEx  
        - **FCF** → EBITDA - Tax - ΔWC - Capex  
        - **XIRR** → Annualized IRR on investment outflow + terminal (EBITDA × multiple)
        """)

    # ── Dashboard ──
    st.subheader("Key Investor Metrics (Median across simulations)")

    cols = st.columns(6)
    cols[0].metric("Avg Gross Margin", f"{base_df['Avg Gross Margin %'].median():.1f}%", delta=None)
    cols[1].metric("Final EBITDA", f"₹{base_df['Final EBITDA (₹ Cr)'].median():.1f} Cr")
    cols[2].metric("Cum. FCF", f"₹{base_df['Cum FCF (₹ Cr)'].median():.1f} Cr")
    cols[3].metric("Ending Cash", f"₹{base_df['Final Free Cash (₹ Cr)'].median():.1f} Cr")
    cols[4].metric("Survival Prob", f"{base_df['Survived'].mean():.0%}")
    cols[5].metric("XIRR (with investment)", f"{base_df['Investor XIRR %'].median():.1f}%" if investment_cr > 0 else "—")

    tab_base, tab_exp, tab_compare = st.tabs(["Base Case (Defense Focus)", "Expansion Case", "Side-by-Side Comparison"])

    with tab_base:
        st.plotly_chart(
            px.histogram(base_df, x="Final Free Cash (₹ Cr)", nbins=50, title="Distribution — Ending Free Cash (Base Case)")
            .add_vline(x=base_df['Final Free Cash (₹ Cr)'].median(), line_dash="dash", line_color="red"),
            use_container_width=True
        )

    with tab_exp:
        st.plotly_chart(
            px.histogram(exp_df, x="Final Free Cash (₹ Cr)", nbins=50, title="Distribution — Ending Free Cash (Expansion)")
            .add_vline(x=exp_df['Final Free Cash (₹ Cr)'].median(), line_dash="dash", line_color="red"),
            use_container_width=True
        )

    with tab_compare:
        fig = go.Figure()
        m_ax = list(range(months + 1))
        fig.add_traces([
            go.Scatter(x=m_ax, y=base_cash, name="Base Median Cash", line_color="green"),
            go.Scatter(x=m_ax, y=exp_cash, name="Expansion Median Cash", line_color="purple"),
            go.Scatter(x=m_ax, y=base_p10, name="Base 10th %ile", line_color="green", line_dash="dot", opacity=0.4),
            go.Scatter(x=m_ax, y=base_p90, name="Base 90th %ile", line_color="green", line_dash="dot", opacity=0.4, fill='tonexty'),
            go.Scatter(x=m_ax, y=exp_p10, name="Exp 10th %ile", line_color="purple", line_dash="dot", opacity=0.4),
            go.Scatter(x=m_ax, y=exp_p90, name="Exp 90th %ile", line_color="purple", line_dash="dot", opacity=0.4, fill='tonexty'),
        ])
        fig.update_layout(title="Cash Balance Trajectories (with uncertainty bands)", xaxis_title="Months", yaxis_title="₹ Cr")
        st.plotly_chart(fig, use_container_width=True)

    st.download_button(
        "Download Full Results CSV",
        pd.concat([base_df.add_prefix("Base_"), exp_df.add_prefix("Exp_")], axis=1).to_csv(index=False),
        "drone-sim-results.csv"
    )

else:
    st.info("Tweak assumptions in the sidebar → click **Run Monte Carlo Simulation** to see probabilistic outcomes.")

st.caption("Inspired by clean interactive sim UIs | Tailored for your Bengaluru drone startup | 2026 context")
