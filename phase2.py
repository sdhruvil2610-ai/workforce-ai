import pandas as pd
import numpy as np
import os

# --- 1. CONFIGURATION ---
# Assumes your data is organized as established in Phase I
INPUT_DIR = 'data/input'
OUTPUT_DIR = 'data/output'
OPTIMIZED_FILE = 'optimized_schedule.csv'

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_phase_ii_diagnostics():
    print("🚀 Generating Phase II Diagnostics...")

    # 2. LOAD DATA
    df_opt = pd.read_csv(OPTIMIZED_FILE)
    df_emp = pd.read_csv(os.path.join(INPUT_DIR, 'employees_phase2.csv'))
    df_demand = pd.read_csv(os.path.join(INPUT_DIR, 'labor_demand_curve.csv'))
    df_stores = pd.read_csv(os.path.join(INPUT_DIR, 'stores.csv'))

    # Standardize IDs and Formats
    for df in [df_opt, df_emp, df_demand, df_stores]:
        for col in ['store_id', 'employee_id', 'role']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    
    df_demand['date'] = pd.to_datetime(df_demand['date']).dt.strftime('%Y-%m-%d')
    df_opt['date'] = pd.to_datetime(df_opt['date']).dt.strftime('%Y-%m-%d')

    # --- 3. EMPLOYEE LEVEL DIAGNOSTICS (PHASE II) ---
    # Map metadata from the employee roster
    wages = df_emp.set_index('employee_id')['hourly_wage_mxn'].to_dict()
    roles = df_emp.set_index('employee_id')['role'].to_dict()
    store_map = df_emp.set_index('employee_id')['store_id'].to_dict()

    emp_diag = df_opt.groupby('employee_id').agg({'duration': 'sum'}).reset_index()
    emp_diag['store_id'] = emp_diag['employee_id'].map(store_map)
    emp_diag['role'] = emp_diag['employee_id'].map(roles)
    emp_diag['total_hours'] = emp_diag['duration']
    
    # 40-hour legal cap logic (OT is penalized at 200% if present)
    emp_diag['overtime_hours'] = emp_diag['total_hours'].apply(lambda x: max(0, x - 40))
    emp_diag['regular_hours'] = emp_diag['total_hours'] - emp_diag['overtime_hours']
    emp_diag['total_labor_cost_mxn'] = (emp_diag['regular_hours'] * emp_diag['employee_id'].map(wages)) + \
                                      (emp_diag['overtime_hours'] * emp_diag['employee_id'].map(wages) * 2.0)

    emp_diag.to_csv(os.path.join(OUTPUT_DIR, 'employee_level_diagnostics_optimized.csv'), index=False)
    print("✅ Created: employee_level_diagnostics_optimized.csv")

    # --- 4. STORE LEVEL DIAGNOSTICS (PHASE II) ---
    # Explode shifts to hourly coverage blocks to measure gaps
    hourly_rows = []
    for _, row in df_opt.iterrows():
        for h in range(int(row['shift_start']), int(row['shift_end'])):
            hourly_rows.append({
                'store_id': row['store_id'], 'date': row['date'], 
                'hour': h, 'role': row['assigned_role'], 'scheduled_staff': 1
            })
    
    df_coverage = pd.DataFrame(hourly_rows).groupby(['store_id', 'date', 'hour', 'role']).size().reset_index(name='scheduled_staff')
    
    # Merge coverage with demand curve to find over/understaffing
    df_merged = pd.merge(df_demand, df_coverage, on=['store_id', 'date', 'hour', 'role'], how='left').fillna(0)
    df_merged['understaffed'] = (df_merged['required_staff'] - df_merged['scheduled_staff']).clip(lower=0)
    df_merged['overstaffed'] = (df_merged['scheduled_staff'] - df_merged['required_staff']).clip(lower=0)
    
    # Aggregate KPIs to Store Level
    store_agg = df_merged.groupby('store_id').agg({
        'required_staff': 'sum', 'scheduled_staff': 'sum',
        'understaffed': 'sum', 'overstaffed': 'sum'
    }).reset_index()
    
    # Merge with costs and metadata
    store_costs = emp_diag.groupby('store_id')['total_labor_cost_mxn'].sum().reset_index()
    store_diag = pd.merge(df_stores, store_agg, on='store_id')
    store_diag = pd.merge(store_diag, store_costs, on='store_id')
    
    # Apply CEO KPI Formulas
    store_diag['total_labor_cost'] = store_diag['total_labor_cost_mxn']
    store_diag['total_scheduled_hours'] = store_diag['scheduled_staff']
    store_diag['total_required_hours'] = store_diag['required_staff']
    
    # Utilization and Service Level math
    store_diag['labor_utilization_pct'] = (store_diag['total_required_hours'] / store_diag['total_scheduled_hours'] * 100).fillna(0)
    store_diag['service_level_pct'] = ((store_diag['total_required_hours'] - store_diag['understaffed']) / store_diag['total_required_hours'] * 100).fillna(0)
    
    # Final Output Formatting
    final_cols = ['store_id', 'city', 'format', 'total_labor_cost', 'total_scheduled_hours', 
                  'total_required_hours', 'labor_utilization_pct', 'service_level_pct', 
                  'waste_overstaffed_hours', 'total_understaffed_hours']
    
    store_diag.rename(columns={'overstaffed': 'waste_overstaffed_hours', 'understaffed': 'total_understaffed_hours'}, inplace=True)
    store_diag[final_cols].to_csv(os.path.join(OUTPUT_DIR, 'store_level_diagnostics_optimized.csv'), index=False)
    print("✅ Created: store_level_diagnostics_optimized.csv")

if __name__ == "__main__":
    generate_phase_ii_diagnostics()