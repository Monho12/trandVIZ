"""
Давтамжийн тоог дахин гаргах скрипт (#54): ADR 0016, 0019–0022, 0026, 0027-д бичигдсэн тоонууд нэг ажиллуулалтаар.

Мөр: `src/calibrate.valid_frame` ((в)-гүй valid, хэмжигдэх сэдэв, ADR 0004/0005). Test-ийг ашиглахгүй (ADR 0002).
Тодорхойлолт (ADR 0021): дүгнэлт = Anomaly сэдвийн таамагласан pct (h3) ≤ −10% → унтрах, бусад → үргэлжлэх;
бодит үр дүн = h3 өдрийн (asof+3) бодит pct ≤ −10% → унтарсан.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import cycle, scoring, situation  # noqa: E402
from src.features import HORIZONS  # noqa: E402


def faded(actual_pct_h3) -> np.ndarray:
    """Бодит үр дүн (ADR 0021): h3 өдрийн бодит pct ≤ −10% → унтарсан. "3 өдрийн дотор аль нэг өдөр" биш."""
    with np.errstate(invalid="ignore"):
        return situation.HELD["fade"](np.asarray(actual_pct_h3, dtype=float))


def per_day(mask, dates: pd.Series, days: pd.Index) -> pd.Series:
    """Өдөр бүрт mask-ийн тоо, df-д байгаа бүх өдрөөр (мөргүй өдөр 0)."""
    return pd.Series(np.asarray(mask, dtype=int), index=dates.to_numpy()).groupby(level=0).sum().reindex(days, fill_value=0)


def verdict_numbers(df: pd.DataFrame) -> dict:
    """#1–#5. df: [date, anomaly, pred_pct, actual_pct] (pct нь h3), бүх мөр (Anomaly-гүй өдөр ч тоологдоно)."""
    days = pd.Index(df["date"].unique())
    a = df[df["anomaly"].fillna(False).astype(bool)]
    v = situation.verdict(a["pred_pct"], np.ones(len(a), bool))
    cont = v == "continue"
    held = ~faded(a["actual_pct"])
    k = per_day(cont, a["date"], days)
    return {"days": len(days), "anomalies": len(a), "continue": int(cont.sum()),
            "anomalies_per_day": len(a) / len(days), "faded_share": float(1 - held.mean()),
            "continue_per_day": cont.sum() / len(days), "continue_share": float(cont.mean()),
            "continue_held": float(held[cont].mean()), "base_held": float(held.mean()),
            "days_zero_continue": int((k == 0).sum()), "days_one_continue": int((k == 1).sum())}


def strong_numbers(df: pd.DataFrame, T: float) -> dict:
    """#6, #7 (ADR 0026). df: [date, anomaly, pred_pct, cycle].
      pct_ge_T  таамагласан pct ≥ T, мөчлөгийн өсөлт ОРСОН (#6, ADR 0026-ийн хуучин "~3.8")
      strong    **Хүчтэй өсөлтийн таамаг** (CONTEXT.md) = pct ≥ T ба мөчлөгийн өсөлт биш (ADR 0019): сайтын тод тоо
    "Тод зүйлгүй өдөр" = Хүчтэй өсөлтийн таамаг ч, Anomaly-ийн "үргэлжлэх" (тод үг) ч 0."""
    days = pd.Index(df["date"].unique())
    p, c = df["pred_pct"].to_numpy(float), df["cycle"].to_numpy(float)
    ge_T = p >= T
    strong = ge_T & ~cycle.is_cyclical_rise(p, c)
    cont = situation.verdict(p, df["anomaly"].fillna(False).astype(bool)) == "continue"
    ns, nc = per_day(strong, df["date"], days), per_day(cont, df["date"], days)
    return {"days": len(days), "rows": len(df), "pct_ge_T": int(ge_T.sum()), "strong": int(strong.sum()),
            "pct_ge_T_per_day": ge_T.sum() / len(days), "pct_ge_T_share": float(ge_T.mean()),
            "strong_per_day": strong.sum() / len(days), "strong_share": float(strong.mean()),
            "days_zero_strong": int((ns == 0).sum()), "days_nothing_bold": int(((ns == 0) & (nc == 0)).sum())}


def excess_hit(actual_pct, cyc) -> np.ndarray:
    """Бодит илүүдэл ≥ +10% (ADR 0019). Мөчлөг тодорхойгүй бол False."""
    with np.errstate(invalid="ignore"):
        return cycle.excess(actual_pct, cyc) >= cycle.EXCESS_BAND


def excess_hit_rate(actual_pct, cyc) -> float:
    """Бодит илүүдэл ≥ +10% болсон хувь, мөчлөг мэдэгдсэн мөрүүд дээр (src/situation.outcome-той ижил хүрээ)."""
    e = cycle.excess(actual_pct, cyc)
    defined = np.isfinite(e)
    return float(np.mean(e[defined] >= cycle.EXCESS_BAND))


def interval_widening(df: pd.DataFrame, interval: dict) -> dict:
    """#11 (ADR 0027). df: [y_0, delta_hat_h1..h3]; interval: meta.json-ийн "interval". Мөр бүрт 80% интервалын pct-ийн
    өргөн (hi − lo, сайтын зурдаг хэмжээ) h1 ≤ h2 ≤ h3 байх хувь. log_width = h бүрийн лог хуваарийн тогтмол өргөн."""
    w = []
    for h in HORIZONS:
        lo, hi = scoring.interval_pct(df["y_0"], df[f"delta_hat_h{h}"], interval[f"h{h}"]["lo"], interval[f"h{h}"]["hi"])
        w.append(np.asarray(hi - lo, dtype=float))
    ok = (w[0] <= w[1]) & (w[1] <= w[2])
    return {"rows": len(df), "share_widening": float(ok.mean()),
            "share_h1_le_h2": float((w[0] <= w[1]).mean()), "share_h2_le_h3": float((w[1] <= w[2]).mean()),
            "log_width": {f"h{h}": round(interval[f"h{h}"]["hi"] - interval[f"h{h}"]["lo"], 5) for h in HORIZONS}}


