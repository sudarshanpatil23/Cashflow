from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

bad_block = '''        runtime_dir = BASE_DIR / "data" / "runtime"
        runtime_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        runtime_company_file = (
            runtime_dir / "company_upload_source"
        )
        runtime_company_file.write_bytes(
            uploaded_bytes
        )

'''

s = s.replace(
    bad_block,
    "",
    1,
)

s = s.replace(
    '''    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_upload_source"
    )
''',
    '''    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_receivables.csv"
    )
''',
    1,
)

p.write_text(
    s,
    encoding="utf-8",
)

print("PDF/CSV source handling fixed.")
