import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os  # Added to handle directory creation

def generate_dynamic_weekly_demand():
    # 1. Load the constant store infrastructure
    try:
        df_stores = pd.read_csv('data/input/stores.csv')
    except FileNotFoundError:
        print("❌ Error: stores.csv not found in data/input/")
        return

    # 2. Conceptual Constants (The 'Physics' of your Retail Model)
    format_mult = {'Small': 0.75, 'Medium': 1.00, 'Large': 1.35}
    day_mult = {
        'Sunday': 1.20, 'Monday': 0.85, 'Tuesday': 0.80, 'Wednesday': 0.85, 
        'Thursday': 0.95, 'Friday': 1.15, 'Saturday': 1.30
    }
    productivity = {
        'Cashier': 40, 'Floor': 60, 'Stock': 120, 'Customer Service': 100, 'Supervisor': 250
    }

    # 3. Time Window: Sunday to Saturday
    # We use a dynamic start date to simulate 'Next Week'
    start_date = datetime.now() + timedelta(days=(6 - datetime.now().weekday() + 7) % 7) 
    dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    hours = list(range(8, 23)) # 08:00 - 22:00

    new_demand_rows = []

    # 4. The Dynamic Wave Engine
    for _, store in df_stores.iterrows():
        f_factor = format_mult.get(store['format'], 1.0)
        
        for date_str in dates:
            day_name = datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')
            d_factor = day_mult.get(day_name, 1.0)
            
            # Weekly Jitter: Every week has a slightly different 'vibe' (+/- 15%)
            weekly_noise = np.random.uniform(0.85, 1.15)
            
            for hour in hours:
                # Core Sinusoidal Wave
                base_traffic = 60 + 40 * np.sin(np.pi * (hour - 8) / 14)
                
                # Hourly Jitter: Specific hours vary randomly (+/- 10%)
                hourly_noise = np.random.uniform(0.9, 1.1)
                
                # Peak Multiplier (17:00 - 20:00)
                peak_spike = 1.5 if 17 <= hour <= 20 else 1.0
                
                # Calculate Final Traffic
                total_traffic = base_traffic * f_factor * d_factor * weekly_noise * hourly_noise * peak_spike
                
                # Convert to Staffing Requirements
                for role, divisor in productivity.items():
                    req_staff = int(np.ceil(total_traffic / divisor))
                    if role == 'Supervisor':
                        req_staff = max(1, req_staff)
                        
                    new_demand_rows.append({
                        'store_id': store['store_id'],
                        'date': date_str,
                        'hour': hour,
                        'role': role,
                        'required_staff': req_staff
                    })

    # 5. Output for Universal App Processing
    df_new_week = pd.DataFrame(new_demand_rows)
    
    # --- THE FIX: Force the server to build the folder if it gets confused ---
    os.makedirs('data/input', exist_ok=True)
    
    df_new_week.to_csv('data/input/labor_demand_curve_sim.csv', index=False)
    print(f"✅ Concept-consistent demand generated for week starting {dates[0]}.")

if __name__ == "__main__":
    generate_dynamic_weekly_demand()