LEVEL_DAYS = 28   # "28 өдрийн медиан": t−27 … t


def normal_levels(cl: pd.DataFrame) -> pd.DataFrame:
    """#12-ийн naive "ердийн түвшин рүүгээ буцна" дүрмийн түвшин, y = log1p(анхаарал) хуваарьт. cl: [article, date, y]
    (сэдэв бүрт өдөр тутмын, дутуугүй). Буцаах: cl-ийн index-тэй
      level_28    t−27 … t өдрийн y-ийн медиан (28 цэг бүрэн)
      level_0017  ADR 0017-ийн ердийн түвшин: t−59 … t−7 өдрийн y-ийн медиан, ≥ 28 цэг (src/anomaly.py-ийн цонх)"""
    from src.anomaly import MIN_POINTS, WINDOW_FROM, WINDOW_TO

    d = cl.sort_values(["article", "date"])
    g = d.groupby("article", observed=True, sort=False)["y"]
    out = pd.DataFrame(index=d.index)
    out["level_28"] = g.transform(lambda s: s.rolling(LEVEL_DAYS, min_periods=LEVEL_DAYS).median())
    span = WINDOW_FROM - WINDOW_TO + 1
    out["level_0017"] = g.transform(lambda s: s.shift(WINDOW_TO).rolling(span, min_periods=MIN_POINTS).median())
    return out.reindex(cl.index)


def same_n_list(df: pd.DataFrame, pct_col: str, n_per_day: pd.Series) -> pd.DataFrame:
    """Давж өсөх жагсаалтын дүрэм (ADR 0019: Rising, мөчлөгийн өсөлт биш, pct-ээр) өөр таамгаар (pct_col), өдөр бүр
    n_per_day[өдөр] мөр (model-ийн жагсаалттай ижил N, ADR 0020-ийн харьцуулалт). n_per_day-д байхгүй өдөр 0.
    df: [date, article, pct_col, cycle] (хэмжигдэх мөрүүд)."""
    p, c = df[pct_col].to_numpy(float), df["cycle"].to_numpy(float)
    keep = (p >= scoring.RISING) & ~cycle.is_cyclical_rise(p, c)
    r = df[keep].sort_values(["date", pct_col, "article"], ascending=[True, False, True])
    rank = r.groupby("date").cumcount() + 1
    return r[rank.to_numpy() <= r["date"].map(n_per_day).fillna(0).to_numpy()].reset_index(drop=True)


def auc(score, label) -> float:
    """ROC AUC (Mann–Whitney): санамсаргүй эерэг мөр сөрөг мөрөөс өндөр оноотой байх магадлал, тэнцвэл ½."""
    s, y = pd.Series(np.asarray(score, dtype=float)), np.asarray(label, dtype=bool)
    r = s.rank(method="average").to_numpy()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


SHARE_STEP = 0.05


def total_ratio(total: pd.DataFrame) -> pd.Series:
    """Өдөр бүрийн нийт уншилт ÷ өмнөх 28 өдрийн медиан (src/live.complete_days-ийн суурь), date index-тэй.
    Суурь бүрэн биш (< 28 өмнөх өдөр) өдрүүд орохгүй."""
    t = total.sort_values("date").set_index("date")["total_views"].astype(float)
    return (t / t.shift(1).rolling(28, min_periods=28).median()).dropna()


def article_coverage(pv: pd.DataFrame) -> pd.Series:
    """Өдөр бүрт уншилттай сэдвийн тоо (views > 0: API 0 уншилтыг буцаадаггүй) ÷ өмнөх өдрийн бүх мөртэй сэдвийн тоо
    (cache-д 0 уншилттай мөр ч бий). src/live.last_covered_day-ийн харьцаа."""
    seen = pv[pv["views"] > 0].groupby("date")["article"].nunique().sort_index()
    rows = pv.groupby("date")["article"].nunique().reindex(seen.index)
    return (seen / rows.shift(1)).dropna()


def share_threshold(ratios, step: float = SHARE_STEP) -> float:
    """Бүх бүрэн өдрийн харьцаанаас ХАТУУ доор байх step-ийн хамгийн их үржвэр. Хатуу: нийт уншилтын шалгалт
    (`live.complete_days`) "> босго" бол бүрэн гэж үздэг (сэдвийн шалгалт `last_covered_day` нь "≥ босго")."""
    lo = float(np.min(ratios))
    k = np.ceil(round(lo / step, 9)) - 1
    return round(float(k * step), 4)


def partial_day_flips(df: pd.DataFrame, x: float) -> dict:
    """Нэг өдрийн өгөгдөл x-ээр дутуу байсан бол (хожим x-ээр өссөн, ADR 0016 8-р зүйл) тэр өдрийн хэдэн Anomaly (z ≥ 3)
    тэмдэг өөрчлөгдөх байсан бэ, өдөрт. df: [date, attention, y_0, z, sigma, anomaly], sigma = z-ийн хуваагч (лог).
    z-ийн цонх t−59 … t−7 тул тэр өдрийн y л өөрчлөгдөнө. Хоёр чиглэл:
      down  сэдвүүдийн уншилт дутуу (анхаарал ÷ (1 + x)): Anomaly алга болно
      up    нийт уншилт дутуу (анхаарал × (1 + x)): худал Anomaly гарна"""
    from src.anomaly import Z_ANOMALY

    days = df["date"].nunique()
    att, y, z, s = (df[c].to_numpy(float) for c in ("attention", "y_0", "z", "sigma"))
    was = df["anomaly"].fillna(False).astype(bool).to_numpy()
    out = {}
    for key, k in (("down", 1 / (1 + x)), ("up", 1 + x)):
        with np.errstate(invalid="ignore"):
            now = (z + (np.log1p(att * k) - y) / s) >= Z_ANOMALY
        out[key] = float((now != was).sum() / days)
    return out


