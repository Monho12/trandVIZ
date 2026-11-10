"""
Test-ийн НЭГ удаагийн үнэлгээ (issue #7, ADR 0002, 0005).

Загвар (3 алгоритм) ба baseline-уудыг (naive, seasonal, momentum) сэдвийн бүлэг (а)/(б)/(в) тус бүрт test дээр
нэг удаа үнэлж, ADR 0002-ийн шалгуурыг давсан эсэхийг тайлбаргүйгээр тогтооно. Гол дүгнэлт нь (а) дээр.

⚠️ Test-ийг нэг л удаа ажиллуулна. Тоо муу гарсан ч дахин ажиллуулж "сайжруулахгүй".

Энэ модулийн дээд хэсгийн функцүүд цэвэр (pure): файл уншихгүй. `run()` нь өгөгдөл ачаалж, тэдгээрийг дуудна.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import scoring

N_BOOT, BOOT_SEED, CI = 1000, 42, 0.95


def skill_ci(df: pd.DataFrame, n_boot: int = N_BOOT, seed: int = BOOT_SEED, ci: float = CI) -> tuple[float, float, float]:
    """df: [date, err_model, err_naive] (мөр бүрийн |алдаа|). Skill score = 1 − MAE_загвар / MAE_naive ба
    түүний 95% bootstrap интервал, ӨДРӨӨР resample хийсэн (ADR 0002). Нэг өдрийн мөрүүд хоорондоо хамааралтай тул
    мөрөөр resample хийвэл интервал хэт нарийн гарна. Буцаах: (цэгэн үнэлгээ, доод, дээд)."""
    daily = df.groupby("date")[["err_model", "err_naive"]].sum()
    m, n = daily["err_model"].to_numpy(), daily["err_naive"].to_numpy()
    point = 1 - m.sum() / n.sum()
    idx = np.random.default_rng(seed).integers(0, len(daily), size=(n_boot, len(daily)))
    boot = 1 - m[idx].sum(axis=1) / n[idx].sum(axis=1)
    a = (1 - ci) / 2
    lo, hi = np.quantile(boot, [a, 1 - a])
    return float(point), float(lo), float(hi)


def _ranked_days(df: pd.DataFrame) -> pd.DataFrame:
    """Хэмжигдэх сэдэв ≥ 10 байгаа өдрүүдийн хэмжигдэх мөрүүд. Top-10 үргэлж 10 сэдэвтэй (ADR 0004) тул
    цөөн сэдэвтэй бүлэгт ((в), 36 сэдэв) 10-д хүрэхгүй өдрийг precision@10 ба үндсэн хувиас хоёуланг нь хасна."""
    m = df[df["measurable"].fillna(False).astype(bool)]
    n = m.groupby("date")["article"].transform("size")
    return m[n >= scoring.TOP_N]


def _is_up(actual_pct: pd.Series) -> pd.Series:
    return scoring.true_trend(actual_pct) == scoring.UP


def precision_at_10(df: pd.DataFrame, pct_col: str) -> tuple[float, int]:
    """df: [date, article, measurable, pct_col, actual_pct (h3)]. Өдөр бүрийн top-10-ийн (pct_col-оор) хэдэн хувь нь
    үнэн trend ↑ болсон бэ, өдрүүдийн дундаж (ADR 0002). Загварт pct_col = таамагласан pct(h3), momentum-д pct_m.
    Буцаах: (precision@10, тоологдсон өдрийн тоо)."""
    m = _ranked_days(df)
    top = scoring.top10(m, pct_col)
    hit = _is_up(top["actual_pct"]).groupby(top["date"]).mean()
    return float(hit.mean()), int(len(hit))


def base_rate(df: pd.DataFrame) -> float:
    """Үндсэн хувь: тухайн өдрийн хэмжигдэх сэдвүүдийн ↑-ийн эзлэх хувь, өдрүүдийн дундаж (precision@10-тэй ижил өдрүүд)."""
    m = _ranked_days(df)
    return float(_is_up(m["actual_pct"]).groupby(m["date"]).mean().mean())


def direction_accuracy(actual_pct: pd.Series, pred_dir: pd.Series) -> dict:
    """Чиглэлийн нарийвчлал (ADR 0002): ӨСӨХ (бодит pct ≥ +25%) мөрүүдийн хэдэн хувьд pred_dir > 0, БУУРАХ (≤ −20%)
    мөрүүдийн хэдэн хувьд pred_dir < 0 байсан бэ, ТУСАД НЬ. Тогтвортой мөр тоологдохгүй, таамаг 0 бол буруу.
    Загварт pred_dir = sign(Δ̂_h3), momentum-д sign(y_0 − y_{−3})."""
    t = scoring.true_trend(actual_pct)
    d = np.sign(pd.Series(pred_dir, index=t.index))
    rise, fall = t == scoring.UP, t == scoring.DOWN
    return {"rise": float((d[rise] > 0).mean()), "fall": float((d[fall] < 0).mean()),
            "n_rise": int(rise.sum()), "n_fall": int(fall.sum())}


def share_days_better(df: pd.DataFrame) -> float:
    """df: [date, err_model, err_naive]. Test-ийн өдрүүдийн хэдэн хувьд тухайн өдрийн MAE_загвар < MAE_naive байсан бэ
    (ADR 0002, найдвартай байдал). Тэнцүү өдөр "сайн" гэж тоологдохгүй."""
    daily = df.groupby("date")[["err_model", "err_naive"]].mean()
    return float((daily["err_model"] < daily["err_naive"]).mean())


def interval_coverage(delta: pd.Series, delta_hat: pd.Series, lo: float, hi: float) -> float:
    """80% интервалын бодит хамралт: Δ нь [Δ̂ + lo, Δ̂ + hi] дотор (хил орно) байсан мөрийн хувь (ADR 0003).
    Δ-ийн хувьд шалгах нь pct-ийн хувьд шалгахтай ижил (expm1 монотон)."""
    r = np.subtract(delta, delta_hat)
    return float(((r >= lo - 1e-12) & (r <= hi + 1e-12)).mean())


SKILL_MIN = 0.05   # ADR 0002


def verdict(g: dict) -> dict:
    """ADR 0002-ийн шалгуурууд нэг бүлгийн хэмжүүр дээр (тайлбаргүй, тэнцүү бол давсангүй):
    1. h бүрт skill score ≥ 5% БӨГӨӨД bootstrap 95% CI-ийн доод хил > 0;  2. precision@10 > momentum;
    3. ӨСӨХ-ийн чиглэлийн нарийвчлал > momentum.  "pass" = гурвуулаа."""
    skill = {h: bool(s["point"] >= SKILL_MIN - 1e-12 and s["lo"] > 0) for h, s in g["skill"].items()}
    v = {
        "skill": skill,
        "skill_all": all(skill.values()),
        "precision10": bool(g["precision10"]["model"] > g["precision10"]["momentum"]),
        "rise_direction": bool(g["direction"]["model"]["rise"] > g["direction"]["momentum"]["rise"]),
    }
    v["pass"] = v["skill_all"] and v["precision10"] and v["rise_direction"]
    return v


# ---------------------------------------------------------------- Загвар хуудас (app/mock/model.json)

ALGO_NAME = {"lightgbm": "LightGBM", "xgboost": "XGBoost", "catboost": "CatBoost"}


def as_pct(mae_log: float) -> float:
    """Лог MAE-г хувиар: exp(MAE) − 1, "дунджаар хэдэн хувиар зөрдөг вэ" (PLAN, Загвар хуудас; Майк зөвшөөрсөн, 2026-11-10).
    Энэ нь анхаарлын өөрчлөлтийн pct БИШ, зөвхөн алдааны хэмжээг ойлгомжтой болгох хувиргалт."""
    return float(np.expm1(mae_log))


def model_page(meta: dict, group: str = "а") -> dict:
    """meta.json (test-тэй) -> Загвар хуудасны JSON: 3 алгоритм + naive-ийн `group` дээрх test MAE (хувиар),
    ялагч, skill score, ялагчийн learning curve (h3) ба importance top-10."""
    t, algo = meta["test"], meta["algo"]
    g = t["groups"][group]
    keys = list(ALGO_NAME) + ["naive"]
    lc = meta["learning_curve"]["h3"]
    return {
        "asof": t["test_end"], "mock": False, "group": group, "winner": algo,
        "keys": keys, "names": {**ALGO_NAME, "naive": "Өчигдрийнх шиг"},
        "metrics": [{"h": int(h[1:]), **{k: round(as_pct(g["mae"][h][k]) * 100, 1) for k in keys}} for h in g["mae"]],
        "skill": {h: {k: round(v * 100, 1) for k, v in s.items()} for h, s in g["skill"].items()},
        "curve": [{"it": i, "train": tr, "valid": va} for i, tr, va in zip(lc["iteration"], lc["train"], lc["valid"])],
        "best_iter": meta["best_iteration"]["h3"],
        "importance": [{"f": r["feature"], "gain": round(r["share"] * 100)} for r in meta["importance_top10"]],
    }


# ---------------------------------------------------------------- нэг удаагийн test (файл уншина)

# Ялагдсан 2 алгоритмыг app/model/-д хадгалаагүй. Тэдний Optuna-ийн хамгийн сайн trial нь seed 42-ийн санамсаргүй
# (startup) trial #1 байсан (04_model, h бүрт), тиймээс параметрийг яг сэргээж, ИЖИЛ train/valid дээр дахин сургана.
# Сэргээсэн model-ийн valid MAE ба best_iteration-ийг meta.json-ийн valid_table-тэй тулгаж шалгана. Test-ийг ашиглахгүй.
BEST_TRIAL = {"lightgbm": 1, "xgboost": 1}
GROUPS = ("а", "б", "в")
GROUP_NOTES = {
    "а": "гол дүгнэлт: сонгосон 151 сэдэв, сонголтын хазайлт бага",
    "б": "train үед оргилсон вирал: ихэвчлэн оргилын дараах уналт, \"↓\" чиглэл хэт сайн харагдана (гол дүгнэлт биш)",
    "в": "valid/test үед оргилсон вирал: сонголтын хазайлттай (ирээдүйг мэдэж сонгосон), гол дүгнэлт биш",
}


def trial_params(algo: str, number: int) -> dict:
    """TPESampler(seed=SEED)-ийн `number` дугаар trial-ын параметр (startup үед утгаас хамаарахгүй, санамсаргүй)."""
    import optuna
    from src import train

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    st = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=train.SEED))
    for i in range(number + 1):
        t = st.ask()
        p = train.suggest(t, algo)
        st.tell(t, 0.0)
    return p


def test_frame(model, refits: dict, split: str = "test") -> pd.DataFrame:
    """Test-ийн (`split`; valid нь зөвхөн урьдчилсан шалгалтад) бүх мөр: бүлэг, хэмжигдэх эсэх, h бүрийн Δ, Δ̂ (ялагч + 3 алгоритм), naive/seasonal-ийн |алдаа|,
    h3-ын бодит/таамагласан pct, momentum."""
    from src import baselines, train
    from src.features import HORIZONS

    feats = pd.read_parquet(train.P / "features.parquet")
    te = feats[feats["split"] == split].copy()
    cl = pd.read_parquet(train.P / "clean.parquet", columns=["date", "article", "y"])
    cl["measurable"] = scoring.is_measurable(cl)
    te = te.merge(cl[["article", "date", "measurable"]], on=["article", "date"], how="left")
    te["group"] = te["article"].map(train.load_groups())
    for h in HORIZONS:
        y = te[f"y_h{h}"]
        te[f"delta_h{h}"] = y - te["y_0"]
        te[f"hat_model_h{h}"] = model.predict(te, h)
        te[f"hat_{model.meta['algo']}_h{h}"] = te[f"hat_model_h{h}"]
        for algo, fitted in refits.items():
            te[f"hat_{algo}_h{h}"] = train.predict(fitted[h], te[model.meta["features"]])
        te[f"seasonal_h{h}"] = baselines.seasonal_pred(te, cl, h)
    te["actual_pct"] = scoring.pct(te["y_0"], te["y_h3"])
    te["pred_pct"] = scoring.predicted_pct(te["y_0"], te["hat_model_h3"])
    y_m3 = te["y_0"] - te["growth_3"]   # features.parquet-д lag_3 хадгалагдаагүй, growth_3 = y_0 − y_{−3}
    te["mom_pct"] = scoring.momentum_pct(te["y_0"], y_m3)
    te["mom_dir"] = scoring.momentum_direction(te["y_0"], y_m3)
    return te


def group_metrics(d: pd.DataFrame, interval: dict, algos: list[str]) -> dict:
    """Нэг бүлгийн test хэмжүүрүүд (issue #7). d: test_frame-ийн тухайн бүлгийн мөрүүд."""
    from src.features import HORIZONS

    g = {"rows": int(len(d)), "topics": int(d["article"].nunique()), "days": int(d["date"].nunique()),
         "mae": {}, "skill": {}, "days_better": {}, "coverage": {}}
    for h in HORIZONS:
        k, delta = f"h{h}", d[f"delta_h{h}"]
        err = lambda col: (d[col] - delta).abs()   # noqa: E731
        ok = d[f"seasonal_h{h}"].notna()
        g["mae"][k] = {"model": float(err(f"hat_model_h{h}").mean()), "naive": float(delta.abs().mean()),
                       "seasonal": float((d.loc[ok, f"y_h{h}"] - d.loc[ok, f"seasonal_h{h}"]).abs().mean()),
                       **{a: float(err(f"hat_{a}_h{h}").mean()) for a in algos}}
        e = pd.DataFrame({"date": d["date"], "err_model": err(f"hat_model_h{h}"), "err_naive": delta.abs()})
        point, lo, hi = skill_ci(e)
        g["skill"][k] = {"point": point, "lo": lo, "hi": hi}
        g["days_better"][k] = share_days_better(e)
        g["coverage"][k] = interval_coverage(delta, d[f"hat_model_h{h}"], interval[k]["lo"], interval[k]["hi"])
    p_model, n_days = precision_at_10(d, "pred_pct")
    p_mom, _ = precision_at_10(d, "mom_pct")
    g["precision10"] = {"model": p_model, "momentum": p_mom, "base_rate": base_rate(d), "days": n_days}
    meas = d[d["measurable"].fillna(False).astype(bool)]
    g["direction"] = {"model": direction_accuracy(meas["actual_pct"], np.sign(meas["hat_model_h3"])),
                      "momentum": direction_accuracy(meas["actual_pct"], meas["mom_dir"])}
    g["verdict"] = verdict(g)
    return g


def _round(o, nd=5):
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, float):
        return round(o, nd)
    return o


