"""Docker image (#9, ADR 0008/0010): Dockerfile, runtime хамаарал, repo-д нууц token алга.  pytest -q"""
import ast
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PORT = 7860   # Dockerfile-ийн порт (README: docker run -p 7860:7860)
DIST_FOR_MODULE = {"xgboost": "xgboost-cpu"}   # import нэр != pip багцын нэр
HF_TOKEN = re.compile(rb"hf_[A-Za-z0-9]{30,}")   # Hugging Face access token-ий хэлбэр


def test_dockerfile_serves_app_port_and_ships_model_and_starting_cache():
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cmd = re.search(r"^CMD\s+(.+)$", df, re.M).group(1)
    assert "app.main:app" in cmd and f'"{APP_PORT}"' in cmd and '"0.0.0.0"' in cmd
    copied = re.findall(r"^COPY\s+(?:--\S+\s+)*(\S+)\s+\S+$", df, re.M)
    assert {"app/", "src/", "data/"} <= set(copied)   # app/model/ ба data/processed/ (#8-ийн эхлэх cache)
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ignored = {p.strip().strip("/") for p in lines if p.strip() and not p.lstrip().startswith("#")}
    assert not ignored & {"app", "app/model", "data", "data/processed", "src"}
    assert {"data/live", "data/raw", ".git"} <= ignored


def third_party_imports(files) -> set[str]:
    mods = set()
    for f in files:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return mods - set(sys.stdlib_module_names) - {"src", "app"}


def test_image_requirements_cover_every_server_import():
    reqs = {re.split(r"[=<>~\s\[]", line.strip())[0].lower()
            for line in (ROOT / "requirements-app.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}
    imported = third_party_imports([ROOT / "app" / "main.py", *(ROOT / "src").glob("*.py")])
    assert {"catboost", "fastapi", "pandas"} <= imported   # скан ажиллаж байгаа эсэх
    missing = {m for m in imported if DIST_FOR_MODULE.get(m, m) not in reqs}
    assert not missing, f"requirements-app.txt-д алга: {sorted(missing)}"


def test_no_hugging_face_token_in_repo_files():
    # bytes хэрэгтэй (binary файл ч шалгана) тул git() helper биш
    files = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
    leaks = [f.decode() for f in files if f and (ROOT / f.decode()).is_file()
             and HF_TOKEN.search((ROOT / f.decode()).read_bytes())]
    assert not leaks, f"HF token шиг мөр олдлоо (тэр даруй revoke хий): {leaks}"