def tolerated_shortfall(flips: dict, max_flips: float, direction: str = "up") -> float | None:
    """flips: {x: partial_day_flips}. `direction`-ийн тоо max_flips-ээс хэтрэхгүй хамгийн их x. Байхгүй бол None.
    ADR 0016-ийн 8-р зүйл НИЙТ уншилтын өсөлтийг шалгадаг тул "up" (нийт уншилт дутуу байсан) чиглэл."""
    ok = [x for x, f in flips.items() if f[direction] <= max_flips]
    return max(ok) if ok else None


SEED, BOOT_N = 54, 2000


def day_bootstrap_diff(a: pd.DataFrame, b: pd.DataFrame, n: int = BOOT_N, seed: int = SEED) -> dict:
    """a, b: [date, hit] (хоёр жагсаалтын мөр). Нийлүүлсэн хувийн зөрүү a − b ба өдрөөр (хос) bootstrap-ийн 95% интервал:
    өдрүүдийг буцааж сонгоод, тэр өдрүүдийн мөрийг жагсаалт бүрт нийлүүлж хувийг тооцно. Тогтмол seed."""
    days = pd.Index(sorted(set(a["date"]) | set(b["date"])))
    sums = [pd.DataFrame({"k": d.groupby("date")["hit"].sum(), "n": d.groupby("date").size()}).reindex(days, fill_value=0)
            for d in (a, b)]
    (ka, na), (kb, nb) = ((s["k"].to_numpy(float), s["n"].to_numpy(float)) for s in sums)
    idx = np.random.default_rng(seed).integers(0, len(days), size=(n, len(days)))
    with np.errstate(invalid="ignore", divide="ignore"):
        diffs = ka[idx].sum(1) / na[idx].sum(1) - kb[idx].sum(1) / nb[idx].sum(1)
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    return {"diff": float(ka.sum() / na.sum() - kb.sum() / nb.sum()), "lo": float(lo), "hi": float(hi), "n_boot": n, "seed": seed}


# ================================================================ өгөгдөл ачаалах ба бүх тоо (нэг ажиллуулалт)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT_DIR = ROOT / "docs" / "numbers"
SHORTFALL_GRID = tuple(round(0.005 * k, 3) for k in range(1, 21))   # 0.5% … 10%
MAX_FLIP_SHARE = 0.05   # #13: дутуу өдөр тэр өдрийн Anomaly-ийн ≤ 5%-ийг л өөрчлөх ёстой (Claude-ийн санал, ADR 0016)


@dataclass
class Frames:
    model: object                 # train.LoadedModel
    raw: object                   # live.RawCache (data/processed)
    cl: pd.DataFrame              # clean.clean_frame (бүх сэдэв, бүх өдөр)
    cl_anomaly: pd.Series         # cl-ийн index-тэй Anomaly (z ≥ 3), бүх сэдэв (нүүрний тоолол, #10)
    valid: pd.DataFrame           # calibrate.valid_frame + Anomaly, мөчлөг, код, бодит pct (h3); хэмжигдэх ба хэмжигдэхгүй


def load() -> Frames:
    """data/processed-оос (git-д байгаа) санах ойд: `serve.clean_chunks` нь сэдвээр хэсэглэсэн `clean.clean_frame` тул
    `python -m src.clean`-ийн clean.parquet-тэй ижил, features нь `features.frame` (= `python -m src.features`).
    Мөр, нэмэлт баганууд нь tests/test_situation.py-ийн `valid` fixture-тэй ижил."""
    from src import anomaly, calibrate, features, live, serve, train

    model = train.load()
    raw = live.RawCache.load(PROCESSED)
    cl = pd.concat(list(serve.clean_chunks(raw)), ignore_index=True)
    va = calibrate.valid_frame(model, features.frame(cl), cl)
    an = anomaly.score(cl)
    extra = cl[["article", "date", "y", "attention"]].assign(
        z=an["z"].to_numpy(), anomaly=an["anomaly"].to_numpy(), sigma=np.log1p(an["typical_pct"].to_numpy()),
        cycle=cycle.cycle(cl).to_numpy())
    extra = pd.concat([extra, situation.recent_peak(extra), normal_levels(extra)], axis=1).drop(columns="y")
    va = va.merge(extra, on=["article", "date"], how="left")
    total = cl.drop_duplicates("date")[["date", "total_views"]]
    va["total_day"] = va["date"].map({d: anomaly.total_note(total, d) is not None for d in va["date"].unique()})
    p = va["pred_pct"]
    va["cyclical"] = cycle.is_cyclical_rise(p, va["cycle"]) | cycle.is_cyclical_fall(p, va["cycle"])
    va["situation"] = situation.code(va)
    va["actual_pct"] = scoring.pct(va["y_0"], va["y_h3"])
    va["anomaly"] = va["anomaly"].fillna(False).astype(bool)
    return Frames(model, raw, cl, an["anomaly"].fillna(False).astype(bool), va)


def _span(dates) -> dict:
    d = pd.to_datetime(pd.Series(dates))
    return {"from": d.min().strftime("%Y-%m-%d"), "through": d.max().strftime("%Y-%m-%d"), "days": int(d.nunique())}


def model_version() -> dict:
    from src import train

    d = Path(train.MODEL_DIR)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    return {"model_hash": train.model_hash(d), "version": train.short_version(train.model_hash(d)),
            "trained_at": meta["trained_at"],
            "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*.cbm"))}}