def run(force: bool = False, log=print) -> dict:
    """Test-ийг НЭГ удаа үнэлж, meta.json-д "test" талбар, app/mock/model.json-ийг бичнэ.
    meta.json-д "test" аль хэдийн байвал (force-гүй) ажиллахгүй: test-ийг дахин ажиллуулж тоо "сайжруулахгүй"."""
    import json
    from src import train
    from src.features import HORIZONS

    model = train.load()
    if "test" in model.meta and not force:
        raise RuntimeError("Test аль хэдийн үнэлэгдсэн (meta.json: test). Дахин ажиллуулахгүй (ADR 0002).")

    # 1. Ялагдсан 2 алгоритмыг сэргээх (test-гүй өгөгдөл дээр)
    features = model.meta["features"]
    feats = pd.read_parquet(train.P / "features.parquet")
    feats = feats[feats["split"] != "test"]
    rs = train.row_sets(feats, train.load_groups())
    tr, va = feats[rs["train"]], feats[rs["valid"]]
    recorded = {(r["algo"], r["h"]): r for r in model.meta["valid_table"]}
    refits, repro = {}, {}
    for algo, number in BEST_TRIAL.items():
        params = trial_params(algo, number)
        refits[algo] = {}
        for h in HORIZONS:
            f = train.fit(algo, params, tr[features], tr[f"y_h{h}"] - tr["y_0"], va[features], va[f"y_h{h}"] - va["y_0"])
            refits[algo][h] = f
            rec = recorded[(algo, h)]
            got = train.mae(f, va[features], va[f"y_h{h}"] - va["y_0"])
            repro[f"{algo}_h{h}"] = {"valid_mae": round(got, 5), "recorded": rec["valid_mae"],
                                     "best_iteration": f.best_iteration, "recorded_iteration": rec["best_iteration"]}
            log(f"{algo:9s} h{h}: сэргээсэн valid MAE {got:.5f} (бүртгэсэн {rec['valid_mae']:.5f}), "
                f"{f.best_iteration} iter (бүртгэсэн {rec['best_iteration']})")

    # 2. Test, нэг удаа
    te = test_frame(model, refits)
    algos = list(ALGO_NAME)
    groups = {grp: group_metrics(te[te["group"] == grp], model.meta["interval"], algos) for grp in GROUPS}
    test = {
        "evaluated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "rule": "Test-ийг нэг удаа үнэлсэн (issue #7). Шалгуур ADR 0002: h бүрт skill ≥ 5% ба 95% CI-ийн доод хил > 0; "
                "precision@10 (h3) > momentum; ӨСӨХ-ийн чиглэл > momentum. Гол дүгнэлт (а) дээр (ADR 0005).",
        "test_start": str(te["date"].min().date()), "test_end": str(te["date"].max().date()),
        "bootstrap": {"n": N_BOOT, "seed": BOOT_SEED, "unit": "өдөр", "ci": CI},
        "mae_unit": "лог (y = log1p(анхаарал)), бүх мөр",
        "refit_reproduction": repro,
        "main_group": "а", "notes": GROUP_NOTES,
        "groups": _round(groups),
    }
    meta = {**model.meta, "test": test}
    (train.MODEL_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    page = model_page(meta)
    (train.ROOT / "app" / "mock" / "model.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    report(test, log)
    return {"test": test, "frame": te, "refits": refits}


def report(test: dict, log=print) -> None:
    """Бүлэг бүрийн гол тоо ба ADR 0002-ийн дүгнэлт."""
    yes = lambda b: "ДАВСАН" if b else "ДАВААГҮЙ"   # noqa: E731
    for grp, g in test["groups"].items():
        log(f"\n=== ({grp}) {g['topics']} сэдэв, {g['days']} өдөр, {g['rows']:,} мөр — {test['notes'][grp]}")
        for h, m in g["mae"].items():
            s = g["skill"][h]
            log(f"  {h}: MAE model {m['model']:.4f}  naive {m['naive']:.4f}  seasonal {m['seasonal']:.4f}  "
                f"(LGBM {m['lightgbm']:.4f}, XGB {m['xgboost']:.4f}, CB {m['catboost']:.4f})  "
                f"skill {s['point']:+.1%} [{s['lo']:+.1%}, {s['hi']:+.1%}]  "
                f"өдрийн {g['days_better'][h]:.0%}-д < naive  хамралт {g['coverage'][h]:.1%}")
        p, dm, dn = g["precision10"], g["direction"]["model"], g["direction"]["momentum"]
        log(f"  precision@10: model {p['model']:.1%}  momentum {p['momentum']:.1%}  үндсэн хувь {p['base_rate']:.1%} ({p['days']} өдөр)")
        log(f"  ӨСӨХ: model {dm['rise']:.1%}  momentum {dn['rise']:.1%} (n={dm['n_rise']});  "
            f"БУУРАХ: model {dm['fall']:.1%}  momentum {dn['fall']:.1%} (n={dm['n_fall']})")
        v = g["verdict"]
        log(f"  ADR 0002: skill {yes(v['skill_all'])} {v['skill']};  precision@10 {yes(v['precision10'])};  "
            f"ӨСӨХ {yes(v['rise_direction'])}  ->  {yes(v['pass'])}")


if __name__ == "__main__":
    run()
