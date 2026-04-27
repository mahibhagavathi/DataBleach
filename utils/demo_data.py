import pandas as pd
import numpy as np

DEMO_DATASETS = {
    "👥 HR Attrition (IBM)": "hr",
}


def load_demo(key: str) -> pd.DataFrame:
    np.random.seed(42)
    if key == "hr":
        return _hr(500)
    return pd.DataFrame()


def _hr(n):
    departments = ["Sales", "R&D", "HR", "sales", "R&d", "hr"]
    education   = ["Bachelor", "Master", "PhD", "bachelor's", "MASTER", "phd"]
    gender      = ["Male", "Female", "male", "M", "F", "FEMALE", "female"]

    rows = []
    for i in range(n):
        rows.append({
            "employee_id":        f"EMP{i:04d}" if i % 40 != 0 else f"EMP{i-1:04d}",
            "age":                int(np.random.randint(22, 60)) if i % 35 != 0 else 150,
            "gender":             str(np.random.choice(gender)),
            "department":         str(np.random.choice(departments)),
            "education":          str(np.random.choice(education)),
            "monthly_income":     float(np.random.randint(2000, 20000)) if i >= 50 else None,
            "years_at_company":   int(np.random.randint(0, 35)) if i % 30 != 0 else -5,
            "job_satisfaction":   int(np.random.randint(1, 5)),
            "attrition":          str(np.random.choice(["Yes", "No", "yes", "NO", "1", "0"])),
            "over_time":          str(np.random.choice(["Yes", "No", "YES", "no"])),
            "performance_rating": int(np.random.randint(1, 5)),
            "job_level":          int(np.random.randint(1, 6)),
            "phone":              f"555-{np.random.randint(1000,9999)}" if i % 15 != 0 else "not provided",
            "email":              f"emp{i}@company.com" if i % 20 != 0 else "invalid-email",
            "currency":           "USD",
        })

    df = pd.DataFrame(rows)
    return df