def compute(f: Frames) -> dict:
    """Бүх тоо. Санамсаргүй зүйл зөвхөн тогтмол seed-тэй bootstrap: дахин ажиллуулахад ижил."""
    meta = f.model.meta
    T = meta["fire"]["T"]
    m = f.valid[f.valid["measurable"].fillna(False).astype(bool)].copy()
    span = _span(m["date"])
    rows = {"population": "(в)-гүй valid, хэмжигдэх сэдэв (src/calibrate.valid_frame)", **span, "rows": len(m)}
    out = {"rows": rows}

    # #1–#5 дүгнэлт (ADR 0021), + AUC ба MAE (ADR 0021-ийн "Яагаад")
    v = verdict_numbers(m)
    a = m[m["anomaly"]]
    fade = faded(a["actual_pct"])
    v |= {"auc_fade_model": auc(-a["pred_pct"], fade), "auc_fade_z": auc(a["z"], fade),
          "mae_h3_model": float((a["delta_h3"] - a["delta_hat_h3"]).abs().mean()),
          "mae_h3_naive": float(a["delta_h3"].abs().mean())}
    out["verdict"] = v

    # #6, #7 хүчтэй өсөлт ба тод зүйл (ADR 0026)
    out["strong"] = {"T": T, **strong_numbers(m, T)}

    # #8 бууралтын quantile
    le20 = m["pred_pct"].to_numpy(float) <= situation.BAND_EDGES[0]   # ↓ ≤ −20% (сайтын сумтай нэг хил)
    out["decline"] = {"share_le_-20": float(le20.mean()), "per_day_le_-20": le20.sum() / span["days"], "n": int(le20.sum())}

    # #9 Давж өсөх жагсаалт ба үндсэн хувь (ADR 0019, 0020)
    m["hit"] = excess_hit(m["actual_pct"], m["cycle"])
    lst = cycle.beyond_list(m)
    N = lst.groupby("date").size()
    not_cr = ~cycle.is_cyclical_rise(m["pred_pct"], m["cycle"])
    pool = m[not_cr]
    day_base = pool.groupby("date")["hit"].mean()
    out["beyond"] = {
        "rows": len(lst), "excess_hit": float(lst["hit"].mean()),
        "base_all": excess_hit_rate(m["actual_pct"], m["cycle"]),
        "base_not_cyclical_rise": excess_hit_rate(pool["actual_pct"], pool["cycle"]),
        "base_same_n_random_not_cyclical_rise": float((day_base * N.reindex(day_base.index, fill_value=0)).sum() / N.sum()),
        "rebound_share_of_list": float((lst["situation"] == "rebound").mean())}

    # #10 Anomaly-ийн хамгийн бага тоо (ADR 0022). Нүүр БҮХ сэдвийн Anomaly-г тоолдог (хэмжигдэхгүй, (в) ч орно) тул хоёуланг.
    k = per_day(m["anomaly"], m["date"], pd.Index(m["date"].unique()))
    site = f.cl[f.cl["date"].isin(m["date"].unique())][["article", "date"]].copy()
    site["anomaly"] = f.cl_anomaly.reindex(site.index).to_numpy()
    ks = per_day(site["anomaly"], site["date"], pd.Index(m["date"].unique()))
    out["quiet"] = {"min_per_day": int(k.min()), "days_zero": int((k == 0).sum()), "min_day": k.idxmin().strftime("%Y-%m-%d"),
                    "site_min_per_day": int(ks.min()), "site_days_zero": int((ks == 0).sum()),
                    "site_min_day": ks.idxmin().strftime("%Y-%m-%d"), "site_mean_per_day": float(ks.mean()),
                    "site_topics": int(site["article"].nunique())}

    # #11 интервал тэлэх эсэх (ADR 0027)
    out["interval"] = interval_widening(m, meta["interval"])

    # #12 Буцалтын "ердийн түвшин рүүгээ буцна" дүрэм (issue-д "naive"; CONTEXT.md-ийн naive = Δ̂ = 0 тул энд "буцах дүрэм")
    reb = m[m["situation"] == "rebound"]
    lr = lst[lst["situation"] == "rebound"]
    mae = lambda d, pred: float((d["delta_h3"] - pred).abs().mean())   # noqa: E731
    reversion = {}
    for lvl in ("level_28", "level_0017"):
        mm = m.assign(rev_pct=scoring.predicted_pct(m["y_0"], m[lvl] - m["y_0"]))
        rl = same_n_list(mm, "rev_pct", N)
        rr = same_n_list(mm[mm["situation"] == "rebound"], "rev_pct", lr.groupby("date").size())
        reversion[lvl] = {"mae_h3_rebound": mae(reb, reb[lvl] - reb["y_0"]), "undefined_rows": int(reb[lvl].isna().sum()),
                          "within_rebound_rows": len(rr), "within_rebound_excess_hit": float(rr["hit"].mean()),
                          "diff_within_rebound": day_bootstrap_diff(lr[["date", "hit"]], rr[["date", "hit"]]),
                          "list_rows": len(rl), "list_excess_hit": float(rl["hit"].mean()),
                          "list_rebound_share": float((rl["situation"] == "rebound").mean()),
                          "diff_list": day_bootstrap_diff(lst[["date", "hit"]], rl[["date", "hit"]])}
    out["rebound"] = {"rows": len(reb), "per_day": len(reb) / span["days"],
                      "base_excess_hit": excess_hit_rate(reb["actual_pct"], reb["cycle"]),
                      "mae_h3_model": mae(reb, reb["delta_hat_h3"]), "mae_h3_naive": mae(reb, 0.0),
                      "model_list_excess_hit": float(lst["hit"].mean()), "model_list_rows": len(lst),
                      "model_within_rebound_rows": len(lr), "model_within_rebound_excess_hit": float(lr["hit"].mean()),
                      "reversion": reversion}

    # #13 X% (ADR 0016, 8-р зүйл)
    flips = {x: partial_day_flips(m, x) for x in SHORTFALL_GRID}
    limit = MAX_FLIP_SHARE * v["anomalies_per_day"]
    X = tolerated_shortfall(flips, limit, "up")
    out["recheck"] = {"X": X, "direction": "up", "max_flips_per_day": limit, "flips": {f"{x:.3f}": fl for x, fl in flips.items()}}

    # #14 "Өгөгдөл дутуу"-гийн хоёр босго (ADR 0022). Бүх түүх (model-ийн үнэлгээ биш, нийт уншилтын тархалт).
    from src import live
    tr, ac = total_ratio(f.raw.total), article_coverage(f.raw.pageviews)
    q = (0.0, 0.001, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0)
    out["incomplete"] = {
        "total": {**_span(tr.index), "quantiles": {f"{k:g}": float(v_) for k, v_ in tr.quantile(q).items()},
                  "lowest": {d.strftime("%Y-%m-%d"): float(r) for d, r in tr.nsmallest(5).items()},
                  "threshold": share_threshold(tr), "current": live.TOTAL_MIN_SHARE},
        "article": {**_span(ac.index), "quantiles": {f"{k:g}": float(v_) for k, v_ in ac.quantile(q).items()},
                    "lowest": {d.strftime("%Y-%m-%d"): float(r) for d, r in ac.nsmallest(5).items()},
                    "threshold": share_threshold(ac), "current": live.ARTICLE_MIN_SHARE}}
    return out


