import pandas as pd
from ortools.sat.python import cp_model
import os
import time
import argparse

# --- DYNAMIC PATHING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'output')
PENALTY_RATE = 10000 
VOLATILITY_BUFFER = 1.0

def load_file(filename):
    # Safe pathing for Linux
    path = os.path.join(INPUT_DIR, filename) 
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    return pd.read_csv(path)

def get_eligible_shifts(role):
    if 'Supervisor' in role:
        return [{'start': 8, 'end': 16, 'dur': 8}, {'start': 14, 'end': 22, 'dur': 8}]
    return [
        {'start': 8, 'end': 16, 'dur': 8}, {'start': 10, 'end': 18, 'dur': 8},
        {'start': 12, 'end': 20, 'dur': 8}, {'start': 14, 'end': 22, 'dur': 8},
        {'start': 16, 'end': 22, 'dur': 6}, {'start': 17, 'end': 22, 'dur': 5}
    ]

def run_network_optimization(demand_file, output_filename):
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

        # --- WAGE & PENALTY OBJECTIVE ---
        cost_terms = []
        
        # 1. Minimize Payroll Wasted
        for emp in s_emps:
            e = emp['employee_id']
            wage = float(emp['hourly_wage_mxn'])
            templates = get_eligible_shifts(emp['role'])
            for d in days:
                for s_idx, s in enumerate(templates):
                    cost_terms.append(X[(e, d, s_idx)] * int(s['dur'] * wage))

        # 2. Minimize Service Gaps
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

        model.Minimize(sum(cost_terms))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 12.0 
        
        # --- THE HACK: FORCE IT TO LOOK LIKE IT IS "THINKING" ---
        start_time = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - start_time
        
        solver = cp_model.CpSolver()
        # Give the AI up to 25 seconds to fight for the absolute cheapest cost
        solver.parameters.max_time_in_seconds = 25.0 
        
        # --- THE HACK: FORCE IT TO LOOK LIKE IT IS "THINKING" ---
        start_time = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - start_time
        
        # If you want to force the presentation to take longer, increase the sleep timer too:
        # This forces the app to "think" for at least 5 seconds per store if it solves it too fast.
        if solve_time < 8.0: 
            time.sleep(8.0 - solve_time)
        
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

    # --- FOLDER CREATION & SAVING (FIXED) ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_path = os.path.join(OUTPUT_DIR, output_filename)
    pd.DataFrame(optimized_records).to_csv(final_path, index=False)
    print("DONE", flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, default='labor_demand_curve_sim.csv')
    parser.add_argument('--output', type=str, default='final_network_schedule.csv') 
    
    args = parser.parse_args()
    run_network_optimization(args.input, args.output)
