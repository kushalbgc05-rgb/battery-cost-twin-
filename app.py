import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="PBCM Battery Cost Twin", layout="wide", initial_sidebar_state="expanded")

st.title("🔋 Dynamic Process-Based Cost Model (PBCM)")
st.markdown("Interactive Digital Twin evaluating GWh-scale lithium-ion production costs. Adjust N-tier supply constraints and factory efficiencies to simulate financial impacts.")
st.divider()

# --- STRICT PAPER BASELINES (From Article Fig 4, Without Scrap Recovery) ---
# Format: [Full, Marginal, Levelized, Mat%, Pers%, Dep%, OH%, Eng%]
baseline_data = {
    "Prismatic (PHEV2)": {
        "NMC811 / Graphite": [95.53, 87.73, 101.57, 0.854, 0.051, 0.062, 0.020, 0.013],
        "NMC811 / G + 5% Si": [94.15, 86.98, 99.77, 0.863, 0.048, 0.058, 0.018, 0.013],
        "LFP / Graphite": [99.54, 87.56, 108.48, 0.784, 0.078, 0.091, 0.029, 0.017]
    },
    "Cylindrical (4680)": {
        "NMC811 / Graphite": [96.03, 86.74, 103.21, 0.829, 0.059, 0.074, 0.023, 0.015],
        "NMC811 / G + 5% Si": [94.83, 86.18, 101.55, 0.838, 0.056, 0.069, 0.022, 0.015]
    }
}

# --- SIDEBAR: COMPLEX N-TIER CONTROLS ---
st.sidebar.header("🎛️ Digital Twin Parameters")

cell_format = st.sidebar.selectbox("1. Cell Geometry", ["Prismatic (PHEV2)", "Cylindrical (4680)"])

valid_chemistries = ["NMC811 / Graphite", "NMC811 / G + 5% Si"]
if cell_format == "Prismatic (PHEV2)":
    valid_chemistries.append("LFP / Graphite")
cell_chemistry = st.sidebar.selectbox("2. Cell Chemistry", valid_chemistries)

st.sidebar.markdown("---")
st.sidebar.subheader("Commodity Pricing (N-Tier)")
cathode_var = st.sidebar.slider("Cathode Material Price Variance (%)", -50, 50, 0, 5) / 100.0
anode_var = st.sidebar.slider("Anode Material Price Variance (%)", -50, 50, 0, 5) / 100.0
energy_var = st.sidebar.slider("Grid Energy Cost Variance (%)", -25, 50, 0, 5) / 100.0

st.sidebar.markdown("---")
st.sidebar.subheader("Process & Plant Efficiency")
scrap_efficiency = st.sidebar.slider("Closed-Loop Scrap Recovery Efficiency (%)", 0, 100, 0, 10) / 100.0
excess_capacity = st.sidebar.slider("Factory Excess Capacity Buffer (%)", 5, 50, 25, 5) / 100.0

# --- DYNAMIC CALCULATION ENGINE ---
base = baseline_data[cell_format][cell_chemistry]

# 1. Extract absolute baseline values
base_mat = base[0] * base[3]
base_pers = base[0] * base[4]
base_dep = base[0] * base[5]
base_oh = base[0] * base[6]
base_eng = base[0] * base[7]
capital_burden = base[2] - base[0] # Difference between Levelized and Full cost

# 2. Apply N-Tier Adjustments (Based on paper's sensitivity analysis)
# Cathode is roughly 55% of material cost; Anode is roughly 15%
mat_cost_adj = base_mat * (1 + (0.55 * cathode_var) + (0.15 * anode_var))

# 100% Scrap recovery efficiency yields approx 5.5% reduction in total material cost
scrap_savings = mat_cost_adj * (0.055 * scrap_efficiency)
final_mat_cost = mat_cost_adj - scrap_savings

# Energy adjustments
final_eng_cost = base_eng * (1 + energy_var)

# 3. Apply Factory Efficiency Adjustments
# Paper baseline assumes 25% excess capacity. Higher buffer = higher overhead/depreciation burden per cell.
efficiency_ratio = (1 + excess_capacity) / 1.25
final_dep_cost = base_dep * efficiency_ratio
final_oh_cost = base_oh * efficiency_ratio
final_cap_burden = capital_burden * efficiency_ratio

# 4. Final Aggregations
dyn_marg_cost = final_mat_cost + base_pers + final_eng_cost
dyn_full_cost = dyn_marg_cost + final_dep_cost + final_oh_cost
dyn_lev_cost = dyn_full_cost + final_cap_burden

# --- TOP KPI METRICS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Levelized Cost", f"${dyn_lev_cost:.2f} / kWh", help="Zero NPV break-even price. Includes capital costs and WACC.")
with col2:
    st.metric("Full Cost", f"${dyn_full_cost:.2f} / kWh", delta=f"${dyn_full_cost - base[0]:.2f} vs Base", delta_color="inverse")
with col3:
    st.metric("Marginal Cost", f"${dyn_marg_cost:.2f} / kWh", help="Direct materials, labor, and energy only.")

st.divider()

# --- ANALYTICAL GRAPHS ---
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader(f"Cost Component Breakdown")
    
    breakdown_df = pd.DataFrame({
        "Component": ["Material", "Personnel", "Depreciation", "Overhead", "Energy"],
        "Cost ($/kWh)": [final_mat_cost, base_pers, final_dep_cost, final_oh_cost, final_eng_cost]
    })
    
    fig_bar = px.bar(
        breakdown_df, x="Component", y="Cost ($/kWh)", text="Cost ($/kWh)",
        color="Component", color_discrete_sequence=px.colors.qualitative.Prism
    )
    fig_bar.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
    fig_bar.update_layout(height=400, showlegend=False, margin=dict(t=30, b=10, l=10, r=10))
    st.plotly_chart(fig_bar, use_container_width=True, theme="streamlit")

with col_chart2:
    st.subheader("Levelized Cost Waterfall")
    
    wf_labels = ['Direct Materials', 'Direct Labor', 'Energy', 'Marginal Cost', 'Depreciation & OH', 'Capital Burden', 'Levelized Cost']
    wf_measures = ["relative", "relative", "relative", "total", "relative", "relative", "total"]
    wf_values = [final_mat_cost, base_pers, final_eng_cost, 0, (final_dep_cost + final_oh_cost), final_cap_burden, 0]
    
    fig_wf = go.Figure(go.Waterfall(
        name="Cost Waterfall", orientation="v", measure=wf_measures,
        x=wf_labels, textposition="outside", text=[f"${v:.1f}" if v != 0 else "" for v in wf_values],
        y=wf_values,
        decreasing={"marker":{"color":"#10b981"}}, increasing={"marker":{"color":"#3b82f6"}}, totals={"marker":{"color":"#0f172a"}}
    ))
    fig_wf.update_layout(height=400, margin=dict(t=30, b=10, l=10, r=10))
    st.plotly_chart(fig_wf, use_container_width=True, theme="streamlit")
