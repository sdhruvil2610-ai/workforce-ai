import pandas as pd
from ortools.sat.python import cp_model
import os
import time
import math

# --- 1. SETUP ---
INPUT_DIR = 'data/input'
# Changed to save directly in the main folder so you can find it instantly
OUTPUT_FILE = 'optimized_schedule.csv' 

print("🚀 Launching Workforce AI (Full Network & Heavy-Duty Solver)...")

# --- 2. LOAD DATA ---
def load_file(name):
    path1 = os.path.join(INPUT_DIR, name)
    if os.path.exists(path1): return pd.read_csv(path1)
    elif os.path.exists(name): return pd.read_csv(name)
    else: raise FileNotFoundError(f"Missing {name}")

try:
    df_demand = load_file('labor_demand_curve.csv')
    df_emp = load_file('employees_phase2.csv')
    df_baseline = load_file('current_schedule.csv')
    
    for df in [df_demand, df_emp, df_baseline]:
        for col in ['store_id', 'role', 'employee_id']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    
    df_demand['date'] = pd.to_datetime(df_demand['date']).dt.strftime('%Y-%m-%d')
    df_baseline['date'] = pd.to_datetime(df_baseline['date']).dt.strftime('%Y-%m-%d')
except Exception as e:
    print(f"❌ Error during load: {e}")
    exit()

# --- 3. SHIFT TEMPLATES ---
def get_eligible_shifts(role):
    templates = []
    if 'Supervisor' in role:
        for start in [8, 10, 12, 14]:
            templates.append({'start': start, 'end': start + 8, 'duration': 8})
    else:
        for start in [8, 10, 12, 14]:
            templates.append({'start': start, 'end': start + 8, 'duration': 8})
        for start in [13, 14, 15, 16]:
            for dur in [5, 6]:
                templates.append({'start': start, 'end': start + dur, 'duration': dur})
    return templates

# --- 4. OPTIMIZATION ENGINE ---
VOLATILITY_BUFFER = 1.0 # 100% of demand (Matches your 10% savings run)
PENALTY_RATE = 10000 
optimized_records = []
total_optimized_payroll = 0
total_shortfall_hours = 0
demo_stores = df_demand['store_id'].unique()

start_time = time.time()

