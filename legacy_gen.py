import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'data', 'input')
OUTPUT_FILE = os.path.join(BASE_DIR, 'legacy_schedule_sim.csv')

def find_optimal_staffing(demands, target_level):
    """Calculates min staff k needed to meet target service level over an 8h shift."""
    total_demand = sum(demands)
    if total_demand == 0: return 0
    for k in range(1, 30):
        met_demand = sum(min(k, d) for d in demands)
        if (met_demand / total_demand) >= target_level:
            return k
    return 1

def generate_legacy_schedule():
    print("🧱 Simulating Legacy 48-hour Peak-Coverage Schedule...")
    try:
        df_demand = pd.read_csv(os.path.join(INPUT_DIR, 'labor_demand_curve_sim.csv'))
        df_emp = pd.read_csv(os.path.join(INPUT_DIR, 'employees_phase2.csv'))
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    # Phase 1 Manager Targets
    targets = {'Cashier': 0.95, 'Floor': 0.90, 'Stock': 0.85, 'Customer Service': 0.92, 'Supervisor': 0.98}
    shift_defs = [{'name': 'Morning', 'start': 8, 'end': 16}, {'name': 'Evening', 'start': 14, 'end': 22}]
    
    schedule_data = []
    emp_running_hrs = {str(row['employee_id']): 0 for _, row in df_emp.iterrows()}

    for date in sorted(df_demand['date'].unique()):
        for store in df_demand['store_id'].unique():
            store_demand = df_demand[(df_demand['date'] == date) & (df_demand['store_id'] == store)]
            
            for shift in shift_defs:
                shift_data = store_demand[(store_demand['hour'] >= shift['start']) & (store_demand['hour'] < shift['end'])]
                
                for role in store_demand['role'].unique():
                    role_demands = shift_data[shift_data['role'] == role]['required_staff'].tolist()
                    if sum(role_demands) == 0: continue
                    
                    target = targets.get(role, 0.95)
                    needed_k = find_optimal_staffing(role_demands, target)
                    
                    # Pull staff for this store and role
                    potential_staff = df_emp[(df_emp['store_id'] == store) & (df_emp['role'] == role)]
                    assigned = 0
                    
                    for _, emp in potential_staff.iterrows():
                        emp_id = str(emp['employee_id'])
                        # Managers cap out at 56 hours (8 hours of massive OT)
                        if assigned < needed_k and emp_running_hrs[emp_id] < 56:
                            schedule_data.append({
                                'store_id': store, 'employee_id': emp_id, 'assigned_role': role,
                                'date': date, 'shift_start': shift['start'], 'shift_end': shift['end'], 'duration': 8
                            })
                            emp_running_hrs[emp_id] += 8
                            assigned += 1

    pd.DataFrame(schedule_data).to_csv(OUTPUT_FILE, index=False)
    print("✅ Legacy Schedule Created using Phase I Manager Logic.")

if __name__ == "__main__":
    generate_legacy_schedule()