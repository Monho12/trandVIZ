"""src/train.py: сургалт/сонголтын мөрүүд, ялагч сонголт, app/model-ийн экспорт.  Ажиллуулах:  pytest -q"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import train  # noqa: E402


def frame():
    """Гурван сэдэв (а, б, в бүлэг), train/valid/test хугацаа бүрээс нэг нэг өдөр + 2023-07-01-ээс өмнөх нэг өдөр."""
    dates = pd.to_datetime(["2023-06-30", "2023-07-01", "2025-06-01", "2025-08-01", "2026-05-01"])
    split = ["train", "train", "train", "valid", "test"]
    rows = [{"date": d, "split": s, "article": a} for a in ("A", "B", "C") for d, s in zip(dates, split)]
    return pd.DataFrame(rows), pd.Series({"A": "а", "B": "б", "C": "в"})


def test_training_rows_include_v_and_start_2023_07_01():
    """ADR 0009: (в)-ийн train хугацааны мөр сургалтад орно. Хурдны тулд train нь 2023-07-01-ээс (Майк, 2026-11-10)."""
    f, groups = frame()
    tr = f.loc[train.row_sets(f, groups)["train"]]
    assert set(tr["article"]) == {"A", "B", "C"}
    assert set(tr["date"]) == {pd.Timestamp("2023-07-01"), pd.Timestamp("2025-06-01")}


def test_selection_valid_excludes_v_and_test_is_never_used():
    """ADR 0005: алгоритм сонголт (в)-гүй valid дээр. Test нь сургалт, сонголтын аль алинд орохгүй."""
    f, groups = frame()
    rs = train.row_sets(f, groups)
    va = f.loc[rs["valid"]]
    assert set(va["article"]) == {"A", "B"} and set(va["split"]) == {"valid"}
    used = f.loc[rs["train"] | rs["valid"]]
    assert "test" not in set(used["split"])


def test_winner_has_lowest_mean_valid_mae_over_horizons():
    """Сонголт: (в)-гүй valid MAE-ийн h1–h3 дундаж хамгийн бага алгоритм. Нэг horizon-д түрүүлсэн нь хангалтгүй."""
    table = pd.DataFrame([
        ("lightgbm", 1, 0.090), ("lightgbm", 2, 0.150), ("lightgbm", 3, 0.180),   # дундаж 0.1400, h1-д түрүүлнэ
        ("xgboost", 1, 0.095), ("xgboost", 2, 0.140), ("xgboost", 3, 0.175),      # дундаж 0.1367
        ("catboost", 1, 0.099), ("catboost", 2, 0.149), ("catboost", 3, 0.178),   # дундаж 0.1420
    ], columns=["algo", "h", "valid_mae"])
    assert train.select_winner(table) == "xgboost"



@pytest.mark.parametrize("algo", train.ALGOS)
def test_exported_model_predicts_exactly_like_the_trained_one(algo, tmp_path):
    """Вэб (ADR 0008) app/model/-оос ачаалсан model нь сургасантай ЯГ ижил Δ̂ гаргах ёстой, meta.json-д
    algo, 18 feature, learning curve, importance top-10, сургасан огноо байна."""
    rng = np.random.default_rng(0)
    feats = [f"f{i}" for i in range(18)]
    X = pd.DataFrame(rng.normal(size=(400, 18)), columns=feats)
    fitted = {}
    for h in (1, 2, 3):
        y = X["f0"] * h + rng.normal(scale=0.1, size=400)
        fitted[h] = train.fit(algo, {}, X[:300], y[:300], X[300:], y[300:], n_rounds=30)

    train.export(tmp_path, algo, fitted, feats)
    loaded = train.load(tmp_path)

    for h in (1, 2, 3):
        np.testing.assert_array_equal(loaded.predict(X, h), train.predict(fitted[h], X))
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["algo"] == algo and meta["features"] == feats and meta["horizons"] == [1, 2, 3]
    pd.Timestamp(meta["trained_at"])                                         # огноо уншигдана
    assert meta["importance_top10"][0]["feature"] == "f0" and len(meta["importance_top10"]) == 10
    curve = meta["learning_curve"]["h1"]
    assert len(curve["train"]) == len(curve["valid"]) == len(curve["iteration"]) > 0


def _copy_model(dst: Path) -> Path:
    """app/model/-ийн хуулбар (model файлууд + meta.json), тест бүр өөрийнхөө хуулбарыг өөрчилнө."""
    import shutil
    return Path(shutil.copytree(train.MODEL_DIR, dst))


def test_model_hash_is_the_same_for_the_same_files(tmp_path):
    """ADR 0015, 2-р дүрэм: model хувилбар нь файлуудаас тогтмол, давтагдах hash. Хавтасны байршлаас хамаарахгүй."""
    a, b = _copy_model(tmp_path / "a"), _copy_model(tmp_path / "b")
    h = train.model_hash(a)
    assert len(h) == 64 and int(h, 16) >= 0                    # бүтэн sha256 hex
    assert train.model_hash(a) == h == train.model_hash(b)


def test_model_hash_changes_when_calibration_is_rewritten_with_the_same_trained_at(tmp_path):
    """src/calibrate.py нь T ба интервалыг trained_at-ыг өөрчлөхгүйгээр дахин бичдэг тул trained_at хувилбар болохгүй."""
    d = _copy_model(tmp_path / "m")
    before = train.model_hash(d)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    meta["interval"]["h3"]["hi"] += 0.01
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    after = train.model_hash(d)
    assert json.loads((d / "meta.json").read_text(encoding="utf-8"))["trained_at"] == meta["trained_at"]
    assert after != before


def test_model_hash_covers_the_model_files_too(tmp_path):
    """Hash нь meta.json-оос гадна h1–h3 model файлыг бүхэлд нь хамарна."""
    d = _copy_model(tmp_path / "m")
    before = train.model_hash(d)
    f = d / json.loads((d / "meta.json").read_text(encoding="utf-8"))["files"]["h2"]
    f.write_bytes(f.read_bytes() + b"\0")
    assert train.model_hash(d) != before


def test_loaded_model_carries_its_version():
    """Сервер, log (W2), backtest (W4) нэг л функцээр хувилбараа авна: load() нь model_hash-ийг хадгална."""
    m = train.load()
    assert m.version == train.model_hash(train.MODEL_DIR)
    assert train.short_version(m.version) == "v" + m.version[:7]
