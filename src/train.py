"""
Сургалт: LightGBM, XGBoost, CatBoost-ыг horizon бүрт (h1, h2, h3) сургаж, Optuna-аар тааруулаад,
(в)-гүй valid MAE-ээр ялагчийг сонгож, app/model/ руу экспортлоно (issue #5).

Өөрчлөгдөхгүй зүйлс: 18 feature (feature_list.json), target Δ = y_h − y_0, L1 loss, тогтмол хуваалт.
  - Сургалт: train хуваалтын 2023-07-01-ээс хойшх мөр, (в) ОРНО (ADR 0009). Хилийн purge features.py-д хийгдсэн.
  - Early stopping ба сонголт: valid, (в)-гүй (ADR 0005). Test-ийг энд ОГТ уншихгүй.

Ажиллуулах:  python -m src.train  ->  app/model/{h1,h2,h3}.<ext> + meta.json
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import catboost as cb
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb

from src.features import HORIZONS
from src.scoring import GROUP_NEW_VIRAL, topic_group

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "app" / "model"

ALGOS = ("lightgbm", "xgboost", "catboost")
EXT = {"lightgbm": "txt", "xgboost": "json", "catboost": "cbm"}

# Optuna тохиргоо (Майк зөвшөөрсөн (Claude санал болгосон), 2026-11-10)
TRAIN_FROM = pd.Timestamp("2023-07-01")   # хурдны тулд train-ийн энэ өдрөөс хойшх хэсэг
N_TRIALS = 25                             # алгоритм × horizon бүрт
EARLY_STOP = 100
MAX_ROUNDS = 3000
REPORT_EVERY = 10                         # MedianPruner-т valid MAE-г хэдэн iteration тутам мэдээлэх вэ
SEED = 42
THREADS = 4
CURVE_POINTS = 200                        # meta.json-ийн learning curve-ийн цэгийн дээд тоо


def row_sets(feats: pd.DataFrame, groups: pd.Series) -> dict[str, pd.Series]:
    """feats: [date, split, article, ...], groups: article -> а/б/в.
    Буцаах: {"train": mask, "valid": mask}. train = train хуваалт, date ≥ 2023-07-01, бүх бүлэг (в орно).
    valid = valid хуваалт, (в)-гүй (early stopping ба алгоритм сонголтод). Test аль алинд нь орохгүй."""
    g = feats["article"].map(groups)
    return {
        "train": (feats["split"] == "train") & (feats["date"] >= TRAIN_FROM),
        "valid": (feats["split"] == "valid") & (g != GROUP_NEW_VIRAL),
    }


def select_winner(table: pd.DataFrame) -> str:
    """table: [algo, h, valid_mae] ((в)-гүй valid). h1–h3-ын дундаж MAE хамгийн бага алгоритмын нэр."""
    return str(table.groupby("algo")["valid_mae"].mean().idxmin())


# ---------------------------------------------------------------- нэг model сургах / таамаглах

@dataclass
class Fitted:
    """Нэг horizon-ы сургасан model. `model` нь хамгийн сайн iteration хүртэл тасдагдсан."""
    algo: str
    model: object
    params: dict
    best_iteration: int                      # 1-ээс эхэлсэн мод/iteration-ы тоо
    curve: dict                              # {"train": [MAE...], "valid": [MAE...]} iteration бүрээр
    importance: dict = field(default_factory=dict)   # feature -> хувь (нийлбэр 1)


class _Pruned(Exception):
    pass


def _norm(imp: dict, features: list[str]) -> dict:
    v = np.array([float(imp.get(f, 0.0)) for f in features])
    v = v / v.sum() if v.sum() > 0 else v
    return dict(zip(features, v.tolist()))


def fit(algo: str, params: dict, X_tr: pd.DataFrame, y_tr, X_va: pd.DataFrame, y_va,
        n_rounds: int = MAX_ROUNDS, trial: optuna.Trial | None = None) -> Fitted:
    """L1 loss, valid дээр early stopping (EARLY_STOP). `trial` өгвөл REPORT_EVERY iteration тутам valid MAE-г
    Optuna руу мэдээлж, MedianPruner шийдвэл optuna.TrialPruned шиднэ."""
    features = list(X_tr.columns)
    stop = min(EARLY_STOP, n_rounds)

    def report(it: int, value: float) -> bool:
        """True = таслах."""
        if trial is None or it % REPORT_EVERY:
            return False
        trial.report(value, it)
        return trial.should_prune()

    if algo == "lightgbm":
        p = {"objective": "l1", "metric": "l1", "verbosity": -1, "num_threads": THREADS, "seed": SEED,
             "deterministic": True, "force_row_wise": True, **params}
        dtr = lgb.Dataset(X_tr, y_tr, free_raw_data=False)
        dva = lgb.Dataset(X_va, y_va, reference=dtr)
        hist: dict = {}

        def cb_prune(env):
            val = [r[2] for r in env.evaluation_result_list if r[0] == "valid"][0]
            if report(env.iteration + 1, val):
                raise _Pruned()

        m = lgb.train(p, dtr, n_rounds, valid_sets=[dtr, dva], valid_names=["train", "valid"],
                      callbacks=[lgb.early_stopping(stop, verbose=False), lgb.record_evaluation(hist), cb_prune])
        best = m.best_iteration or m.current_iteration()
        m = lgb.Booster(model_str=m.model_to_string(num_iteration=best))
        curve = {"train": hist["train"]["l1"], "valid": hist["valid"]["l1"]}
        imp = dict(zip(features, m.feature_importance("gain")))

    elif algo == "xgboost":
        p = {"objective": "reg:absoluteerror", "eval_metric": "mae", "tree_method": "hist", "nthread": THREADS,
             "seed": SEED, **params}
        dtr = xgb.QuantileDMatrix(X_tr, y_tr)
        dva = xgb.QuantileDMatrix(X_va, y_va, ref=dtr)
        hist = {}

        class CbPrune(xgb.callback.TrainingCallback):
            def after_iteration(self, model, epoch, evals_log):
                if report(epoch + 1, evals_log["valid"]["mae"][-1]):
                    raise _Pruned()
                return False

        m = xgb.train(p, dtr, n_rounds, evals=[(dtr, "train"), (dva, "valid")], early_stopping_rounds=stop,
                      evals_result=hist, verbose_eval=False, callbacks=[CbPrune()])
        best = m.best_iteration + 1
        m = m[:best]
        curve = {"train": hist["train"]["mae"], "valid": hist["valid"]["mae"]}
        imp = m.get_score(importance_type="total_gain")

    elif algo == "catboost":
        pruned = {"flag": False}

        class CbPrune:
            def after_iteration(self, info):
                if report(info.iteration, info.metrics["validation"]["MAE"][-1]):
                    pruned["flag"] = True
                    return False
                return True

        p = {"loss_function": "MAE", "eval_metric": "MAE", "thread_count": THREADS, "random_seed": SEED,
             "allow_writing_files": False, "verbose": 0, **params}
        m = cb.CatBoostRegressor(iterations=n_rounds, od_type="Iter", od_wait=stop, use_best_model=True, **p)
        m.fit(X_tr, y_tr, eval_set=(X_va, y_va), callbacks=[CbPrune()])
        if pruned["flag"]:
            raise _Pruned()
        ev = m.get_evals_result()
        best = m.get_best_iteration() + 1
        curve = {"train": ev["learn"]["MAE"], "valid": ev["validation"]["MAE"]}
        imp = dict(zip(features, m.get_feature_importance()))
    else:
        raise ValueError(f"танигдаагүй алгоритм: {algo}")

    curve = {k: [float(x) for x in v] for k, v in curve.items()}
    return Fitted(algo, m, dict(params), int(best), curve, _norm(imp, features))


def predict(fitted: Fitted, X: pd.DataFrame) -> np.ndarray:
    """Δ̂ = таамагласан y_h − y_0."""
    return _predict(fitted.algo, fitted.model, X)


def _predict(algo: str, model, X: pd.DataFrame) -> np.ndarray:
    if algo == "xgboost":
        return np.asarray(model.inplace_predict(X), dtype=float)
    return np.asarray(model.predict(X), dtype=float)


def mae(fitted: Fitted, X: pd.DataFrame, y) -> float:
    return float(np.mean(np.abs(predict(fitted, X) - np.asarray(y))))


# ---------------------------------------------------------------- экспорт / ачаалах (app/model/)

def _curve(c: dict) -> dict:
    n = len(c["valid"])
    idx = np.unique(np.linspace(0, n - 1, min(n, CURVE_POINTS)).round().astype(int))
    return {"iteration": (idx + 1).tolist(),
            "train": [round(c["train"][i], 5) for i in idx], "valid": [round(c["valid"][i], 5) for i in idx]}


def export(out_dir: Path, algo: str, fitted: dict[int, Fitted], features: list[str], extra: dict | None = None) -> dict:
    """Ялагч алгоритмын h бүрийн model (h1.<ext>, h2.<ext>, h3.<ext>) + meta.json-ийг out_dir руу бичнэ."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for h, f in fitted.items():
        f.model.save_model(str(out_dir / f"h{h}.{EXT[algo]}"))
    imp = pd.DataFrame({h: f.importance for h, f in fitted.items()}).mean(axis=1).sort_values(ascending=False)
    meta = {
        "algo": algo,
        "features": list(features),
        "target": "y_h - y_0 (y = log1p(анхаарал))",
        "horizons": sorted(fitted),
        "files": {f"h{h}": f"h{h}.{EXT[algo]}" for h in sorted(fitted)},
        "trained_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "best_iteration": {f"h{h}": f.best_iteration for h, f in fitted.items()},
        "params": {f"h{h}": f.params for h, f in fitted.items()},
        "importance_top10": [{"feature": k, "share": round(float(v), 4)} for k, v in imp.head(10).items()],
        "learning_curve": {f"h{h}": _curve(f.curve) for h, f in fitted.items()},
        **(extra or {}),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


@dataclass
class LoadedModel:
    meta: dict
    models: dict

    def predict(self, X: pd.DataFrame, h: int) -> np.ndarray:
        """Δ̂ (h өдрийн дараах лог анхаарал − өнөөдрийнх). X-ээс meta["features"] багануудыг дарааллаар нь авна."""
        return _predict(self.meta["algo"], self.models[h], X[self.meta["features"]])


def load(model_dir: Path = MODEL_DIR) -> LoadedModel:
    """app/model/-оос meta.json + 3 model-ийг ачаална (вэб backend, ADR 0008)."""
    model_dir = Path(model_dir)
    meta = json.loads((model_dir / "meta.json").read_text(encoding="utf-8"))
    algo, models = meta["algo"], {}
    for h in meta["horizons"]:
        path = str(model_dir / meta["files"][f"h{h}"])
        if algo == "lightgbm":
            models[h] = lgb.Booster(model_file=path)
        elif algo == "xgboost":
            models[h] = xgb.Booster()
            models[h].load_model(path)
        else:
            models[h] = cb.CatBoostRegressor()
            models[h].load_model(path)
    return LoadedModel(meta, models)


# ---------------------------------------------------------------- Optuna

def suggest(trial: optuna.Trial, algo: str) -> dict:
    """Алгоритм бүрийн хайлтын орон зай (learning rate, модны хэмжээ, regularization, түүвэрлэлт)."""
    if algo == "lightgbm":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 20, 1000, log=True),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
            "bagging_freq": 1,
            "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
        }
    if algo == "xgboost":
        return {
            "eta": trial.suggest_float("eta", 0.02, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 100.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "lambda": trial.suggest_float("lambda", 1e-3, 10.0, log=True),
        }
    if algo == "catboost":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.3, log=True),
            "depth": trial.suggest_int("depth", 4, 10),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 30.0, log=True),
            "bootstrap_type": "Bernoulli",
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "rsm": trial.suggest_float("rsm", 0.5, 1.0),
        }
    raise ValueError(f"танигдаагүй алгоритм: {algo}")