# ================================================================ тайлан: тоо бүр = утга, тодорхойлолт, n, огноо, ADR-ийн бичсэн тоо

def _get(res: dict, path: str):
    for k in path.split("."):
        res = res[k]
    return res


# (тайлбар, results-ийн зам, ADR-д ОДОО бичигдсэн утга, зөвшөөрөх зөрүү, ADR, өмнө бичигдсэн утга эсвэл None).
# Зөрүү = бичигдсэн тооны нарийвчлалын хагас.
# Тоо зөрвөл ADR-ийг шинэчилж (хуучин тоо, шалтгаантай), энд бичигдсэн утгыг шинэчилнэ, хуучныг нь "өмнө" баганад үлдээнэ.
CLAIMS = {
    1: [("Anomaly өдөрт", "verdict.anomalies_per_day", 19.6, 0.05, "0021", None)],
    2: [("h3-т унтарсан", "verdict.faded_share", 0.695, 0.0005, "0021", None)],
    3: [("\"үргэлжлэх\" өдөрт", "verdict.continue_per_day", 3.8, 0.05, "0021, 0026", None),
        ("\"үргэлжлэх\" / Anomaly", "verdict.continue_share", 0.19, 0.005, "0026", None)],
    4: [("\"үргэлжлэх\"-ийн унтраагүй хувь", "verdict.continue_held", 0.608, 0.0005, "0020, 0021", None),
        ("үндсэн хувь (бүх Anomaly)", "verdict.base_held", 0.305, 0.0005, "0020, 0021", None)],
    5: [("\"үргэлжлэх\" 0-тэй өдөр", "verdict.days_zero_continue", 8, 0, "0021", None),
        ("\"үргэлжлэх\" 1-тэй өдөр", "verdict.days_one_continue", 31, 0, "0021", None)],
    6: [("pct ≥ T өдөрт (мөчлөгийн өсөлт орсон)", "strong.pct_ge_T_per_day", 3.8, 0.05, "0026", None),
        ("pct ≥ T хувь", "strong.pct_ge_T_share", 0.016, 0.0005, "0026", None)],
    7: [("Хүчтэй өсөлтийн таамаг өдөрт", "strong.strong_per_day", 1.56, 0.005, "0026", 3.8),
        ("тод зүйлгүй өдөр", "strong.days_nothing_bold", 4, 0, "0026", None)],
    8: [("pct ≤ −20% хувь", "decline.share_le_-20", 0.105, 0.0005, "0026", 0.10),
        ("pct ≤ −20% өдөрт", "decline.per_day_le_-20", 24.5, 0.05, "0026", 23)],
    9: [("бодит илүүдэл ≥ +10%", "beyond.excess_hit", 0.589, 0.0005, "0019, 0020", None),
        ("үндсэн хувь", "beyond.base_all", 0.293, 0.0005, "0019, 0020", 0.301)],
    10: [("Anomaly-ийн хамгийн бага (нүүр)", "quiet.site_min_per_day", 10, 0, "0022", None),
         ("Anomaly 0-тэй өдөр (нүүр)", "quiet.site_days_zero", 0, 0, "0022", None)],
    11: [("h1 ≤ h2 ≤ h3", "interval.share_widening", 0.973, 0.0005, "0027", None)],
    12: [("Буцалт доторх үндсэн хувь", "rebound.base_excess_hit", 0.388, 0.0005, "0020", None),
         ("Буцалт: CatBoost жагсаалт", "rebound.model_within_rebound_excess_hit", 0.591, 0.0005, "0020", None),
         ("Буцалт: буцах дүрэм (28 өдөр)", "rebound.reversion.level_28.within_rebound_excess_hit", 0.543, 0.0005, "0020", None),
         ("Буцалт: буцах дүрэм (ADR 0017)", "rebound.reversion.level_0017.within_rebound_excess_hit", 0.560, 0.0005, "0020", None)],
    13: [("X", "recheck.X", 0.015, 0, "0016", None)],
    14: [("TOTAL_MIN_SHARE санал", "incomplete.total.threshold", 0.85, 0, "0022", None),
         ("ARTICLE_MIN_SHARE санал", "incomplete.article.threshold", 0.95, 0, "0022", None)],
    15: [("\"унтрах\" эрэмбийн AUC", "verdict.auc_fade_model", 0.744, 0.0005, "0021", None),
         ("z ганцаараа AUC", "verdict.auc_fade_z", 0.591, 0.0005, "0021", None),
         ("MAE (h3, Anomaly)", "verdict.mae_h3_model", 0.268, 0.0005, "0021", None),
         ("naive MAE (h3, Anomaly)", "verdict.mae_h3_naive", 0.446, 0.0005, "0021", None)],
}

TITLES = {
    1: "Өдрийн Anomaly-ийн дундаж",
    2: "Anomaly-ийн хэдэн % нь h3-т унтарсан",
    3: "\"Үргэлжлэх\" дүгнэлт өдөрт / Anomaly-ийн %",
    4: "\"Үргэлжлэх\"-ийн precision ба үндсэн хувь",
    5: "\"Үргэлжлэх\" 0-тэй ба 1-тэй өдөр",
    6: "Хүчтэй өсөлтийн таамаг (pct ≥ T)",
    7: "Мөчлөгийн өсөлтийг хассан хүчтэй өсөлт (тод тоо); тод зүйлгүй өдөр",
    8: "Таамагласан pct ≤ −20%",
    9: "Давж өсөх жагсаалтын бодит илүүдэл ≥ +10% ба үндсэн хувь",
    10: "Өдрийн Anomaly-ийн хамгийн бага тоо, Anomaly 0-тэй өдөр",
    11: "80% интервалын өргөн h1 ≤ h2 ≤ h3",
    12: "Буцалтын naive дүрэмтэй харьцуулалт",
    13: "ADR 0016-ийн 8-р зүйлийн X%",
    14: "\"Өгөгдөл дутуу\"-гийн хоёр босго",
    15: "ADR 0021-ийн AUC ба MAE (нэмэлт: ADR-д \"давтагдаагүй\" гэж бичигдсэн)",
}


