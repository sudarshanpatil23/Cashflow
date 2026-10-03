from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

old = '''    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_receivables.csv"
    )
'''

new = '''    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_upload_source"
    )
'''

if old not in s:
    raise SystemExit("Runtime company path block not found.")

s = s.replace(old, new, 1)

p.write_text(
    s,
    encoding="utf-8",
)

print("Dashboard company source fixed.")
