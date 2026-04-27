import pandas as pd
import numpy as np

DEMO_DATASETS = {
    "👥 HR Attrition (IBM)": "hr",
}

FIRST_NAMES = [
    "james", "MARY", "John", "patricia", "ROBERT", "jennifer", "Michael",
    "linda", "WILLIAM", "barbara", "david", "Elizabeth", "richard", "SUSAN",
    "joseph", "Jessica", "thomas", "Sarah", "charles", "KAREN", "Priya",
    "rahul", "ANANYA", "vikram", "deepa", "AMIT", "pooja", "SANJAY",
]
LAST_NAMES = [
    "smith", "JOHNSON", "Williams", "brown", "JONES", "garcia", "Miller",
    "Davis", "WILSON", "moore", "taylor", "Anderson", "THOMAS", "jackson",
    "white", "HARRIS", "martin", "Thompson", "PATEL", "sharma", "KUMAR",
    "singh", "Reddy", "MEHTA", "nair", "IYER", "Das", "bose",
]


def load_demo(key: str) -> pd.DataFrame:
    np.random.seed(42)
    if key == "hr":
        return _hr(500)
    return pd.DataFrame()


def _hr(n):
    departments = ["Sales", "R&D", "HR", "sales", "R&d", "hr", "Finance", "finance", "FINANCE"]
    education   = ["Bachelor", "Master", "PhD", "bachelor's", "MASTER", "phd", "High School", "high school"]
    gender      = ["Male", "Female", "male", "M", "F", "FEMALE", "female", "m", "f"]
    job_titles  = ["Manager", "Analyst", "Engineer", "Director", "Associate",
                   "manager", "ANALYST", "engineer", "DIRECTOR", "associate"]

    rng = np.random.default_rng(42)

    rows = []
    for i in range(n):
        fn = np.random.choice(FIRST_NAMES)
        ln = np.random.choice(LAST_NAMES)
        name = f"{fn} {ln}"

        # Duplicate employee IDs every 40 rows
        emp_id = f"EMP-{i:04d}" if i % 40 != 0 else f"EMP-{i-1:04d}"

        # Age: mostly normal, some impossible
        age = int(np.random.randint(22, 60)) if i % 35 != 0 else 150

        # Monthly income: first 50 rows null (high null rate demo)
        income = float(np.random.randint(2000, 20000)) if i >= 50 else None

        # Years at company: some negative
        years = int(np.random.randint(0, 35)) if i % 30 != 0 else -5

        # Phone: mix of formats
        if i % 4 == 0:
            phone = f"({np.random.randint(200,999)}) {np.random.randint(100,999)}-{np.random.randint(1000,9999)}"
        elif i % 4 == 1:
            phone = f"{np.random.randint(2000000000,9999999999)}"
        elif i % 4 == 2:
            phone = f"+91-{np.random.randint(7000000000,9999999999)}"
        else:
            phone = "not provided" if i % 15 == 0 else f"{np.random.randint(100,999)}-{np.random.randint(1000,9999)}"

        # Email: some invalid
        email = f"{fn.lower()}.{ln.lower()}@company.com" if i % 20 != 0 else "invalid-email"

        # Salary band: inconsistent format
        band_num = np.random.randint(1, 6)
        if i % 3 == 0:
            salary_band = f"Band {band_num}"
        elif i % 3 == 1:
            salary_band = f"band{band_num}"
        else:
            salary_band = f"BAND-{band_num}"

        rows.append({
            "employee_id":        emp_id,
            "full_name":          name,
            "age":                age,
            "gender":             str(np.random.choice(gender)),
            "department":         str(np.random.choice(departments)),
            "job_title":          str(np.random.choice(job_titles)),
            "education":          str(np.random.choice(education)),
            "salary_band":        salary_band,
            "monthly_income":     income,
            "years_at_company":   years,
            "job_satisfaction":   int(np.random.randint(1, 5)),
            "attrition":          str(np.random.choice(["Yes", "No", "yes", "NO", "1", "0"])),
            "over_time":          str(np.random.choice(["Yes", "No", "YES", "no"])),
            "performance_rating": int(np.random.randint(1, 5)),
            "job_level":          int(np.random.randint(1, 6)),
            "phone":              phone,
            "email":              email,
            "currency":           "USD",
            "hire_date":          str((pd.Timestamp("2015-01-01") + pd.Timedelta(days=int(np.random.randint(0, 3000)))).date()) if i % 25 != 0 else "01/15/2018",
        })

    df = pd.DataFrame(rows)

    # Inject ~8 exact duplicate rows
    dupes = df.iloc[[10, 25, 50, 75, 100, 150, 200, 250]].copy()
    df = pd.concat([df, dupes], ignore_index=True)

    return df
