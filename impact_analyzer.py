import pandas as pd
import numpy as np
import os
import argparse

# --- 1. DYNAMIC PATHING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')

# Look for the new distinct name
OPTIMIZED_SCHED = os.path.join(BASE_DIR, 'final_network_schedule.csv')
LEGACY_SCHED = os.path.join(BASE_DIR, 'legacy_schedule_sim.csv')

def analyze_schedule(schedule_path, demand_path, prefix):
    print(f"   ↳ Processing {prefix} metrics...")
    try:
        df_sched = pd.read_csv(schedule_path)
        df_emp = pd.read_csv(os.path.join(INPUT_DIR, 'employees_phase2.csv'))
        df_demand = pd.read_csv(demand_path)
        df_stores = pd.read_csv(os.path.join(INPUT_DIR, 'stores.csv'))
    except FileNotFoundError:
        return False

    for df in [df_sched, df_emp, df_demand, df_stores]:
        for col in ['store_id', 'employee_id', 'role', 'assigned_role']:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()

    # CRITICAL: Legacy evaluates OT > 48hrs. Optimized evaluates OT > 40hrs.
    ot_threshold = 48 if prefix == 'legacy' else 40

    wages = df_emp.set_index('employee_id')['hourly_wage_mxn'].to_dict()
    emp_diag = df_sched.groupby('employee_id').agg({'duration': 'sum'}).reset_index()
    emp_diag['store_id'] = emp_diag['employee_id'].map(df_emp.set_index('employee_id')['store_id'].to_dict())
    
    emp_diag['overtime_hours'] = emp_diag['duration'].apply(lambda x: max(0, x - ot_threshold))
    emp_diag['regular_hours'] = emp_diag['duration'] - emp_diag['overtime_hours']
    
    # 2.0x Mexican Overtime Penalty
    emp_diag['total_labor_cost_mxn'] = (emp_diag['regular_hours'] * emp_diag['employee_id'].map(wages)) + \
                                       (emp_diag['overtime_hours'] * emp_diag['employee_id'].map(wages) * 2.0)

    hourly_coverage = []
    for row in df_sched.itertuples():
        for h in range(int(row.shift_start), int(row.shift_end)):
            hourly_coverage.append({
                'store_id': row.store_id, 'date': row.date, 'hour': h, 
                'role': row.assigned_role, 'scheduled_staff': 1
            })
    
    df_cov = pd.DataFrame(hourly_coverage).groupby(['store_id', 'date', 'hour', 'role'])['scheduled_staff'].sum().reset_index()
    df_merged = pd.merge(df_demand, df_cov, on=['store_id', 'date', 'hour', 'role'], how='left').fillna({'scheduled_staff': 0})
    
    df_merged['overstaffed'] = (df_merged['scheduled_staff'] - df_merged['required_staff']).clip(lower=0)
    df_merged['understaffed'] = (df_merged['required_staff'] - df_merged['scheduled_staff']).clip(lower=0)
    
    store_agg = df_merged.groupby('store_id').agg({
        'required_staff': 'sum', 'scheduled_staff': 'sum', 'understaffed': 'sum', 'overstaffed': 'sum'
    }).reset_index()
    
    store_costs = emp_diag.groupby('store_id')['total_labor_cost_mxn'].sum().reset_index()
    store_diag = pd.merge(df_stores, store_agg, on='store_id')
    store_diag = pd.merge(store_diag, store_costs, on='store_id')
    
    store_diag['labor_utilization_pct'] = np.where(store_diag['scheduled_staff'] > 0, 
                                                   (store_diag['required_staff'] / store_diag['scheduled_staff']) * 100, 0)
    
    store_diag.to_csv(os.path.join(OUTPUT_DIR, f'store_diagnostics_{prefix}.csv'), index=False)
    emp_diag.to_csv(os.path.join(OUTPUT_DIR, f'employee_diagnostics_{prefix}.csv'), index=False)
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--demand', type=str, default=os.path.join(INPUT_DIR, 'labor_demand_curve_sim.csv'))
    args = parser.parse_args()
    
    analyze_schedule(OPTIMIZED_SCHED, args.demand, 'optimized')
    analyze_schedule(LEGACY_SCHED, args.demand, 'legacy')