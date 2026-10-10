from openjarvis.tools import x_analytics as xa


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_csv_summary_and_top(tmp_path, monkeypatch):
    monkeypatch.setattr(xa, "EXPORT_DIR", tmp_path)
    _write(tmp_path, "tweet_activity.csv",
           '﻿"Tweet id","Tweet text","time","impressions","likes","replies","engagement rate"\n'
           '"1","Mi optimizer","2026-10-01 10:00 +0000","1,000","10","2","1.5%"\n'
           '"2","Video moto","2026-10-02 10:00 +0000","5000","80","9","3.2%"\n'
           '"3","Otro","2026-10-03 10:00 +0000","200","1","0","0.5%"\n')
    tool = xa.XAnalyticsTool()
    summary = tool.execute(action="summary", file="tweet_activity.csv").content
    assert "EXACT TOTAL: 3 posts" in summary and "impressions: total 6200" in summary
    top = tool.execute(action="top_posts", file="tweet_activity.csv", limit=2).content
    assert top.splitlines()[1].startswith("1. impressions 5000") and "Video moto" in top


def test_archive_skips_retweets_and_has_no_impressions(tmp_path, monkeypatch):
    monkeypatch.setattr(xa, "EXPORT_DIR", tmp_path)
    _write(tmp_path, "tweets.js",
           'window.YTD.tweets.part0 = [{"tweet":{"id_str":"9","full_text":"hola","favorite_count":"7","retweet_count":"1","created_at":"x"}},'
           '{"tweet":{"id_str":"8","full_text":"RT @a: x","favorite_count":"0","retweet_count":"0"}}]')
    tool = xa.XAnalyticsTool()
    assert "1 posts" in tool.execute(action="summary", file="tweets.js").content
    assert not tool.execute(action="top_posts", file="tweets.js", metric="impressions").success


def test_only_files_inside_the_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(xa, "EXPORT_DIR", tmp_path / "x")
    (tmp_path / "secret.csv").write_text('"Tweet text","likes"\n"a","1"\n', encoding="utf-8")
    tool = xa.XAnalyticsTool()
    for bad in ("../secret.csv", str(tmp_path / "secret.csv"), "evil.exe"):
        assert not tool.execute(action="summary", file=bad).success
    assert "No X export files" in tool.execute(action="list_files").content
