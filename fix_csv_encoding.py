from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

old = '''            receivables = pd.read_csv(
                runtime_company_path
            )
'''

new = '''            try:
                receivables = pd.read_csv(
                    runtime_company_path,
                    encoding="utf-8-sig",
                )

            except UnicodeDecodeError:

                receivables = pd.read_csv(
                    runtime_company_path,
                    encoding="cp1252",
                )
'''

if old not in s:
    raise SystemExit(
        "Company CSV read block not found."
    )

s = s.replace(
    old,
    new,
    1,
)

p.write_text(
    s,
    encoding="utf-8",
)

print(
    "Company CSV encoding fallback added."
)
