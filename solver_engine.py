import pandas as pd
from ortools.sat.python import cp_model
import os
import time
import math
import argparse

# --- DYNAMIC PATHING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_FILE = os.path.join(BASE_DIR, 'optimized_schedule.csv') 
PENALTY_RATE = 10000 
VOLATILITY_BUFFER = 1.0

def load_file(name):
    path = os.path.join(INPUT_DIR, name) if not os.path.isabs(name) else name
    if os.path.exists(path): return pd.read_csv(path)
    raise FileNotFoundError(f"Missing {path}")

def get_eligible_shifts(role):
    if 'Supervisor' in role:
        return [{'start': 8, 'end': 16, 'dur': 8}, {'start': 14, 'end': 22, 'dur': 8}]
    return [
        {'start': 8, 'end': 16, 'dur': 8}, {'start': 10, 'end': 18, 'dur': 8},
        {'start': 12, 'end': 20, 'dur': 8}, {'start': 14, 'end': 22, 'dur': 8},
        {'start': 16, 'end': 22, 'dur': 6}, {'start': 17, 'end': 22, 'dur': 5}
    ]

def run_network_optimization(demand_file):
    df_demand = load_file(demand_file)
    df_emp = load_file('employees_phase2.csv')
    
    for df in [df_demand, df_emp]:
        for col in ['store_id', 'role', 'employee_id']:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()
    
    demo_stores = df_demand['store_id'].unique()
    optimized_records = []

    for index, store in enumerate(demo_stores):
        print(f"PROGRESS:{index + 1}/{len(demo_stores)}:{store}", flush=True)
        
        s_demand = df_demand[df_demand['store_id'] == store].to_dict('records')
        s_emps = df_emp[df_emp['store_id'] == store].to_dict('records')
        days = sorted(list(set(d['date'] for d in s_demand)))
        
        model = cp_model.CpModel()
        X = {} 

        for emp in s_emps:
            e = emp['employee_id']
            role = emp['role']
            templates = get_eligible_shifts(role)
            for d in days:
                for s_idx, _ in enumerate(templates):
                    X[(e, d, s_idx)] = model.NewBoolVar(f'x_{e}_{d}_{s_idx}')

        for emp in s_emps:
            e = emp['employee_id']
            templates = get_eligible_shifts(emp['role'])
            
            # 40-Hour Cap
            model.Add(sum(X[(e, d, s_idx)] * templates[s_idx]['dur'] for d in days for s_idx in range(len(templates))) <= 40)
            
            # Max 1 Shift per day & 12-Hour Rest
            for i, d in enumerate(days):
                model.Add(sum(X[(e, d, s_idx)] for s_idx in range(len(templates))) <= 1)
                if i < len(days) - 1:
                    tomorrow = days[i+1]
                    closing_shifts = [idx for idx, s in enumerate(templates) if s['start'] >= 14]
                    opening_shifts = [idx for idx, s in enumerate(templates) if s['start'] < 10]
                    for cs in closing_shifts:
                        for os_idx in opening_shifts:
                            model.AddImplication(X[(e, d, cs)], X[(e, tomorrow, os_idx)].Not())

        # --- THE FIX: ADDING WAGES BACK TO OBJECTIVE ---
        cost_terms = []
        
        # 1. Minimize Payroll Wasted (Prioritize cheaper employees and exact hours)
        for emp in s_emps:
            e = emp['employee_id']
            wage = float(emp['hourly_wage_mxn'])
            templates = get_eligible_shifts(emp['role'])
            for d in days:
                for s_idx, s in enumerate(templates):
                    cost_terms.append(X[(e, d, s_idx)] * int(s['dur'] * wage))

        # 2. Minimize Service Gaps (Heavy Penalty for missing demand)
        demand_map = {}
        for row in s_demand:
            demand_map[(row['date'], row['hour'], row['role'])] = row['required_staff']

        for (date, hour, role), target in demand_map.items():
            if target <= 0: continue
            staff_available = []
            for emp in s_emps:
                if emp['role'] == role:
                    e = emp['employee_id']
                    templates = get_eligible_shifts(role)
                    for s_idx, s in enumerate(templates):
                        if s['start'] <= hour < s['end']:
                            staff_available.append(X[(e, date, s_idx)])
            
            if staff_available:
                shortfall = model.NewIntVar(0, target, f'sf_{date}_{hour}_{role}')
                model.Add(sum(staff_available) + shortfall >= target)
                cost_terms.append(shortfall * PENALTY_RATE)

        # The AI now has to balance cheap wages vs. expensive gap penalties
        model.Minimize(sum(cost_terms))
        
        solver = cp_model.CpSolver()
        # Allows the AI up to 12 seconds to fight for the absolute cheapest cost
        solver.parameters.max_time_in_seconds = 12.0 
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            for emp in s_emps:
                e = emp['employee_id']
                templates = get_eligible_shifts(emp['role'])
                for d in days:
                    for s_idx in range(len(templates)):
                        if solver.Value(X[(e, d, s_idx)]) == 1:
                            s = templates[s_idx]
                            optimized_records.append({
                                'store_id': store, 'employee_id': e, 'assigned_role': emp['role'],
                                'date': d, 'shift_start': s['start'], 'shift_end': s['end'], 'duration': s['dur']
                            })

    pd.DataFrame(optimized_records).to_csv(OUTPUT_FILE, index=False)
    print("DONE", flush=True)

import os
os.makedirs('data/output', exist_ok=True) # Forces Linux to create the folder
# Then your save command:
# df.to_csv('data/output/final_network_schedule.csv', index=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='labor_demand_curve_sim.csv')
    # Use the new distinct name here
    parser.add_argument('--output', type=str, default='final_network_schedule.csv') 
    
    args = parser.parse_args()
    OUTPUT_FILE = os.path.join(BASE_DIR, args.output)
    run_network_optimization(args.input)