def claims(res: dict) -> list[dict]:
    out = []
    for num, items in CLAIMS.items():
        for label, path, want, tol, adr, before in items:
            got = _get(res, path)
            ok = got is not None and abs(got - want) <= tol + 1e-12
            out.append({"number": num, "label": label, "path": path, "adr": adr, "documented": want, "previously": before,
                        "value": got, "matches": bool(ok)})
    return out


def _clean(x):
    """JSON-д тогтвортой: float-ыг 6 оронтой, numpy төрлийг python руу."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), 6)
    return x


def report(f: Frames) -> dict:
    res = compute(f)
    return _clean({"script": "scripts/frequency_numbers.py", "issue": 54, "model": model_version(),
                   "data": {"processed_through": f.raw.end.strftime("%Y-%m-%d"), "source": "data/processed/ (git)"},
                   "results": res, "claims": claims(res)})


def _p(x, k: int = 1) -> str:
    return "—" if x is None else f"{x * 100:.{k}f}%"


def _ci(d: dict) -> str:
    return f"{d['diff'] * 100:+.1f} pp (95% CI {d['lo'] * 100:+.1f} … {d['hi'] * 100:+.1f})"


def _claim_fmt(c: dict):
    """Тоо (өдөрт, тоолол) → 2 орон эсвэл бүхэл, AUC/MAE → 3 орон, хувь → 1 оронтой %."""
    if c["path"].startswith(("verdict.auc", "verdict.mae")):
        return lambda x: f"{x:.3f}"
    if c["path"].endswith(("per_day", "per_day_le_-20")):
        return lambda x: f"{x:.2f}"
    if isinstance(c["value"], int) and not isinstance(c["value"], bool):
        return lambda x: f"{x:g}"
    return lambda x: f"{x * 100:.1f}%"


def render_md(r: dict) -> str:
    """docs/numbers/frequency.md: хүнд уншигдах хувилбар. Бүх тоо frequency.json-оос (энэ функц шинэ тоо тооцохгүй)."""
    R, mv, rows = r["results"], r["model"], r["results"]["rows"]
    v, b, dc, bl, q, iv, rb = (R[k] for k in ("verdict", "strong", "decline", "beyond", "quiet", "interval", "rebound"))
    n28, n17 = rb["reversion"]["level_28"], rb["reversion"]["level_0017"]
    # ADR 0020-ийн өмнөх 30.1%-ийг (0.1%-ийн нарийвчлалаар) давтах үндсэн хувийн хувилбар байгаа эсэх
    bases = {"бүх хэмжигдэх мөр": bl["base_all"], "мөчлөгийн өсөлт биш мөр": bl["base_not_cyclical_rise"],
             "мөчлөгийн өсөлт биш мөрөөс өдөр бүр жагсаалттай ижил N санамсаргүй авахын хүлээгдэх утга": bl["base_same_n_random_not_cyclical_rise"]}
    hits301 = [k for k, x in bases.items() if abs(x - 0.301) <= 0.0005]
    rc, inc = R["recheck"], R["incomplete"]
    span = f"{rows['from']} … {rows['through']}, {rows['days']} өдөр"
    L = [
        "# Давтамжийн тоо (#54)",
        "",
        "> **Үүсгэсэн файл, гараар засахгүй.** `python scripts/frequency_numbers.py` → `docs/numbers/frequency.json` + энэ файл.",
        "> Дахин ажиллуулахад ижил (bootstrap нь тогтмол seed-тэй). Тест: `tests/test_frequency_numbers.py`.",
        "",
        f"- **Model:** `{mv['version']}` (`train.model_hash` {mv['model_hash']}), `meta.json` trained_at {mv['trained_at']}.",
        "  `.cbm`-ийн sha256: " + ", ".join(f"{k} `{h[:12]}…`" for k, h in mv["files_sha256"].items()) + ".",
        f"- **Өгөгдөл:** `data/processed/` (git), сүүлийн өдөр {r['data']['processed_through']}. "
        "`serve.clean_chunks` (= `python -m src.clean`) → `features.frame` (= `python -m src.features`).",
        f"- **Мөр (#1–#12):** {rows['population']}, {span}, {rows['rows']:,} мөр. Test-ийг ашиглаагүй (ADR 0002).",
        "- **Тодорхойлолт (ADR 0021):** дүгнэлт = Anomaly (z ≥ 3, ADR 0017) сэдвийн таамагласан pct (h3) ≤ −10% → унтрах, "
        "бусад → үргэлжлэх. Бодит үр дүн = h3 өдрийн (asof+3) бодит pct ≤ −10% → унтарсан.",
        "",
        "## Бичигдсэн тоотой харьцуулалт",
        "",
        "Бичигдсэн = ADR-д одоо бичигдсэн утга (зөрсөн тоог энэ скриптээр шинэчилсэн бол хуучин нь \"Өмнө\" баганад).",
        "",
        "| # | Тоо | ADR | Өмнө | Бичигдсэн | Скрипт | |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in r["claims"]:
        fmt = _claim_fmt(c)
        before = "" if c["previously"] is None else fmt(c["previously"])
        L.append(f"| {c['number']} | {c['label']} | {c['adr']} | {before} | {fmt(c['documented'])} | {fmt(c['value'])} | "
                 f"{'✅' if c['matches'] else '⚠️ зөрсөн'} |")
    L += [
        "",
        "## Тоо бүр",
        "",
        f"### 1–5. {TITLES[1]} … \"үргэлжлэх\" 0/1-тэй өдөр (ADR 0021)",
        "",
        f"- Anomaly: {v['anomalies']:,} мөр, өдөрт **{v['anomalies_per_day']:.2f}**.",
        f"- h3-т унтарсан (бодит pct (h3) ≤ −10%): **{_p(v['faded_share'])}**.",
        f"- \"Үргэлжлэх\": {v['continue']:,} мөр, өдөрт **{v['continue_per_day']:.2f}**, Anomaly-ийн **{_p(v['continue_share'])}**.",
        f"- \"Үргэлжлэх\"-ийн **{_p(v['continue_held'])}** нь унтраагүй (бодит pct (h3) > −10%). Үндсэн хувь (бүх Anomaly): **{_p(v['base_held'])}**.",
        f"- \"Үргэлжлэх\" 0-тэй өдөр **{v['days_zero_continue']}**, 1-тэй өдөр **{v['days_one_continue']}** ({v['days']}-ээс).",
        f"- Нэмэлт (#15): \"унтрах\" эрэмбийн AUC (оноо = −таамагласан pct, шошго = унтарсан) **{v['auc_fade_model']:.3f}**, "
        f"z ганцаараа **{v['auc_fade_z']:.3f}**. MAE (Δ, h3, Anomaly) **{v['mae_h3_model']:.3f}**, naive (Δ̂ = 0) **{v['mae_h3_naive']:.3f}**.",
        "",
        f"### 6–7. {TITLES[6]}; {TITLES[7]} (ADR 0026)",
        "",
        f"- T = {b['T']:.0%} (`meta.json`). Таамагласан pct ≥ T (мөчлөгийн өсөлт орсон): {b['pct_ge_T']:,} мөр, "
        f"өдөрт **{b['pct_ge_T_per_day']:.2f}** (мөрийн **{_p(b['pct_ge_T_share'])}**).",
        f"- **Хүчтэй өсөлтийн таамаг** (CONTEXT.md: pct ≥ T ба мөчлөгийн өсөлт биш, ADR 0019; сайтын тод тоо): {b['strong']:,} мөр, "
        f"өдөрт **{b['strong_per_day']:.2f}** (**{_p(b['strong_share'], 2)}**). 0-тэй өдөр **{b['days_zero_strong']}** ({b['days']}-ээс).",
        f"- Тод зүйлгүй өдөр (Хүчтэй өсөлтийн таамаг ч, \"үргэлжлэх\" ч 0): **{b['days_nothing_bold']}** ({b['days']}-ээс).",
        "",
        f"### 8. {TITLES[8]} (ADR 0026)",
        "",
        f"- {dc['n']:,} мөр: **{_p(dc['share_le_-20'])}**, өдөрт **{dc['per_day_le_-20']:.1f}**.",
        "",
        f"### 9. {TITLES[9]} (ADR 0019, 0020)",
        "",
        f"- Жагсаалт: {bl['rows']:,} мөр, бодит илүүдэл ≥ +10% **{_p(bl['excess_hit'])}** (Буцалт {_p(bl['rebound_share_of_list'])}).",
        "- Үндсэн хувь (бодит илүүдэл ≥ +10%), хүрээний хувилбар бүрээр: "
        + "; ".join(f"{k} **{_p(x)}**" for k, x in bases.items()) + ".",
        "- ADR 0020-ийн өмнөх 30.1%-ийг давтах хувилбар: " + (", ".join(hits301) if hits301 else "**алга**") + ".",
        "",
        f"### 10. {TITLES[10]} (ADR 0022)",
        "",
        f"- Хэмжигдэх, (в)-гүй: хамгийн бага **{q['min_per_day']}** ({q['min_day']}), 0-тэй өдөр **{q['days_zero']}**.",
        f"- Нүүрний тоолол (бүх {q['site_topics']} сэдэв, хэмжигдэхгүй ба (в) орно, `serve.anomaly_summary`): хамгийн бага **{q['site_min_per_day']}** "
        f"({q['site_min_day']}), 0-тэй өдөр **{q['site_days_zero']}**, дундаж {q['site_mean_per_day']:.1f}.",
        f"- \"Нам гүм\" төлөв (нүүрний Anomaly 0) valid-ийн {rows['days']} өдрийн **{q['site_days_zero']}**-д гарсан.",
        "",
        f"### 11. {TITLES[11]} (ADR 0027)",
        "",
        f"- Мөр бүрийн 80% интервалын pct өргөн (сайтын зурдаг): h1 ≤ h2 ≤ h3 **{_p(iv['share_widening'])}** "
        f"(h1 ≤ h2 {_p(iv['share_h1_le_h2'])}, h2 ≤ h3 {_p(iv['share_h2_le_h3'])}).",
        f"- Лог хуваарийн өргөн тогтмол, тэлдэг: h1 {iv['log_width']['h1']}, h2 {iv['log_width']['h2']}, h3 {iv['log_width']['h3']}. "
        "Тэлэхгүй мөр нь h бүрийн Δ̂ өөр байгаагаас (pct өргөн нь exp(Δ̂)-тэй пропорциональ).",
        "",
        f"### 12. {TITLES[12]}",
        "",
        f"- Буцалт нөхцөл (ADR 0020, `situation.code`): {rb['rows']:,} мөр (өдөрт {rb['per_day']:.1f}). "
        f"**Буцалт доторх үндсэн хувь** (бодит илүүдэл ≥ +10%): **{_p(rb['base_excess_hit'])}** (бүх мөрийнх {_p(bl['base_all'])}).",
        "- **Буцах дүрэм** (issue-д \"naive\"; CONTEXT.md-ийн naive нь Δ̂ = 0): \"сэдэв ердийн түвшин рүүгээ буцна\", Δ̂ (h3) = түвшин − y_0, "
        "y = log1p(анхаарал). Хоёр түвшин: 28 өдрийн медиан (t−27 … t, asof өдөр орно), ADR 0017-ийн ердийн түвшин (t−59 … t−7-ийн медиан).",
        "- Жагсаалт: Давж өсөх жагсаалтын дүрэм (Rising, мөчлөгийн өсөлт биш, pct-ээр) буцах дүрмийн pct-ээр, өдөр бүр CatBoost-ийн жагсаалттай "
        "ижил N (ADR 0020). Model − дүрэм = нийлүүлсэн хувийн зөрүү, 95% CI нь өдрөөр хос bootstrap.",
        "",
        "| **Буцалт мөрүүд дээр** (spec-ийн хүрээ) | MAE (Δ, h3) | Жагсаалт: бодит илүүдэл ≥ +10% | CatBoost − дүрэм |",
        "|---|---|---|---|",
        f"| CatBoost ({rb['model_within_rebound_rows']:,} мөр) | **{rb['mae_h3_model']:.3f}** | **{_p(rb['model_within_rebound_excess_hit'])}** | |",
        f"| Буцах дүрэм, 28 өдрийн медиан | {n28['mae_h3_rebound']:.3f} | {_p(n28['within_rebound_excess_hit'])} | {_ci(n28['diff_within_rebound'])} |",
        f"| Буцах дүрэм, ADR 0017-ийн түвшин | {n17['mae_h3_rebound']:.3f} | {_p(n17['within_rebound_excess_hit'])} | {_ci(n17['diff_within_rebound'])} |",
        f"| Naive (Δ̂ = 0) | {rb['mae_h3_naive']:.3f} | | |",
        f"| Үндсэн хувь (Буцалт доторх) | | {_p(rb['base_excess_hit'])} | |",
        "",
        "| Бүх хэмжигдэх мөр (нүүрний жагсаалт шиг) | Жагсаалт: бодит илүүдэл ≥ +10% | CatBoost − дүрэм |",
        "|---|---|---|",
        f"| CatBoost (Давж өсөх жагсаалт, {rb['model_list_rows']:,}) | **{_p(rb['model_list_excess_hit'])}** | |",
        f"| Буцах дүрэм, 28 өдөр (жагсаалтын Буцалт {_p(n28['list_rebound_share'], 0)}) | {_p(n28['list_excess_hit'])} | {_ci(n28['diff_list'])} |",
        f"| Буцах дүрэм, ADR 0017 (Буцалт {_p(n17['list_rebound_share'], 0)}) | {_p(n17['list_excess_hit'])} | {_ci(n17['diff_list'])} |",
        f"| Үндсэн хувь (бүх мөр) | {_p(bl['base_all'])} | |",
        "",
        f"### 13. {TITLES[13]} (ADR 0016)",
        "",
        f"- Дүрэм (Claude-ийн санал): нэг өдрийн өгөгдөл X-ээр дутуу байх нь тэр өдрийн Anomaly-ийн ≤ {MAX_FLIP_SHARE:.0%}-ийг "
        f"(өдөрт ≤ {rc['max_flips_per_day']:.2f}) өөрчлөх хамгийн их X, 0.5%-ийн алхмаар. Шалгалт нь НИЙТ уншилтын өсөлтийг хардаг тул "
        "\"нийт уншилт дутуу\" чиглэлээр (худал Anomaly). Сэдвийн уншилт дутуугийн чиглэлийг (Anomaly алга болох) нийт уншилт илрүүлэхгүй: зөвхөн мэдээлэлд.",
        f"- **X = {_p(rc['X'])}**: хадгалснаас хойш нийт уншилт ≥ {_p(rc['X'])} өсвөл `incomplete_at_publish`.",
        "",
        "| X | Anomaly алга болох / өдөр | худал Anomaly / өдөр |",
        "|---|---|---|",
    ]
    for x in ("0.005", "0.010", "0.015", "0.020", "0.030", "0.050", "0.100"):
        fl = rc["flips"][x]
        L.append(f"| {float(x):.1%} | {fl['down']:.2f} | {fl['up']:.2f} |")
    t, a = inc["total"], inc["article"]
    L += [
        "",
        f"### 14. {TITLES[14]} (ADR 0022)",
        "",
        "Бүх түүх, test-ийн хугацаа орно: энэ нь model-ийн үнэлгээ биш, Wikimedia-ийн өгөгдлийн бүрэн байдлын тархалт (ADR 0002 хамаарахгүй). "
        "Дүрэм: бүх бүрэн өдрөөс хатуу доор байх 5%-ийн хамгийн их үржвэр. **Санал**, `src/live.py`-д хэрэгжүүлээгүй (Майк батлах).",
        "",
        "| | Хүрээ | min | 0.1% | 1% | медиан | Санал | Одоо |",
        "|---|---|---|---|---|---|---|---|",
        f"| Нийт уншилт ÷ өмнөх 28 өдрийн медиан (`TOTAL_MIN_SHARE`) | {t['from']} … {t['through']} ({t['days']}) | "
        f"{t['quantiles']['0']:.3f} | {t['quantiles']['0.001']:.3f} | {t['quantiles']['0.01']:.3f} | {t['quantiles']['0.5']:.3f} | **{t['threshold']:.2f}** | {t['current']:.2f} |",
        f"| Уншилттай сэдэв ÷ өмнөх өдрийн мөртэй сэдэв (`ARTICLE_MIN_SHARE`) | {a['from']} … {a['through']} ({a['days']}) | "
        f"{a['quantiles']['0']:.3f} | {a['quantiles']['0.001']:.3f} | {a['quantiles']['0.01']:.3f} | {a['quantiles']['0.5']:.3f} | **{a['threshold']:.2f}** | {a['current']:.2f} |",
        "",
        "Нийт уншилтын хамгийн бага 5 өдөр: " + ", ".join(f"{d} {x:.3f}" for d, x in t["lowest"].items()) + ".",
        "",
    ]
    return "\n".join(L)


def main(out_dir: Path = OUT_DIR) -> dict:
    r = report(load())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frequency.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "frequency.md").write_text(render_md(r), encoding="utf-8")
    bad = [c for c in r["claims"] if not c["matches"]]
    print(f"{out_dir / 'frequency.json'}, frequency.md: {len(r['claims'])} тоо, {len(bad)} зөрсөн")
    for c in bad:
        print(f"  #{c['number']} {c['label']} (ADR {c['adr']}): бичигдсэн {c['documented']}, скрипт {c['value']}")
    return r


if __name__ == "__main__":
    main()
