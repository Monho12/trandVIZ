"""Feature-үүд ирээдүйг "харахгүй" байгааг (leakage-гүй) шалгах жижиг тестүүд.  Ажиллуулах:  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features import make_features  # noqa: E402


def toy():
    # Хоёр сэдэв: A нь 0,1,2,...,39  B нь 100,101,...  -> утга бүр өдрийн дугаартай тэнцүү тул шалгахад амар
    dates = pd.date_range("2024-01-01", periods=40)
    a = pd.DataFrame({"date": dates, "article": "A", "category": "x", "y": np.arange(40, dtype=float)})
    b = pd.DataFrame({"date": dates, "article": "B", "category": "x", "y": 100 + np.arange(40, dtype=float)})
    return make_features(pd.concat([b, a]))  # дараалал холимог байсан ч зөв ажиллах ёстой


def test_lags_look_back():
    f = toy().set_index(["article", "date"])
    row = f.loc[("A", pd.Timestamp("2024-01-21"))]       # y = 20
    assert row["y_0"] == 20 and row["lag_1"] == 19 and row["lag_7"] == 13 and row["lag_14"] == 6


def test_targets_look_forward():
    row = toy().set_index(["article", "date"]).loc[("A", pd.Timestamp("2024-01-21"))]
    assert (row["y_h1"], row["y_h2"], row["y_h3"]) == (21, 22, 23)


def test_rolling_uses_only_past_and_today():
    row = toy().set_index(["article", "date"]).loc[("A", pd.Timestamp("2024-01-21"))]
    assert row["roll_mean_7"] == np.mean(range(14, 21))   # 14..20, 21+ орохгүй
    assert row["roll_max_28"] != row["roll_max_28"] or row["roll_max_28"] <= 20


def test_no_leak_between_articles():
    f = toy()
    first_b = f[f["article"] == "B"].iloc[0]
    assert np.isnan(first_b["lag_1"])            # A-ийн сүүлийн утга B руу орох ёсгүй
    last_a = f[f["article"] == "A"].iloc[-1]
    assert np.isnan(last_a["y_h1"])              # A-ийн ирээдүй B-ийн эхнээс авагдах ёсгүй


def test_no_feature_correlates_perfectly_with_future_only():
    # Feature бүрийг 1 өдрөөр урагш шилжүүлэхэд утга нь өөрчлөгдөхгүй байх ёсгүй (ирээдүйн мэдээлэлгүй)
    f = toy()
    a = f[f["article"] == "A"].set_index("date")
    assert a.loc["2024-01-30", "roll_mean_3"] == np.mean([27, 28, 29])


def test_seasonal_baseline_uses_only_past():
    """seasonal baseline: ŷ(t+h) = y(t+h-7) — t-ээс хойших утга хэзээ ч ашиглагдахгүй."""
    import pandas as pd
    from src.baselines import seasonal_pred
    dates = pd.date_range("2024-01-01", periods=30)
    cl = pd.DataFrame({"article": "A", "date": dates, "y": range(30)})
    feats = cl.rename(columns={"y": "y_0"}).iloc[10:20].reset_index(drop=True)
    for h in (1, 2, 3):
        s = seasonal_pred(feats, cl, h)
        assert (s.to_numpy() == feats["y_0"].to_numpy() + h - 7).all()   # y нь өдрийн дугаар тул t+h-7


def test_category_not_a_model_input():
    """ADR 0005: `category` ("viral" утга) нь ирээдүйг мэдэж сонгосон жагсаалтыг илтгэдэг -> leakage.
    03 notebook-ийг дахин ажиллуулахад чимээгүй буцаж орж ирэхээс сэргийлнэ."""
    import json
    fl = json.loads((Path(__file__).resolve().parents[1] / "data" / "processed" / "feature_list.json").read_text(encoding="utf-8"))
    assert "category" not in fl["features"]
    assert "category" not in fl.get("categorical", [])
    assert len(fl["features"]) == 18
