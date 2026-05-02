import streamlit as st
import pandas as pd
import subprocess
import os
import time
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Aivena | Full Network Analytics", layout="wide", page_icon="⚙️")

st.markdown("""
    <style>
    .stButton>button {width: 100%; height: 70px; font-size: 20px; font-weight: bold; background-color: #00CC96; color: white;}
    .stProgress > div > div > div > div { background-color: #00CC96; }
    </style>
""", unsafe_allow_html=True)

st.title("⚙️ Aivena Network Control Center")
st.markdown("Full-scale comparison: Legacy 48h 'Peak-Coverage' vs. AI 40h 'Demand-Driven' Optimization.")
st.divider()

if 'workflow_complete' not in st.session_state:
    st.session_state['workflow_complete'] = False

col_btn, col_empty = st.columns([1, 2])
with col_btn:
    start_workflow = st.button("🚀 Execute Full Network Optimization")

if start_workflow:
    st.session_state['workflow_complete'] = False 
    
    with st.status("Running Aivena Pipeline...", expanded=True) as status:
        try:
            st.write("📈 **Step 1:** Simulating Traffic Wave & 48h Manager Baseline...")
            subprocess.run(["python", "demand_gen.py"], check=True)
            subprocess.run(["python", "legacy_gen.py"], check=True)
            time.sleep(1)
            
            # STEP 2: AI OPTIMIZATION
            st.write("🧠 **Step 2:** Deep AI Optimization (12s per store)...")
            p_bar = st.progress(0)
            p_text = st.empty()
            
            process = subprocess.Popen(
                ["python", "-u", "solver_engine.py", 
                 "--input", "labor_demand_curve_sim.csv", 
                 "--output", "final_network_schedule.csv"], # <--- NEW NAME
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True
            )
            
            for line in iter(process.stdout.readline, ''):
                if "PROGRESS:" in line:
                    parts = line.strip().split(":")
                    if len(parts) >= 3:
                        fraction = parts[1].split("/")
                        current, total, store_id = int(fraction[0]), int(fraction[1]), parts[2]
                        p_bar.progress(current / total)
                        p_text.caption(f"✅ Optimized Store **{store_id}** ({current} of {total})")
            process.wait()
            
            st.write("📊 **Step 3:** Executing Comparative ROI Analysis...")
            subprocess.run(["python", "impact_analyzer.py", "--demand", "data/input/labor_demand_curve_sim.csv"], check=True)
            time.sleep(1)
            
            status.update(label="✅ Pipeline Complete", state="complete", expanded=False)
            st.session_state['workflow_complete'] = True
            
        except Exception as e:
            st.error(f"Critical error: {e}")
            st.stop()

st.divider()

# --- EXECUTIVE DASHBOARD ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OPT_DIAG = os.path.join(BASE_DIR, 'data', 'output', 'store_diagnostics_optimized.csv')
LEG_DIAG = os.path.join(BASE_DIR, 'data', 'output', 'store_diagnostics_legacy.csv')

if st.session_state.get('workflow_complete', False) and os.path.exists(OPT_DIAG):
    df_opt = pd.read_csv(OPT_DIAG)
    df_leg = pd.read_csv(LEG_DIAG)
    df_emp = pd.read_csv(os.path.join(BASE_DIR, 'data', 'output', 'employee_diagnostics_optimized.csv'))
    df_demand = pd.read_csv(os.path.join(BASE_DIR, 'data', 'input', 'labor_demand_curve_sim.csv'))

    opt_cost = df_opt['total_labor_cost_mxn'].sum()
    leg_cost = df_leg['total_labor_cost_mxn'].sum()
    savings_pct = ((leg_cost - opt_cost) / leg_cost) * 100 if leg_cost > 0 else 0
    leg_waste = df_leg['overstaffed'].sum()
    opt_waste = df_opt['overstaffed'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Optimized Total Cost", f"${opt_cost:,.0f} MXN", f"-{savings_pct:.2f}% Savings", delta_color="inverse")
    m2.metric("Authentic Legacy Baseline", f"${leg_cost:,.0f} MXN", "48h Manager Model")
    m3.metric("Network Utilization", f"{df_opt['labor_utilization_pct'].mean():.1f}%", f"+{df_opt['labor_utilization_pct'].mean() - df_leg['labor_utilization_pct'].mean():.1f}% vs Legacy")
    m4.metric("Strike Force Signal", f"{df_opt['understaffed'].sum():,.0f} Hrs", "Peak Service Gaps", delta_color="off")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        fig_waste = go.Figure(data=[
            go.Bar(name='Legacy (Wasted Hours)', x=['Payroll Waste'], y=[leg_waste], marker_color='#EF553B'),
            go.Bar(name='Aivena (Wasted Hours)', x=['Payroll Waste'], y=[opt_waste], marker_color='#00CC96')
        ])
        fig_waste.update_layout(title="Waste Comparison: Idle Payroll Hours", barmode='group', template='plotly_white')
        st.plotly_chart(fig_waste, use_container_width=True)

    with c2:
        wave_data = df_demand.groupby('hour')['required_staff'].sum().reset_index()
        fig_wave = px.area(wave_data, x='hour', y='required_staff', title="The Customer Wave (Total Network)", color_discrete_sequence=['#00CC96'], template='plotly_white')
        st.plotly_chart(fig_wave, use_container_width=True)

    st.subheader("📍 Full Network Performance Audit (50 Stores)")
    full_table = df_opt[['store_id', 'format', 'total_labor_cost_mxn', 'labor_utilization_pct', 'understaffed', 'overstaffed']].copy()
    full_table.columns = ['Store ID', 'Format', 'Payroll (MXN)', 'Efficiency %', 'Service Gap (Hrs)', 'Waste (Hrs)']
    st.dataframe(
        full_table.style.format({'Payroll (MXN)': '${:,.0f}', 'Efficiency %': '{:.1f}%', 'Service Gap (Hrs)': '{:,.0f}', 'Waste (Hrs)': '{:,.0f}'})
        .background_gradient(subset=['Efficiency %'], cmap='RdYlGn', vmin=60, vmax=100),
        use_container_width=True, height=450
    )

    st.divider()
    st.subheader("📥 Final Executive Deliverables")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.download_button("📂 Optimized Schedule", pd.read_csv('final_network_schedule.csv').to_csv(index=False), "final_network_schedule.csv", "text/csv")
    with d2:
        st.download_button("📊 Optimized Store Audit", df_opt.to_csv(index=False), "store_audit_optimized.csv", "text/csv")
    with d3:
        st.download_button("🧱 Legacy Store Audit", df_leg.to_csv(index=False), "store_audit_legacy.csv", "text/csv")
    with d4:
        st.download_button("⚖️ Compliance Ledger", df_emp.to_csv(index=False), "compliance_audit.csv", "text/csv")
else:
    st.info("Awaiting workflow execution to generate comparative ROI data.")