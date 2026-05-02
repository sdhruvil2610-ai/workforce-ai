import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Workforce AI | Latin Leap MVP", layout="wide", page_icon="🚀")

st.title("🚀 Workforce AI: 40-Hour Transition Engine")
st.markdown("### Executive Dashboard: Phase I (Legacy) vs. Phase II (AI-Optimized)")
st.markdown("Automated transition from rigid 48-hour schedules to demand-driven 40-hour compliance.")

# --- 2. DATA LOADING ENGINE ---
@st.cache_data
def load_dashboard_data():
    try:
        # Load Phase I (Legacy 48h) Diagnostics
        df_store_p1 = pd.read_csv('data/output/store_level_diagnostics.csv')
        df_emp_p1 = pd.read_csv('data/output/employee_level_diagnostics.csv')
        
        # Load Phase II (Optimized 40h) Diagnostics
        df_store_p2 = pd.read_csv('data/output/store_level_diagnostics_optimized.csv')
        df_emp_p2 = pd.read_csv('data/output/employee_level_diagnostics_optimized.csv')
        
        # Load Raw Optimized Schedule for Download
        df_opt_raw = pd.read_csv('optimized_schedule.csv')
        
        return df_store_p1, df_emp_p1, df_store_p2, df_emp_p2, df_opt_raw
    except FileNotFoundError as e:
        st.error(f"❌ Missing Diagnostic Files. Please ensure both diagnostic generators have been run. Error: {e}")
        st.stop()

df_store_p1, df_emp_p1, df_store_p2, df_emp_p2, df_opt_raw = load_dashboard_data()

# --- 3. MACRO KPI CALCULATIONS ---
# Phase I Totals & Averages
p1_total_cost = df_store_p1['total_labor_cost'].sum()
p1_overtime_hours = df_emp_p1['overtime_hours'].sum()
p1_waste_hours = df_store_p1['waste_overstaffed_hours'].sum()
p1_avg_utilization = df_store_p1['labor_utilization_pct'].mean()
p1_avg_service = df_store_p1['service_level_pct'].mean()

# Phase II Totals & Averages
p2_total_cost = df_store_p2['total_labor_cost'].sum()
p2_overtime_hours = df_emp_p2['overtime_hours'].sum()
p2_shortfall_hours = df_store_p2['total_understaffed_hours'].sum()
p2_avg_utilization = df_store_p2['labor_utilization_pct'].mean()
p2_avg_service = df_store_p2['service_level_pct'].mean()

# Deltas
total_savings_mxn = p1_total_cost - p2_total_cost
savings_pct = (total_savings_mxn / p1_total_cost) * 100

# --- 4. TOP KPI ROW (FINANCIALS) ---
st.subheader("Financial & Compliance Impact")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Legacy Network Cost (48h)", value=f"${p1_total_cost:,.2f} MXN")
with col2:
    st.metric(label="Optimized Network Cost (40h)", value=f"${p2_total_cost:,.2f} MXN", delta=f"-{savings_pct:.2f}% Savings", delta_color="inverse")
with col3:
    st.metric(label="Illegal Overtime (200% Penalty)", value=f"{p2_overtime_hours:,.0f} Hours", delta=f"Down from {p1_overtime_hours:,.0f}h", delta_color="inverse")
with col4:
    st.metric(label="Annual Value Added", value=f"${(total_savings_mxn * 52):,.0f} MXN", delta="Recurring Savings", delta_color="normal")

st.divider()

# --- 5. OPERATIONAL KPI ROW (UTILIZATION & SERVICE) ---
st.subheader("Operational Impact: 'Bricks vs. Waves'")
col_u1, col_u2, col_s1, col_s2 = st.columns(4)

with col_u1:
    st.metric(label="Legacy Labor Utilization", value=f"{p1_avg_utilization:.1f}%")
with col_u2:
    st.metric(label="Optimized Labor Utilization", value=f"{p2_avg_utilization:.1f}%", delta=f"{p2_avg_utilization - p1_avg_utilization:.1f}% Efficiency Gain", delta_color="normal")
with col_s1:
    st.metric(label="Legacy Service Level", value=f"{p1_avg_service:.1f}%")