def tune(algo: str, h: int, X_tr, y_tr, X_va, y_va, n_trials: int = N_TRIALS) -> tuple[optuna.Study, Fitted]:
    """TPE + MedianPruner. Зорилго = (в)-гүй valid MAE (early stopping-ийн хамгийн сайн iteration дээр).
    Хамгийн сайн trial-ын model-ийг дахин сургалгүйгээр буцаана."""
    best: dict = {"mae": np.inf, "fit": None}

    def objective(trial: optuna.Trial) -> float:
        try:
            f = fit(algo, suggest(trial, algo), X_tr, y_tr, X_va, y_va, trial=trial)
        except _Pruned:
            raise optuna.TrialPruned()
        score = mae(f, X_va, y_va)
        trial.set_user_attr("best_iteration", f.best_iteration)
        if score < best["mae"]:
            best.update(mae=score, fit=f)
        return score

    study = optuna.create_study(
        study_name=f"{algo}_h{h}", direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=SEED),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=100))
    study.optimize(objective, n_trials=n_trials)
    return study, best["fit"]


# ---------------------------------------------------------------- бүх ажлыг нэг дор

def load_groups() -> pd.Series:
    """article -> (а)/(б)/(в) (ADR 0005), articles.csv ба viral_articles.csv-ийн peak_month-аар."""
    cur = pd.read_csv(ROOT / "data" / "articles.csv")["article"]
    vir = pd.read_csv(ROOT / "data" / "viral_articles.csv")
    pm = pd.concat([pd.Series(None, index=cur, dtype=object), pd.Series(vir["peak_month"].to_numpy(), index=vir["article"])])
    return topic_group(pm)


