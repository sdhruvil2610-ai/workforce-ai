import pandas as pd
import numpy as np
import math
import os

# --- 1. SETUP PATHS ---
# Based on your sidebar, the files live here:
INPUT_DIR = 'data/input'

print("🚀 Starting Labor Demand & Workforce Phase II Upgrade...")

# --- 2. LOAD PHASE I DATA ---
try:
    df_traffic = pd.read_csv(f'{INPUT_DIR}/traffic_forecast.csv')
    df_rules = pd.read_csv(f'{INPUT_DIR}/staffing_rules.csv')
    df_emp = pd.read_csv(f'{INPUT_DIR}/employees.csv')
except FileNotFoundError as e:
    print(f"❌ Error: Could not find required input files. {e}")
    print(f"Make sure your .csv files are inside the '{INPUT_DIR}' folder.")
    exit()

# ==========================================
# PART A: GENERATE LABOR DEMAND CURVE
# ==========================================
print("📊 Calculating Hourly Labor Demand by Role...")
demand_records = []
PEAK_MULTIPLIER = 1.20 

for _, traffic_row in df_traffic.iterrows():
    customers = traffic_row['forecast_customers']
    is_peak = traffic_row['is_peak_hour']
    
    for _, rule_row in df_rules.iterrows():
        role = rule_row['role']
        productivity = rule_row['customers_per_hour'] 
        min_staff = rule_row['min_staff'] 
        
        required_staff = math.ceil(customers / productivity)
        if is_peak == 1:
            required_staff = math.ceil(required_staff * PEAK_MULTIPLIER)
            
        required_staff = max(required_staff, min_staff)
        
        demand_records.append({
            'store_id': traffic_row['store_id'],
            'date': traffic_row['date'],
            'day_of_week': traffic_row['day_of_week'],
            'hour': traffic_row['hour'],
            'is_peak_hour': is_peak,
            'role': role,
            'required_staff': required_staff
        })

df_demand = pd.DataFrame(demand_records)
# Saving to the same input folder so the optimizer can find it
df_demand.to_csv(f'{INPUT_DIR}/labor_demand_curve.csv', index=False)
print(f"✅ Generated 'labor_demand_curve.csv' in {INPUT_DIR}.")


# ==========================================
# PART B: UPGRADE WORKFORCE TO PHASE II
# ==========================================
print("👥 Upgrading Workforce to 40-Hr Cap & 'Strike Force' Premium...")

df_emp['max_weekly_hours'] = 40
df_emp['is_strike_force'] = 0
df_emp['secondary_role'] = 'None'

# Fix for the decimal wage error
df_emp['hourly_wage_mxn'] = df_emp['hourly_wage_mxn'].astype(float)

# Select 20% Strike Force[cite: 2]
eligible_mask = df_emp['role'].isin(['Cashier', 'Floor'])
np.random.seed(42) 
strike_force_indices = df_emp[eligible_mask].groupby('store_id').sample(frac=0.20, random_state=42).index
df_emp.loc[strike_force_indices, 'is_strike_force'] = 1

# Apply 12% premium[cite: 2]
for idx in strike_force_indices:
    primary_role = df_emp.at[idx, 'role']
    current_wage = df_emp.at[idx, 'hourly_wage_mxn']
    
    if primary_role == 'Cashier':
        df_emp.at[idx, 'secondary_role'] = 'Floor'
    elif primary_role == 'Floor':
        df_emp.at[idx, 'secondary_role'] = 'Cashier'
        
    df_emp.at[idx, 'hourly_wage_mxn'] = round(current_wage * 1.12, 2)

# Save to the input folder
df_emp.to_csv(f'{INPUT_DIR}/employees_phase2.csv', index=False)

print(f"✅ Created 'employees_phase2.csv' in {INPUT_DIR}.")
print("🎯 Phase II Data Prep Complete. Ready for Optimizer!")