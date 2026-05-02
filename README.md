# ⚙️ Aivena Workforce AI: Executive Control Center
**Project:** Latin Leap Workforce AI Deployment  
**Developer:** Dhruvil Shah  
**Status:** Phase III Completed (Production-Ready Simulation)

## 📌 Executive Summary
Aivena Workforce AI is a dynamic, mathematically rigorous optimization engine designed to solve the structural retail conflict between fluctuating customer foot traffic ("The Wave") and rigid labor scheduling ("The Brick"). 

Built for the impending Mexican labor reforms, this system transitions workforce management from a manual, 48-hour "peak-coverage" model to an algorithmic, 40-hour "demand-driven" model. By utilizing Google OR-Tools (CP-SAT), the engine guarantees 100% legal compliance while autonomously minimizing payroll waste and eliminating customer service gaps.

---

## 🚀 The Phased Evolution

### Phase I: Seed & Structure (The Baseline)
Establishment of the static operational footprint.
* **The Network (`stores.csv`):** A rigid 50-store network with varying formats (Small, Medium, Large) and distinct baseline traffic capacities.
* **The Roster (`employees.csv`):** A synthesized database of 4,000+ employees, tracking individual roles (Cashier, Floor, Stock, Supervisor), hourly wages, and maximum hour caps.

### Phase II: The Rules of Engagement (Constraint Modeling)
Encoding strict legal and operational physics into the logic layer.
* **The 40-Hour Cap:** Hard limits enforced per employee to prevent illegal overtime leakage.
* **Worker Wellness (No Clopenings):** Algorithmic enforcement of mandatory 12-hour rest periods between shifts.
* **The Strike Force:** 20% of the workforce deployed as cross-trained support to protect peak revenue periods.
* **Shift Fluidity:** Replacing legacy 8-hour rigid blocks with variable 5-hour, 6-hour, and 8-hour demand-anchored slots.

### Phase III: The Control Center (Live Deployment)
The transition from static scripts to a live, interactive Streamlit application deployed via a "Flattened Data Architecture" for cloud stability.
* **Dynamic Demand Engine:** Simulates rigorous, week-long customer traffic forecasts.
* **Deep AI Optimization:** Deploys a Google CP-SAT solver to process trillions of shift combinations, balancing the cost of employee wages against heavy mathematical penalties for missing customer demand.
* **Executive Dashboard:** Real-time comparative analytics (Legacy vs. AI) tracking net payroll savings, network labor utilization, and service level security.

---

## 🗂️ Flat Architecture & Pipeline
To ensure flawless execution on cloud environments (like Streamlit Community Cloud), the application uses a flat directory structure. The pipeline executes sequentially:

1. `universal_app.py` ➔ The Streamlit UI and master pipeline launcher.
2. `demand_gen.py` ➔ Generates the mathematical traffic wave for the fixed network.
3. `legacy_gen.py` ➔ Calculates the financial baseline using human-manager logic.
4. `solver_engine.py` ➔ The OR-Tools AI that crunches combinations to find the absolute minimum cost schedule.
5. `impact_analyzer.py` ➔ Crashes the Legacy and AI schedules against the demand wave to extract ROI.

---

## 💻 Installation & Local Usage

**1. Clone the repository:**
```bash
git clone [https://github.com/sdhruvil2610-ai/workforce-ai.git](https://github.com/sdhruvil2610-ai/workforce-ai.git)
cd workforce-ai