def run(n_trials: int = N_TRIALS, out_dir: Path = MODEL_DIR, log=print) -> dict:
    """3 алгоритм × 3 horizon-ыг Optuna-аар тааруулж, (в)-гүй valid-аар ялагчийг сонгож, out_dir руу экспортлоно.
    Буцаах: studies, fitted, table (algo × h: train/valid MAE), winner, meta."""
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    features = json.loads((P / "feature_list.json").read_text(encoding="utf-8"))["features"]
    feats = pd.read_parquet(P / "features.parquet")
    feats = feats[feats["split"] != "test"]                      # test-ийг энд огт ашиглахгүй
    groups = load_groups()
    missing = set(feats["article"]) - set(groups.index)
    if missing:
        raise ValueError(f"бүлэггүй сэдэв: {sorted(missing)[:5]}")
    rs = row_sets(feats, groups)
    tr, va = feats[rs["train"]], feats[rs["valid"]]
    va_all = feats[feats["split"] == "valid"]
    log(f"train {len(tr):,} мөр ({TRAIN_FROM.date()}-аас, (в) орсон), valid (в)-гүй {len(va):,} мөр")

    studies, fitted, rows = {}, {}, []
    for algo in ALGOS:
        for h in HORIZONS:
            t0 = time.time()
            y_tr, y_va = tr[f"y_h{h}"] - tr["y_0"], va[f"y_h{h}"] - va["y_0"]
            st, f = tune(algo, h, tr[features], y_tr, va[features], y_va, n_trials)
            studies[(algo, h)], fitted[(algo, h)] = st, f
            states = pd.Series([t.state.name for t in st.trials]).value_counts()
            rows.append({
                "algo": algo, "h": h,
                "train_mae": mae(f, tr[features], y_tr),
                "valid_mae": mae(f, va[features], y_va),
                "valid_mae_all": mae(f, va_all[features], va_all[f"y_h{h}"] - va_all["y_0"]),
                "naive_valid_mae": float(np.mean(np.abs(y_va))),
                "best_iteration": f.best_iteration,
                "trials": int(len(st.trials)), "pruned": int(states.get("PRUNED", 0)),
                "minutes": round((time.time() - t0) / 60, 1),
            })
            r = rows[-1]
            log(f"{algo:9s} h{h}: valid {r['valid_mae']:.4f} (naive {r['naive_valid_mae']:.4f}), train {r['train_mae']:.4f}, "
                f"{r['best_iteration']} iter, {r['trials']} trial ({r['pruned']} pruned), {r['minutes']} мин")

    table = pd.DataFrame(rows)
    winner = select_winner(table)
    log(f"Ялагч: {winner}")
    cols = ["algo", "h", "train_mae", "valid_mae", "valid_mae_all", "naive_valid_mae", "best_iteration", "trials", "pruned"]
    meta = export(out_dir, winner, {h: fitted[(winner, h)] for h in HORIZONS}, features, extra={
        "selection": "h1–h3-ын дундаж valid MAE хамгийн бага, valid нь (в)-гүй (ADR 0005)",
        "train_from": str(TRAIN_FROM.date()), "train_rows": int(len(tr)), "valid_rows": int(len(va)),
        "optuna": {"sampler": "TPE", "pruner": "MedianPruner", "n_trials": n_trials, "early_stopping": EARLY_STOP},
        "valid_table": table[cols].round(5).to_dict("records"),
    })
    return {"studies": studies, "fitted": fitted, "table": table, "winner": winner, "meta": meta,
            "train": tr, "valid": va, "features": features}


if __name__ == "__main__":
    run()
