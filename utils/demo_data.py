import pandas as pd
import numpy as np

DEMO_DATASETS = {
    "👥 HR Attrition (IBM)": "hr",
}

FIRST_NAMES = ["James", "mary", "JOHN", "Patricia", "robert", "JENNIFER",
               "Michael", "linda", "WILLIAM", "barbara", "Priya", "rahul",
               "ANANYA", "vikram", "deepa", "AMIT", "pooja", "sanjay"]
LAST_NAMES  = ["smith", "JOHNSON", "Williams", "brown", "JONES", "garcia",
               "Miller", "Davis", "WILSON", "moore", "PATEL", "sharma",
               "KUMAR", "singh", "Reddy", "mehta", "NAIR", "iyer"]


def load_demo(key: str) -> pd.DataFrame:
    np.random.seed(42)
    if key == "hr":
        return _hr(500)
    return pd.DataFrame()


def _hr(n):
    # Inconsistent representations of the SAME category — this is the data quality issue
    departments = ["Sales", "sales", "SALES",
                   "R&D", "r&d", "R and D",
                   "HR", "hr", "H.R.",
                   "Finance", "finance", "FINANCE"]

    job_titles  = ["Manager", "manager", "MANAGER",
                   "Analyst", "analyst", "ANALYST",
                   "Engineer", "engineer", "ENGINEER",
                   "Director", "director", "DIRECTOR"]

    education   = ["Bachelor", "bachelor", "BACHELOR",
                   "Master", "master", "MASTER",
                   "PhD", "phd", "PHD",
                   "High School", "high school", "HIGH SCHOOL"]

    # Gender: only male/female but inconsistent format
    gender = ["Male", "male", "MALE", "Female", "female", "FEMALE"]

    rows = []
    for i in range(n):
        fn   = np.random.choice(FIRST_NAMES)
        ln   = np.random.choice(LAST_NAMES)
        name = f"{fn} {ln}"  # mixed case e.g. "mary JOHNSON" or "JOHN smith"

        emp_id = f"EMP-{i:04d}" if i % 40 != 0 else f"EMP-{i-1:04d}"  # duplicate IDs

        # Age: realistic range with some clearly wrong entries
        if i % 60 == 0:
            age = np.random.choice([0, 999, -3])   # clearly bad data
        else:
            age = int(np.random.randint(22, 58))

        # Monthly income: realistic by job level — no impossible outliers
        job_lvl = int(np.random.randint(1, 6))
        base_income = {1: 3000, 2: 5000, 3: 8000, 4: 12000, 5: 18000}
        income = float(int(base_income[job_lvl] + np.random.randint(-500, 500)))
        income = None if i < 40 else income   # first 40 rows null

        # Years at company: realistic 0-35, with occasional clearly bad values
        if i % 80 == 0:
            years = np.random.choice([75, 99, -1])  # clearly bad
        else:
            years = int(np.random.randint(0, 36))

        # Phone: 4 string formats all meaning the same thing — stored as strings, never floats
        area = np.random.randint(200, 999)
        mid  = np.random.randint(100, 999)
        last = np.random.randint(1000, 9999)
        r = i % 4
        if r == 0:
            phone = f"({area}) {mid}-{last}"           # (321) 456-7890
        elif r == 1:
            phone = f"+1-{area}-{mid}-{last}"          # +1-321-456-7890
        elif r == 2:
            phone = f"+1{area}{mid:03d}{last}"         # +13214567890
        else:
            phone = "not provided" if i % 20 == 0 else f"{area}{mid:03d}{last}"  # 3214567890

        # Hire date: mixed formats
        base_date = pd.Timestamp("2015-01-01") + pd.Timedelta(days=int(np.random.randint(0, 3000)))
        if i % 3 == 0:
            hire_date = base_date.strftime("%Y-%m-%d")   # ISO
        elif i % 3 == 1:
            hire_date = base_date.strftime("%d/%m/%Y")   # UK format
        else:
            hire_date = base_date.strftime("%B %d, %Y")  # e.g. "March 15, 2019"

        # Email: some invalid
        email = f"{fn.lower()}.{ln.lower()}@company.com" if i % 20 != 0 else "invalid-email"

        # Salary band: same band written 3 different ways
        band_num = job_lvl
        band = np.random.choice([f"Band {band_num}", f"band{band_num}", f"BAND-{band_num}"])

        rows.append({
            "employee_id":        emp_id,
            "full_name":          name,
            "age":                age,
            "gender":             str(np.random.choice(gender)),
            "department":         str(np.random.choice(departments)),
            "job_title":          str(np.random.choice(job_titles)),
            "education":          str(np.random.choice(education)),
            "salary_band":        band,
            "monthly_income":     income,
            "years_at_company":   years,
            "job_satisfaction":   int(np.random.randint(1, 5)),
            "attrition":          str(np.random.choice(["Yes", "No", "yes", "NO", "1", "0"])),
            "over_time":          str(np.random.choice(["Yes", "No", "YES", "no"])),
            "performance_rating": int(np.random.randint(1, 5)),
            "job_level":          job_lvl,
            "phone":              phone,
            "email":              email,
            "hire_date":          hire_date,
            "currency":           "USD",
        })

    df = pd.DataFrame(rows)

    # Inject 8 exact duplicate rows
    dupes = df.iloc[[10, 25, 50, 75, 100, 150, 200, 250]].copy()
    df = pd.concat([df, dupes], ignore_index=True)
    return df
