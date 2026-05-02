import pandas as pd
from ortools.sat.python import cp_model
import os
import math

# --- 1. SETUP ---
TARGET_STORE = 'S035'
INPUT_DIR = 'data/input'
PATCH_FILE = 'optimized_S035_patch.csv'
MAIN_OPTIMIZED_FILE = 'optimized_schedule.csv'

print(f"🧩 Generating standalone patch for Store {TARGET_STORE}...")

# --- 2. LOAD DATA ---
def get_path(name):
    p = os.path.join(INPUT_DIR, name)
    return p if os.path.exists(p) else name

try:
    df_demand = pd.read_csv(get_path('labor_demand_curve.csv'))
    df_emp = pd.read_csv(get_path('employees_phase2.csv'))
    df_baseline = pd.read_csv(get_path('current_schedule.csv'))
    
    # Standardize strings
    for df in [df_demand, df_emp, df_baseline]:
        for col in ['store_id', 'role', 'employee_id']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

    store_demand = df_demand[df_demand['store_id'] == TARGET_STORE]
    store_emps = df_emp[df_emp['store_id'] == TARGET_STORE]
    days = sorted(pd.to_datetime(store_demand['date']).dt.strftime('%Y-%m-%d').unique())
except Exception as e:
    print(f"❌ Load Error: {e}")
    exit()

# --- 3. SHIFT TEMPLATE LOGIC ---
def get_eligible_shifts(role):
    templates = []
    if 'Supervisor' in role:
        for start in [8, 10, 12, 14]: templates.append({'start': start, 'end': start + 8, 'duration': 8})
    else:
        for start in [8, 10, 12, 14]: templates.append({'start': start, 'end': start + 8, 'duration': 8})
        for start in [13, 14, 15, 16]:
            for dur in [5, 6]: templates.append({'start': start, 'end': start + dur, 'duration': dur})
    return templates

# --- 4. OPTIMIZE S035 ---
model = cp_model.CpModel()
X = {}

for _, emp in store_emps.iterrows():
    e, r_orig = emp['employee_id'], emp['role']
    allowed = [r_orig]
    if str(emp['is_strike_force']) == '1' and pd.notna(emp['secondary_role']):
        allowed.append(str(emp['secondary_role']))
    
    for d in days:
        for s_idx, _ in enumerate(get_eligible_shifts(r_orig)):
            for r in allowed:
                X[(e, d, s_idx, r)] = model.NewBoolVar(f'x_{e}_{d}_{s_idx}_{r}')

# Rules: 40h Cap & 12h Rest
for _, emp in store_emps.iterrows():
    e = emp['employee_id']
    t = get_eligible_shifts(emp['role'])
    model.Add(sum(X[(e,d,s_idx,r)] * t[s_idx]['duration'] for d in days for s_idx in range(len(t)) for r in [emp['role'], str(emp.get('secondary_role', 'None'))] if (e,d,s_idx,r) in X) <= 40)
    for d in days:
        model.Add(sum(X[(e,d,s_idx,r)] for s_idx in range(len(t)) for r in [emp['role'], str(emp.get('secondary_role', 'None'))] if (e,d,s_idx,r) in X) <= 1)

# Soft Objective
cost_terms = []
for d in days:
    for h in range(8, 22):
        for r in store_demand['role'].unique():
            f = store_demand[(pd.to_datetime(store_demand['date']).dt.strftime('%Y-%m-%d')==d) & (store_demand['hour']==h) & (store_demand['role']==r)]
            if not f.empty:
                target = math.ceil(f['required_staff'].iloc[0])
                staff = [X[(e_id, d, s_idx, r)] for _, emp in store_emps.iterrows() for e_id in [emp['employee_id']] for s_idx, s in enumerate(get_eligible_shifts(emp['role'])) if s['start'] <= h < s['end'] and (e_id, d, s_idx, r) in X]
                shortfall = model.NewIntVar(0, target, f'sf_{d}_{h}_{r}')
                model.Add(sum(staff) + shortfall >= target)
                cost_terms.append(shortfall * 10000)

for (e, d, s_idx, r), var in X.items():
    wage = float(store_emps[store_emps['employee_id'] == e]['hourly_wage_mxn'].iloc[0])
    dur = get_eligible_shifts(store_emps[store_emps['employee_id']==e]['role'].iloc[0])[s_idx]['duration']
    cost_terms.append(var * int(dur * wage))

model.Minimize(sum(cost_terms))
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 180.0 # High priority time
status = solver.Solve(model)

# --- 5. OUTPUT & CALCULATIONS ---
if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    patch_records = []
    for (e, d, s_idx, r), var in X.items():
        if solver.Value(var) == 1:
            s = get_eligible_shifts(store_emps[store_emps['employee_id']==e]['role'].iloc[0])[s_idx]
            patch_records.append({'store_id': TARGET_STORE, 'employee_id': e, 'assigned_role': r, 'date': d, 'shift_start': s['start'], 'shift_end': s['end'], 'duration': s['duration']})
    
    df_patch = pd.DataFrame(patch_records)
    df_patch.to_csv(PATCH_FILE, index=False)
    print(f"✅ Patch generated: {PATCH_FILE}")

    # Cumulative Metrics
    wages_dict = df_emp.set_index('employee_id')['hourly_wage_mxn'].to_dict()
    
    # Cost of S035
    s35_cost = sum(r['duration'] * wages_dict[r['employee_id']] for _, r in df_patch.iterrows())
    
    # Cost of existing 49 stores
    if os.path.exists(MAIN_OPTIMIZED_FILE):
        df_existing = pd.read_csv(MAIN_OPTIMIZED_FILE)
        df_existing = df_existing[df_existing['store_id'] != TARGET_STORE] # Ensure no double count
        existing_cost = sum(r['duration'] * wages_dict.get(str(r['employee_id']).strip(), 0) for _, r in df_existing.iterrows())
    else:
        existing_cost = 0

    total_opt = existing_cost + s35_cost
    total_base = df_baseline['labor_cost_mxn'].sum()

    print(f"\n--- 📊 FINAL CUMULATIVE NETWORK METRICS ---")
    print(f"Total Baseline:  ${total_base:,.2f} MXN")
    print(f"Total Optimized: ${total_opt:,.2f} MXN (Incl. S035 Patch)")
    print(f"Final Savings:   {((total_base - total_opt)/total_base)*100:.2f}%")
else:
    print("❌ Could not solve S035.")