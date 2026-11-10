"""app/static/*.js-ийн цэвэр функцийг node-оор дуудах (browser-гүй). test_words, test_listing, test_model_words ашиглана."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
NODE = shutil.which("node")


def call(module: str, name: str, *args):
    """app/static/<module>-ийн <name>(*args)-ийн утга (name нь тогтмол бол түүний утга).
    Аргументыг stdin-ээр дамжуулна: 301 сэдвийн жагсаалт ч багтана."""
    if NODE is None:
        pytest.skip("node алга")
    code = (f"const m = require({json.dumps(str(STATIC / module))}); "
            "const args = JSON.parse(require('fs').readFileSync(0, 'utf8')); "
            f"const v = m[{json.dumps(name)}]; console.log(JSON.stringify(typeof v === 'function' ? v(...args) : v))")
    out = subprocess.run([NODE, "-e", code], input=json.dumps(args), capture_output=True, text=True, check=True).stdout
    return json.loads(out)
