from unittest.mock import MagicMock

from googleapiclient.errors import HttpError

from src.collectors import youtube


def _client(search_items, comments=None, comments_error=False, languages=None):
    yt = MagicMock()
    yt.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"id": vid, "snippet": ({"defaultAudioLanguage": lang} if lang else {})}
                  for vid, lang in (languages or {}).items()]}
    yt.search.return_value.list.return_value.execute.return_value = {"items": search_items}
    ct = yt.commentThreads.return_value.list.return_value.execute
    if comments_error:
        ct.side_effect = HttpError(MagicMock(status=403), b"commentsDisabled")
    else:
        ct.return_value = {"items": comments or []}
    return yt


def _video(vid="v1", title="Review da operadora Vivo"):
    return {"id": {"videoId": vid},
            "snippet": {"publishedAt": "2026-10-20T10:00:00Z", "title": title, "description": "desc",
                        "channelId": "UC123"}}


def _comment(cid="c1"):
    return {"id": cid, "snippet": {"topLevelComment": {"snippet": {
        "publishedAt": "2026-10-20T11:00:00Z", "textDisplay": "atendimento ruim", "likeCount": 3,
        "authorChannelId": {"value": "UCauthor"}}}}}


def _patch(monkeypatch, yt, queries=None):
    monkeypatch.setattr(youtube, "build", lambda *a, **k: yt)
    monkeypatch.setattr(youtube, "load_queries", lambda: queries or {"marca": ['"operadora Vivo"']})


def test_youtube_videos_and_comments(monkeypatch):
    _patch(monkeypatch, _client([_video()], [_comment()]))
    rows = youtube.collect(days=1)
    assert [r["source"] for r in rows] == ["youtube_video", "youtube_comment"]
    assert rows[0]["mention_id"] == "v1|marca" and rows[0]["query_group"] == "marca"
    comment = rows[1]
    assert comment["engagement"] == 3 and comment["mention_id"] == "c1|marca"
    assert comment["author_hash"] and "UCauthor" not in str(comment)  # LGPD: nada em claro
    assert "UC123" not in str(rows[0])


def test_youtube_irrelevant_video_and_its_comments_are_dropped(monkeypatch):
    yt = _client([_video("ufo", "OVNIs: segredos na Casa Branca"), _video("live", "Show AO VIVO hoje")],
                 [_comment()])
    _patch(monkeypatch, yt)
    assert youtube.collect() == []
    yt.commentThreads.return_value.list.assert_not_called()  # não gasta cota com ruído


def test_youtube_comparison_video_is_stored_once_per_matching_group(monkeypatch):
    yt = _client([_video("cmp", "Operadora Vivo vs operadora Claro: qual vale mais?")], [_comment()])
    _patch(monkeypatch, yt)
    rows = youtube.collect()
    videos = {r["mention_id"] for r in rows if r["source"] == "youtube_video"}
    assert videos == {"cmp|marca", "cmp|concorrente_a"}
    assert len({r["mention_id"] for r in rows}) == len(rows)  # chaves únicas: o MERGE não colapsa
    assert yt.commentThreads.return_value.list.call_count == 1  # comentários buscados uma vez


def test_youtube_same_video_from_two_searches_is_not_duplicated(monkeypatch):
    yt = _client([_video()], [_comment()])
    _patch(monkeypatch, yt, {"marca": ['"operadora Vivo"', '"Vivo Fibra"']})
    rows = youtube.collect()
    assert len(rows) == 2
    assert yt.commentThreads.return_value.list.call_count == 1


def test_youtube_comments_disabled_is_skipped(monkeypatch):
    _patch(monkeypatch, _client([_video()], comments_error=True))
    assert [r["source"] for r in youtube.collect()] == ["youtube_video"]


def test_youtube_quota_guard_stops_searching(monkeypatch):
    monkeypatch.setattr(youtube, "UNIT_BUDGET", 150)  # cabe 1 busca (100) e 1 comentário
    yt = _client([_video()], [_comment()])
    _patch(monkeypatch, yt, {"marca": ["a", "b", "c"]})
    youtube.collect()
    assert yt.search.return_value.list.call_count == 1


def test_youtube_unescapes_html_entities(monkeypatch):
    _patch(monkeypatch, _client([_video("v9", "teste &quot;operadora Vivo&quot; &amp; fibra")]))
    assert youtube.collect()[0]["text"].startswith('teste "operadora Vivo" & fibra')


def test_youtube_drops_declared_foreign_language_keeps_undeclared(monkeypatch):
    items = [_video("pt1"), _video("en1"), _video("nolang")]
    yt = _client(items, [_comment()], languages={"pt1": "pt-BR", "en1": "en", "nolang": None})
    _patch(monkeypatch, yt)
    ids = {r["mention_id"] for r in youtube.collect() if r["source"] == "youtube_video"}
    assert ids == {"pt1|marca", "nolang|marca"}  # en descartado; sem idioma declarado, mantém


def test_youtube_search_is_restricted_to_region_and_language(monkeypatch):
    yt = _client([_video()], [_comment()])
    _patch(monkeypatch, yt)
    youtube.collect()
    kw = yt.search.return_value.list.call_args.kwargs
    assert kw["regionCode"] == "BR" and kw["relevanceLanguage"] == "pt"
