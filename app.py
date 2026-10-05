import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- PAGE CONFIGURATION & DYNAMIC THEMING ---
st.set_page_config(
    page_title="Battery Cell Supplier Cost Benchmarking",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for executive metric cards and footer formatting
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
        transition: transform 0.2s ease-in-out, border-color 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #0284c7;
    }
    .delta-badge {
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
    }
    .reference-link {
        color: #0284c7;
        text-decoration: none;
        font-weight: 500;
    }
    .reference-link:hover {
        text-decoration: underline;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Battery Cell Supplier Cost Benchmarking")
st.markdown(
    "Bottom-up Process-Based Cost Model (PBCM) comparing cell manufacturing costs across suppliers. "
    "Deconstructs raw materials into granular N-Tier commodity drivers while benchmarking "
    "**Marginal Cost**, **Full Cost**, and **Levelized Cost**."
)
st.divider()

# --- SIDEBAR: N-TIER COMMODITY LEVERS & SUPPLIER PARAMETERS ---
st.sidebar.header("🎛️ N-Tier Cost Drivers & Market Indices")

with st.sidebar.expander("Upstream Raw Materials (Commodity Indices)", expanded=True):
    st.caption("Indexed to contract/spot market swings against baseline values.")
    lithium_var = st.slider("Lithium Hydroxide / Carbonate Index (%)", -50, 50, 0, 5) / 100.0
    nickel_cobalt_var = st.slider("Cathode Active Precursor (CAM / pCAM) (%)", -50, 50, 0, 5) / 100.0
    graphite_si_var = st.slider("Anode Precursor (Graphite / Silicon) (%)", -50, 50, 0, 5) / 100.0
    foils_var = st.slider("Current Collector Foils (Cu & Al) (%)", -40, 40, 0, 5) / 100.0
    electrolyte_sep_var = st.slider("Electrolyte (LiPF6) & Separator (%)", -30, 30, 0, 5) / 100.0

with st.sidebar.expander("Gigafactory Operational Efficiencies", expanded=True):
    grid_energy_var = st.slider("Industrial Electricity Tariff Variance (%)", -40, 60, 0, 5) / 100.0
    global_scrap_recovery = st.slider("Closed-Loop Scrap Recovery Efficiency (%)", 0, 100, 50, 10) / 100.0

st.sidebar.markdown("---")
st.sidebar.subheader("Supplier Configuration Profiles")

# Supplier A Configuration (Baseline: CATL)
with st.sidebar.expander("Supplier A Profile (CATL)", expanded=True):
    supA_name = st.text_input("Supplier A Identifier", value="CATL")
    supA_format = st.selectbox("Cell Geometry (A)", ["Prismatic (PHEV2)", "Cylindrical (4680)"], index=0)
    
    valid_chem_A = ["NMC811 / Graphite", "NMC811 / G + 5% Si"]
    if supA_format == "Prismatic (PHEV2)":
        valid_chem_A.append("LFP / Graphite")
    supA_chem = st.selectbox("Cell Chemistry (A)", valid_chem_A, index=0)
    
    supA_capex_eff = st.slider("Plant Automation & Capex Efficiency (A) (%)", -20, 20, 5, 5, key="eff_A") / 100.0
    supA_margin = st.slider("Commercial Margin / Capital Burden (A) (%)", 4.0, 20.0, 8.5, 0.5, key="mrg_A") / 100.0

# Supplier B Configuration (Baseline: Panasonic)
with st.sidebar.expander("Supplier B Profile (Panasonic)", expanded=True):
    supB_name = st.text_input("Supplier B Identifier", value="Panasonic")
    supB_format = st.selectbox("Cell Geometry (B)", ["Prismatic (PHEV2)", "Cylindrical (4680)"], index=0)
    
    valid_chem_B = ["NMC811 / Graphite", "NMC811 / G + 5% Si"]
    if supB_format == "Prismatic (PHEV2)":
        valid_chem_B.append("LFP / Graphite")
    supB_chem = st.selectbox("Cell Chemistry (B)", valid_chem_B, index=0)
    
    supB_capex_eff = st.slider("Plant Automation & Capex Efficiency (B) (%)", -20, 20, -5, 5, key="eff_B") / 100.0
    supB_margin = st.slider("Commercial Margin / Capital Burden (B) (%)", 4.0, 20.0, 11.0, 0.5, key="mrg_B") / 100.0

# --- RESEARCH BASELINE DATA MATRIX ---
# Baseline structure: [Full Cost ($/kWh), Marginal Cost, Levelized Cost, Mat%, Pers%, Dep%, OH%, Eng%]
baseline_matrix = {
    "Prismatic (PHEV2)": {
        "NMC811 / Graphite": [95.53, 87.73, 101.57, 0.854, 0.051, 0.062, 0.020, 0.013],
        "NMC811 / G + 5% Si": [94.15, 86.98, 99.77, 0.863, 0.048, 0.058, 0.018, 0.013],
        "LFP / Graphite": [99.54, 87.56, 108.48, 0.784, 0.078, 0.091, 0.029, 0.017]
    },
    "Cylindrical (4680)": {
        "NMC811 / Graphite": [96.03, 86.74, 103.21, 0.829, 0.059, 0.074, 0.023, 0.015],
        "NMC811 / G + 5% Si": [94.83, 86.18, 101.55, 0.838, 0.056, 0.069, 0.022, 0.015],
        "LFP / Graphite": [101.20, 88.10, 110.50, 0.770, 0.080, 0.095, 0.035, 0.020]
    }
}

# --- COST CALCULATION ENGINE ---
def calculate_complete_cost_structure(fmt, chem, capex_delta, margin_pct):
    base_entry = baseline_matrix[fmt][chem]
    base_full = base_entry[0]
    
    b_mat = base_full * base_entry[3]
    b_pers = base_full * base_entry[4]
    b_dep = base_full * base_entry[5]
    b_oh = base_full * base_entry[6]
    b_eng = base_full * base_entry[7]
    
    if "LFP" in chem:
        w_li, w_cam, w_anode, w_foils, w_elyte, w_can = 0.18, 0.32, 0.16, 0.14, 0.13, 0.07
    elif "Si" in chem:
        w_li, w_cam, w_anode, w_foils, w_elyte, w_can = 0.27, 0.28, 0.16, 0.11, 0.12, 0.06
    else:
        w_li, w_cam, w_anode, w_foils, w_elyte, w_can = 0.28, 0.28, 0.14, 0.11, 0.13, 0.06
        
    material_index_delta = (
        (w_li * lithium_var) + (w_cam * nickel_cobalt_var) +
        (w_anode * graphite_si_var) + (w_foils * foils_var) + (w_elyte * electrolyte_sep_var)
    )
    
    adjusted_material_gross = b_mat * (1.0 + material_index_delta)
    scrap_reduction = adjusted_material_gross * (0.055 * global_scrap_recovery)
    final_material = adjusted_material_gross - scrap_reduction
    
    bom_components = {
        "Lithium Salt": final_material * w_li,
        "Cathode Active Mat. (CAM)": final_material * w_cam,
        "Anode Active Mat.": final_material * w_anode,
        "Current Collector Foils": final_material * w_foils,
        "Electrolyte & Separator": final_material * w_elyte,
        "Casing & Hardware": final_material * w_can
    }
    
    final_labor = b_pers
    final_energy = b_eng * (1.0 + grid_energy_var)
    
    capex_scale = 1.0 - capex_delta
    final_depreciation = b_dep * capex_scale
    final_overhead = b_oh * capex_scale
    
    marginal_cost = final_material + final_labor + final_energy
    full_cost = marginal_cost + final_depreciation + final_overhead
    
    margin_value = full_cost * margin_pct
    levelized_cost = full_cost + margin_value
    
    return {
        "bom": bom_components, "material_total": final_material, "labor": final_labor,
        "energy": final_energy, "marginal_cost": marginal_cost, "depreciation": final_depreciation,
        "overhead": final_overhead, "full_cost": full_cost, "margin_value": margin_value,
        "levelized_cost": levelized_cost
    }

cost_A = calculate_complete_cost_structure(supA_format, supA_chem, supA_capex_eff, supA_margin)
cost_B = calculate_complete_cost_structure(supB_format, supB_chem, supB_capex_eff, supB_margin)

# --- TOP LEVEL EXECUTIVE KPIS ---
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
delta_levelized = cost_A["levelized_cost"] - cost_B["levelized_cost"]
delta_marginal = cost_A["marginal_cost"] - cost_B["marginal_cost"]

with kpi1:
    st.metric(f"{supA_name} Levelized Price", f"${cost_A['levelized_cost']:.2f} / kWh", f"Full Cost: ${cost_A['full_cost']:.2f}")
with kpi2:
    st.metric(f"{supB_name} Levelized Price", f"${cost_B['levelized_cost']:.2f} / kWh", f"Full Cost: ${cost_B['full_cost']:.2f}")
with kpi3:
    st.metric("Levelized Price Delta (A - B)", f"${abs(delta_levelized):.2f} / kWh", 
              delta=f"{supA_name} is {'More Competitive' if delta_levelized < 0 else 'Higher Cost'}", 
              delta_color="normal" if delta_levelized < 0 else "inverse")
with kpi4:
    st.metric("Marginal Cost Delta (A - B)", f"${abs(delta_marginal):.2f} / kWh", 
              delta=f"Direct Ops Delta: ${delta_marginal:+.2f}", 
              delta_color="normal" if delta_marginal < 0 else "inverse")

st.markdown("<br>", unsafe_allow_html=True)

# --- INTEGRATED WATERFALL BUILD-UP VISUALIZATION ---
st.subheader("I. Granular Cost Breakdown & Milestone Build-Up")
st.caption(
    "Visualizing individual N-Tier raw materials, direct labor, and energy leading to **Marginal Cost**, "
    "followed by depreciation and plant overhead yielding **Full Cost**, and final capital margin yielding **Levelized Cost**."
)

col_chart_A, col_chart_B = st.columns(2)

def generate_supplier_waterfall(cost_data, supplier_title, bar_color):
    labels = [
        "Lithium Salt", "Cathode (CAM)", "Anode Active", "Collector Foils", "Electrolyte/Sep", "Can & Hardware",
        "Direct Labor", "Process Energy", "Marginal Cost", "Plant Depreciation", "Factory Overhead",
        "Full Cost", "Supplier Margin", "Levelized Cost"
    ]
    measures = [
        "relative", "relative", "relative", "relative", "relative", "relative", "relative", "relative",
        "total", "relative", "relative", "total", "relative", "total"
    ]
    
    bom = cost_data["bom"]
    values = [
        bom["Lithium Salt"], bom["Cathode Active Mat. (CAM)"], bom["Anode Active Mat."],
        bom["Current Collector Foils"], bom["Electrolyte & Separator"], bom["Casing & Hardware"],
        cost_data["labor"], cost_data["energy"], 0, cost_data["depreciation"], cost_data["overhead"], 0, 
        cost_data["margin_value"], 0
    ]
    
    text_labels = []
    for idx, m in enumerate(measures):
        if m == "total":
            if idx == 8: val = cost_data["marginal_cost"]
            elif idx == 11: val = cost_data["full_cost"]
            elif idx == 13: val = cost_data["levelized_cost"]
            text_labels.append(f"<b>${val:.2f}</b>")
        else:
            text_labels.append(f"${values[idx]:.2f}")
            
    fig = go.Figure(go.Waterfall(
        name=supplier_title, orientation="v", measure=measures, x=labels, text=text_labels, textposition="outside",
        y=values, decreasing={"marker": {"color": "#10b981"}}, increasing={"marker": {"color": bar_color}},
        totals={"marker": {"color": "#0f172a"}}
    ))
    
    fig.update_layout(
        title=f"<b>{supplier_title}</b>", height=520, yaxis_title="Unit Production Cost ($/kWh)",
        margin=dict(t=50, b=20, l=10, r=10), xaxis=dict(tickangle=-45)
    )
    return fig

with col_chart_A:
    st.plotly_chart(generate_supplier_waterfall(cost_A, f"{supA_name} — {supA_format} ({supA_chem})", "#0284c7"), use_container_width=True)

with col_chart_B:
    st.plotly_chart(generate_supplier_waterfall(cost_B, f"{supB_name} — {supB_format} ({supB_chem})", "#d97706"), use_container_width=True)

# --- DETAILED COMPARATIVE AUDIT REGISTER ---
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("II. Line-Item Cost Comparison Register ($/kWh)")

comparison_df = pd.DataFrame({
    "Cost Category / Milestone": [
        "1. Lithium Salt", "2. Cathode Active Precursor (CAM)", "3. Anode Active Material",
        "4. Current Collector Metal Foils", "5. Electrolyte & Separator", "6. Casing & Cell Hardware",
        "→ Total Raw Materials", "7. Direct Factory Labor", "8. Process Electricity & Energy",
        "★ MARGINAL COST (Direct Operating Floor)", "9. Machinery & Facility Depreciation",
        "10. Factory Overhead & Administration", "★ FULL COST (Complete Production Burden)",
        "11. Supplier Capital Margin / IRR", "★ LEVELIZED COST (Contract Price to OEM)"
    ],
    f"{supA_name} ($/kWh)": [
        cost_A["bom"]["Lithium Salt"], cost_A["bom"]["Cathode Active Mat. (CAM)"], cost_A["bom"]["Anode Active Mat."],
        cost_A["bom"]["Current Collector Foils"], cost_A["bom"]["Electrolyte & Separator"], cost_A["bom"]["Casing & Hardware"],
        cost_A["material_total"], cost_A["labor"], cost_A["energy"], cost_A["marginal_cost"],
        cost_A["depreciation"], cost_A["overhead"], cost_A["full_cost"], cost_A["margin_value"], cost_A["levelized_cost"]
    ],
    f"{supB_name} ($/kWh)": [
        cost_B["bom"]["Lithium Salt"], cost_B["bom"]["Cathode Active Mat. (CAM)"], cost_B["bom"]["Anode Active Mat."],
        cost_B["bom"]["Current Collector Foils"], cost_B["bom"]["Electrolyte & Separator"], cost_B["bom"]["Casing & Hardware"],
        cost_B["material_total"], cost_B["labor"], cost_B["energy"], cost_B["marginal_cost"],
        cost_B["depreciation"], cost_B["overhead"], cost_B["full_cost"], cost_B["margin_value"], cost_B["levelized_cost"]
    ]
})

comparison_df["Variance (A - B)"] = comparison_df[f"{supA_name} ($/kWh)"] - comparison_df[f"{supB_name} ($/kWh)"]
formatted_df = comparison_df.style.format({f"{supA_name} ($/kWh)": "${:.2f}", f"{supB_name} ($/kWh)": "${:.2f}", "Variance (A - B)": "${:+.2f}"})
st.dataframe(formatted_df, use_container_width=True, height=480)

# --- METHODOLOGY & ACADEMIC PROVENANCE (DATA SOURCES) ---
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("📚 Academic & Industry Methodology Provenance (Data Sources)", expanded=False):
    st.markdown("""
    **1. Baseline Factory Macro-Splits & Format Scaling:**
    > Lechner, M., Kollenda, A., Bendzuck, K., Burmeister, J.K., Mahin, K., Keilhofer, J., Kemmer, L., Blaschke, M.J., Friedl, G., Daub, R. & Kwade, A. *"Cost modeling for the GWh-scale production of modern lithium-ion battery cells."* **Communications Engineering 3**, 155 (2024), Nature Portfolio. 
    > <a href="https://doi.org/10.1038/s44172-024-00306-0" class="reference-link" target="_blank">DOI: 10.1038/s44172-024-00306-0</a>
    <br><span style="font-size: 0.85em; color: gray;"><i>(Validates baseline manufacturing splits across Depreciation, Personnel, Energy, and Base Materials for Prismatic and 4680 formats).</i></span>

    <br>

    **2. N-Tier Granular BOM & Raw Material De-Averaging:**
    > Nelson, P.A., Gallagher, K.G., et al. *"Battery Performance and Cost Modeling for Electric-Drive Vehicles (BatPaC v5.0)."* **Argonne National Laboratory** / US Department of Energy (2022).
    > <a href="https://doi.org/10.2172/1877590" class="reference-link" target="_blank">DOI: 10.2172/1877590</a> | <a href="https://www.anl.gov/partnerships/batpac-battery-manufacturing-cost-estimation" class="reference-link" target="_blank">ANL BatPaC Software</a>
    <br><span style="font-size: 0.85em; color: gray;"><i>(Validates the specific stoichiometric splits used for Lithium Salt, Cathode Active Materials (CAM), Anode precursors, Copper/Aluminum foils, and Casing Hardware).</i></span>

    <br>

    **3. Closed-Loop Scrap Recovery & Process Energy:**
    > Degen, F., Schmuch, R. et al. *"Energy consumption and cost modeling of battery production."* **Fraunhofer ISI**.
    > <a href="https://www.isi.fraunhofer.de/en/themen/batterien.html" class="reference-link" target="_blank">Fraunhofer Battery Research Platform</a>
    <br><span style="font-size: 0.85em; color: gray;"><i>(Validates the process energy variance assumptions and the algorithmic impact of closed-loop scrap recycling on raw material cost offsets).</i></span>
    """, unsafe_allow_html=True)