with col_s2:
    st.metric(label="Optimized Service Level", value=f"{p2_avg_service:.1f}%", delta=f"{p2_avg_service - p1_avg_service:.1f}% Gap Change", delta_color="off")

st.divider()

# --- 6. VISUALIZATIONS: EFFICIENCY & SERVICE ---
# Merge P1 and P2 for visualization
df_compare = pd.merge(
    df_store_p1[['store_id', 'city', 'format', 'total_labor_cost', 'labor_utilization_pct', 'service_level_pct']],
    df_store_p2[['store_id', 'total_labor_cost', 'labor_utilization_pct', 'service_level_pct']],
    on='store_id',
    suffixes=('_Legacy', '_Optimized')
)

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown("**Labor Utilization Shift (Eliminating Morning Waste)**")
    fig_util = go.Figure()
    fig_util.add_trace(go.Box(y=df_compare['labor_utilization_pct_Legacy'], name='Phase I (Legacy)', marker_color='#EF553B'))
    fig_util.add_trace(go.Box(y=df_compare['labor_utilization_pct_Optimized'], name='Phase II (Optimized)', marker_color='#00CC96'))
    fig_util.update_layout(yaxis_title="Utilization %", showlegend=False)
    st.plotly_chart(fig_util, use_container_width=True)

with row1_col2:
    st.markdown("**Service Level Protection (Hugging Peak Demand)**")
    fig_serv = go.Figure()
    fig_serv.add_trace(go.Box(y=df_compare['service_level_pct_Legacy'], name='Phase I (Legacy)', marker_color='#EF553B'))
    fig_serv.add_trace(go.Box(y=df_compare['service_level_pct_Optimized'], name='Phase II (Optimized)', marker_color='#00CC96'))
    fig_serv.update_layout(yaxis_title="Service Level %", showlegend=False)
    st.plotly_chart(fig_serv, use_container_width=True)

st.divider()

# --- 7. STORE LEVEL DEEP-DIVE TABLE ---
st.subheader("🔍 Store-Level Performance Matrix")

df_compare['Net_Savings_MXN'] = df_compare['total_labor_cost_Legacy'] - df_compare['total_labor_cost_Optimized']
df_compare['Savings_Pct'] = (df_compare['Net_Savings_MXN'] / df_compare['total_labor_cost_Legacy']) * 100

# Format for display
display_df = df_compare[['store_id', 'format', 'total_labor_cost_Legacy', 'total_labor_cost_Optimized', 'Savings_Pct', 'labor_utilization_pct_Legacy', 'labor_utilization_pct_Optimized', 'service_level_pct_Legacy', 'service_level_pct_Optimized']]

st.dataframe(
    display_df.style.format({
        'total_labor_cost_Legacy': '${:,.2f}',
        'total_labor_cost_Optimized': '${:,.2f}',
        'Savings_Pct': '{:.2f}%',
        'labor_utilization_pct_Legacy': '{:.1f}%',
        'labor_utilization_pct_Optimized': '{:.1f}%',
        'service_level_pct_Legacy': '{:.1f}%',
        'service_level_pct_Optimized': '{:.1f}%'
    }).background_gradient(subset=['Savings_Pct', 'labor_utilization_pct_Optimized'], cmap='YlGn'),
    use_container_width=True,
    height=400
)

# --- 8. SIDEBAR & EXPORT ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", width=50)
st.sidebar.header("Control Panel")
st.sidebar.markdown("**Network:** 50 Stores")
st.sidebar.markdown("**Workforce:** ~4,000 FTEs")
st.sidebar.markdown("**Target Constraint:** 40h/week")

st.sidebar.divider()
st.sidebar.success("✅ AI Engine Status: Optimal")
st.sidebar.metric("Strategic Hiring Signal", f"{p2_shortfall_hours:,.0f} Hrs", "Uncoverable peak demand")

st.sidebar.divider()
st.sidebar.markdown("### Export Hub")
st.sidebar.download_button(
    label="📥 Download Production Schedule (CSV)",
    data=df_opt_raw.to_csv(index=False),
    file_name="Aivena_Optimized_Network_Schedule.csv",
    mime="text/csv"
)