for store in demo_stores:
    print(f"\n⚙️ Solving Store {store}...")
    store_demand = df_demand[df_demand['store_id'] == store]
    store_emps = df_emp[df_emp['store_id'] == store]
    days = sorted(store_demand['date'].unique())
    
    model = cp_model.CpModel()
    X = {} 

    # [A] VARIABLES
    for _, emp in store_emps.iterrows():
        e = emp['employee_id']
        allowed_roles = [emp['role']]
        if str(emp['is_strike_force']) == '1' and pd.notna(emp['secondary_role']) and str(emp['secondary_role']) != 'None':
            allowed_roles.append(str(emp['secondary_role']))
        
        for d in days:
            for s_idx, _ in enumerate(get_eligible_shifts(emp['role'])):
                for r in allowed_roles:
                    X[(e, d, s_idx, r)] = model.NewBoolVar(f'x_{e}_{d}_{s_idx}_{r}')

    # [B] HARD CONSTRAINTS
    for _, emp in store_emps.iterrows():
        e = emp['employee_id']
        templates = get_eligible_shifts(emp['role'])
        
        # 1. 40-Hour Cap
        model.Add(sum(X[(e,d,s_idx,r)] * templates[s_idx]['duration'] 
                      for d in days for s_idx in range(len(templates)) 
                      for r in [emp['role'], str(emp.get('secondary_role', 'None'))] 
                      if (e,d,s_idx,r) in X) <= 40)
        
        # 2. One Shift Per Day
        for d in days:
            model.Add(sum(X[(e,d,s_idx,r)] for s_idx in range(len(templates)) 
                          for r in [emp['role'], str(emp.get('secondary_role', 'None'))] 
                          if (e,d,s_idx,r) in X) <= 1)

        # 3. 12-Hour Rest Rule
        for i in range(len(days) - 1):
            d1, d2 = days[i], days[i+1]
            for s1_idx, s1 in enumerate(templates):
                for s2_idx, s2 in enumerate(templates):
                    if (24 + s2['start']) - s1['end'] < 12:
                        for r1 in [emp['role'], str(emp.get('secondary_role', 'None'))]:
                            for r2 in [emp['role'], str(emp.get('secondary_role', 'None'))]:
                                if (e,d1,s1_idx,r1) in X and (e,d2,s2_idx,r2) in X:
                                    model.AddImplication(X[(e,d1,s1_idx,r1)], X[(e,d2,s2_idx,r2)].Not())

    # [C] SOFT CONSTRAINTS & OBJECTIVE
    cost_terms = []
    shortfall_vars = []
    
    # Track Payroll Wages
    for (e, d, s_idx, r), var in X.items():
        wage = float(store_emps[store_emps['employee_id'] == e]['hourly_wage_mxn'].iloc[0])
        dur = get_eligible_shifts(store_emps[store_emps['employee_id']==e]['role'].iloc[0])[s_idx]['duration']
        cost_terms.append(var * int(dur * wage))

    # Track Coverage & Penalties
    for d in days:
        for h in range(8, 22):
            for r in store_demand['role'].unique():
                forecast = store_demand[(store_demand['date']==d) & (store_demand['hour']==h) & (store_demand['role']==r)]
                if not forecast.empty:
                    target = math.ceil(forecast['required_staff'].iloc[0] * VOLATILITY_BUFFER)
                    if target > 0:
                        staff_here = [X[(e_id, d, s_idx, r)] for _, emp in store_emps.iterrows()
                                      for e_id in [emp['employee_id']]
                                      for s_idx, s in enumerate(get_eligible_shifts(emp['role']))
                                      if s['start'] <= h < s['end'] and (e_id, d, s_idx, r) in X]
                        
                        shortfall = model.NewIntVar(0, target, f'sf_{d}_{h}_{r}')
                        model.Add(sum(staff_here) + shortfall >= target)
                        cost_terms.append(shortfall * PENALTY_RATE)
                        shortfall_vars.append(shortfall)

    model.Minimize(sum(cost_terms))

    # [D] HEAVY-DUTY SOLVE
    solver = cp_model.CpSolver()
    
    # Base configuration for standard stores
    solver.parameters.max_time_in_seconds = 60.0 
    solver.parameters.num_search_workers = 8 
    solver.parameters.relative_gap_limit = 0.05 
    
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    # RESCUE LOGIC: If a store (like S035) fails, give it more time and loosen the rules
    if status_name == "UNKNOWN":
        print(f"   🚨 Store {store} requires extended compute. Rerunning with longer time limit...")
        solver.parameters.max_time_in_seconds = 180.0 # 3 Full Minutes
        solver.parameters.relative_gap_limit = 0.10   # Accept slightly wider gap
        status = solver.Solve(model)
        status_name = solver.StatusName(status)

    print(f"   ↳ Solver Status: {status_name}")

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        store_payroll = 0
        for (e, d, s_idx, r), var in X.items():
            if solver.Value(var) == 1:
                e_role = store_emps[store_emps['employee_id']==e]['role'].iloc[0]
                s = get_eligible_shifts(e_role)[s_idx]
                wage = float(store_emps[store_emps['employee_id'] == e]['hourly_wage_mxn'].iloc[0])
                cost = s['duration'] * wage
                store_payroll += cost
                
                optimized_records.append({
                    'store_id': store, 'employee_id': e, 'assigned_role': r, 
                    'date': d, 'shift_start': s['start'], 'shift_end': s['end'], 'duration': s['duration']
                })
        
        store_shortfall = sum(solver.Value(sf) for sf in shortfall_vars)
        total_shortfall_hours += store_shortfall
        total_optimized_payroll += store_payroll
        
        if store_shortfall > 0:
            print(f"   ⚠️ Could not cover {store_shortfall} hours of demand. (Staffing capacity reached)")

# --- 5. REPORT & FILE GENERATION ---
df_optimized = pd.DataFrame(optimized_records)
# Saves DIRECTLY to root folder
df_optimized.to_csv(OUTPUT_FILE, index=False)
baseline_cost = df_baseline[df_baseline['store_id'].isin(demo_stores)]['labor_cost_mxn'].sum()

print(f"\n======================================")
print(f"📉 Baseline Cost: ${baseline_cost:,.2f} MXN")
print(f"✅ Optimized Cost: ${total_optimized_payroll:,.2f} MXN")
print(f"⚠️ Uncoverable Demand: {total_shortfall_hours} Hours")
if baseline_cost > 0:
    print(f"🏆 Real Labor Savings: {((baseline_cost - total_optimized_payroll)/baseline_cost)*100:.2f}%")
print(f"📁 Schedule correctly saved to: {OUTPUT_FILE}")
print(f"======================================")