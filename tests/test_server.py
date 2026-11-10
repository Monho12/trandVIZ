"""app/main.Server-ийн санах ойн загвар (ADR 0012): Snapshot-д зөвхөн сүүлийн KEEP_DAYS өдөр, түүхий cache-ийг
санах ойд барихгүй, шинэчлэлт дискнээс уншиж data/live/-д бичнэ.  pytest -q"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import app.main as m  # noqa: E402
from src import clean, evaluate, serve  # noqa: E402
from test_live import TODAY, FakeFetcher, cache_ending  # noqa: E402


def test_snapshot_keeps_only_recent_days_but_history_stats_use_full_clean(monkeypatch):
    raw = cache_ending(pd.Timestamp("2026-11-09"), days=700)   # train (≤ 2025-06-30) хэсэгтэй
    raw = m.live.RawCache(pd.concat([raw.pageviews, raw.pageviews.assign(article="C"), raw.pageviews.assign(article="Ä")]),
                          raw.alias, raw.total)
    monkeypatch.setattr(serve, "CHUNK_ARTICLES", 2)     # сэдвийн хэсгүүдээр цэвэрлэх нь бүтэн хүснэгттэй ижил
    end = pd.Timestamp("2026-11-03")
    snap = serve.Snapshot.from_raw(raw, test_end=end)
    full, _ = clean.clean_frame(raw.pageviews, raw.alias, raw.total, end=raw.end)
    assert serve.KEEP_DAYS >= serve.FEATURE_DAYS and serve.KEEP_DAYS >= serve.TOPIC_DAYS
    # index-ийг оролцуулан бүтэн хүснэгтийн сүүлийн KEEP_DAYS өдрийн мөрүүд
    pd.testing.assert_frame_equal(snap.clean, full[full["date"] > raw.end - pd.Timedelta(days=serve.KEEP_DAYS)])
    assert snap.clean["date"].min() == raw.end - pd.Timedelta(days=serve.KEEP_DAYS - 1)
    want = evaluate.history_stats(full, end)
    assert snap.history == want and want["topics"] == 4 and want["clean_rows"] > len(snap.clean)


def test_chunked_history_stats_equal_full_on_real_data():
    """Бодит data/processed дээр: сэдвийн хэсгүүдээр тооцсон /api/model-ийн тоо бүтэн хүснэгтээр тооцсонтой ижил."""
    raw = m.live.RawCache.load(m.PROCESSED)
    end = pd.Timestamp(m.train.load().meta["test"]["test_end"])
    full, _ = clean.clean_frame(raw.pageviews, raw.alias, raw.total, end=raw.end)
    snap = serve.Snapshot.from_raw(raw, test_end=end)
    assert snap.history == evaluate.history_stats(full, end)
    pd.testing.assert_frame_equal(snap.clean, full[full["date"] > raw.end - pd.Timedelta(days=serve.KEEP_DAYS)])


def test_refresh_reads_cache_from_disk_writes_live_and_swaps_snapshot(tmp_path, monkeypatch):
    processed, live_dir = tmp_path / "processed", tmp_path / "live"
    cache_ending(TODAY - pd.Timedelta(days=3)).save(processed)
    monkeypatch.setattr(m, "PROCESSED", processed)
    monkeypatch.setattr(m, "LIVE_DIR", live_dir)
    monkeypatch.setattr(m, "utc_now", lambda: TODAY)
    srv = m.Server()
    srv.start(refresh=False)
    assert not hasattr(srv, "raw")                       # түүхий cache санах ойд үлдэхгүй
    old = srv.snapshot
    assert old.asof == TODAY - pd.Timedelta(days=3)

    class OneShot(FakeFetcher):                          # нэг оролдлогын дараа loop-ийг зогсооно
        def article(self, title, start, end):
            srv._stop.set()
            return super().article(title, start, end)

    monkeypatch.setattr(m.live, "WikiFetcher", OneShot)
    srv._loop()
    assert srv.refresh["status"] == m.live.OK
    assert srv.snapshot is not old and srv.snapshot.asof == TODAY - pd.Timedelta(days=1)
    assert m.live.RawCache.load(live_dir).end == TODAY - pd.Timedelta(days=1)
    assert m.load_raw().end == srv.snapshot.asof          # дараагийн оролдлого data/live/-ээс эхэлнэ
