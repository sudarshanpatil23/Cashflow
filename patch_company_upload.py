from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

old = '''        saved_path = save_uploaded_file(
            uploaded_file.name,
            uploaded_bytes,
        )

        file_info = get_file_info(
            saved_path
        )
'''

new = '''        saved_path = save_uploaded_file(
            uploaded_file.name,
            uploaded_bytes,
        )

        runtime_dir = BASE_DIR / "data" / "runtime"
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

        file_info = get_file_info(
            saved_path
        )
'''

if old not in s:
    raise SystemExit(
        "Upload block not found."
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
    "Company upload persistence added."
)
