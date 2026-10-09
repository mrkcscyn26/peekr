"""T-01, T-05, T-06, T-07, T-09 through the HTTP API (F1-F4, F7) on a copy of the demo data.
The fake LLM stands in for Ollama; Ollama itself is configured at an unused port."""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app.core import os_actions
from app.main import create_app
from conftest import FakeLLM, copy_tree, make_cfg, wait_job
from make_demo_data import BAD_FILES, DOCS


@pytest.fixture(scope="module")
def env(tmp_path_factory, demo_src, embedder):
    base = tmp_path_factory.mktemp("api")
    demo = copy_tree(demo_src, base / "demo")
    llm = FakeLLM()
    app = create_app(make_cfg(base / "data"), embedder=embedder, llm=llm)
    with TestClient(app) as client:
        r = client.post("/api/folders", json={"path": str(demo)})
        assert r.status_code == 200, r.text
        folder = r.json()["folder"]
        job = client.post("/api/index/start", json={"folder_id": folder["id"], "kind": "initial"}).json()
        status = wait_job(client)
        yield {"client": client, "demo": demo, "folder": folder, "job": job, "status": status, "llm": llm,
               "base": base}


def find(client, query, **kw):
    r = client.post("/api/search", json={"query": query, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def file_id(client, name):
    for r in find(client, os.path.splitext(name)[0].replace("_", " "), limit=50)["results"]:
        if r["name"] == name:
            return r["file_id"]
    raise AssertionError(name)


def test_health_with_ollama_stopped_and_local_only(env):
    env["llm"].down = True
    env["client"].app.state.ctx.health._ollama = None  # drop the 5 s cache
    h = env["client"].get("/api/health").json()
    env["llm"].down = False
    assert h["local_only"] is True and h["embedder_ready"] is True and h["db_ok"] is True
    assert h["ollama_ok"] is False and h["llm_ready"] is False
    assert h["ollama_url"] == "http://127.0.0.1:1" and h["embedding_model"] and h["embedding_device"]
    env["client"].app.state.ctx.health._ollama = None


def test_categories_from_config(env):
    cats = env["client"].get("/api/categories").json()["categories"]
    labels = env["client"].app.state.ctx.cfg.category.labels
    assert [c["name"] for c in cats] == list(labels) and all(c["description"] for c in cats)


def test_cdn_doc_pages_disabled_and_ui_served(env):
    c = env["client"]
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404
    assert c.get("/").status_code == 200


def test_folder_validation_errors(env, tmp_path):
    c, demo = env["client"], env["demo"]
    assert c.post("/api/folders", json={"path": str(demo)}).json()["error"]["code"] == "already_added"
    r = c.post("/api/folders", json={"path": str(demo / "School")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_path"
    assert c.post("/api/folders", json={"path": str(tmp_path / "nope")}).json()["error"]["code"] == "invalid_path"
    assert c.post("/api/folders", json={"path": os.environ.get("SystemRoot", r"C:\Windows")}).status_code == 400
    assert c.post("/api/folders", json={"path": "C:\\"}).status_code == 400
    assert c.delete("/api/folders/9999").json()["error"]["code"] == "folder_not_found"
    assert c.post("/api/index/start", json={"folder_id": 9999}).status_code == 404
    assert c.post("/api/folders", json={}).json()["error"]["code"] == "invalid_request"


def test_index_job_done_with_progress_and_skips(env):
    s = env["status"]
    assert s["state"] == "done" and s["job_id"] == env["job"]["job_id"]
    assert s["total"] == len(DOCS) + len(BAD_FILES) == s["processed"]
    reasons = {os.path.basename(i["path"]): i["reason"] for i in s["skipped_items"]}
    assert reasons == BAD_FILES
    folders = env["client"].get("/api/folders").json()["folders"]
    assert folders[0]["available"] and folders[0]["last_scan_at"] and folders[0]["file_count"] == s["total"]


def test_rerun_skips_unchanged_files(env):
    c = env["client"]
    c.post("/api/index/start", json={"kind": "rescan"})
    s = wait_job(c)
    n_skipped = sum(r != "extract_failed" for r in BAD_FILES.values())  # skipped files wait for a change
    assert s["state"] == "done" and s["unchanged"] == len(DOCS) + n_skipped and s["skipped"] == 0
    # error-status files are retried on rescan (Section 8.11), and fail again
    assert s["errors"] == sum(r == "extract_failed" for r in BAD_FILES.values())


def test_user_files_untouched(env, demo_src):
    for rel, *_ in DOCS:
        a, b = env["demo"] / rel, demo_src / rel
        assert a.read_bytes() == b.read_bytes() and a.stat().st_mtime == b.stat().st_mtime


def test_search_result_fields_and_hybrid(env):
    c = env["client"]
    out = find(c, "Meralco")  # exact term
    assert out["results"][0]["name"].startswith("meralco_bill")
    r = out["results"][0]
    for k in ("file_id", "name", "extension", "path", "folder", "category", "modified_at", "score", "snippet",
              "location", "summary_cached"):
        assert k in r, k
    assert "Meralco" in r["snippet"] and r["location"].startswith("page") and r["category"]
    assert out["elapsed_ms"] < 3000
    desc = find(c, "contract for renting an apartment")  # descriptive, unhelpful file name
    assert "scan_0012.pdf" in [x["name"] for x in desc["results"][:3]]


def test_search_filters_and_relaxation(env):
    c = env["client"]
    out = find(c, "kuryente bill last month")
    assert out["parsed"]["date_from"] and out["results"][0]["name"] == "meralco_bill_september.pdf"
    assert all(x["name"] != "meralco_bill_august.pdf" for x in out["results"])
    out = find(c, "pdf sa Downloads tungkol sa passport")
    assert out["parsed"]["folder_hint"] == "downloads"
    assert all(x["extension"] == ".pdf" and "Downloads" in x["path"] for x in out["results"])
    assert out["results"][0]["name"] == "passport_appointment_checklist.pdf"
    listing = find(c, "slides")
    assert listing["results"] and all(x["extension"] == ".pptx" for x in listing["results"])
    mods = [x["modified_at"] for x in listing["results"]]
    assert mods == sorted(mods, reverse=True)
    relaxed = find(c, "adobo recipe sa Lutuin folder")  # no such folder -> folder_hint dropped
    assert relaxed["relaxed_filters"] is True and relaxed["results"][0]["name"] == "adobong_manok.txt"
    assert find(c, "")["results"]  # empty query lists newest files


def test_file_metadata_summary_cache_and_fallback(env):
    c, llm = env["client"], env["llm"]
    fid = file_id(c, "baguio_itinerary.pdf")
    meta = c.get(f"/api/files/{fid}").json()
    assert meta["status"] == "indexed" and meta["folder"].endswith("Travel") and meta["summary_cached"] is False
    assert c.get("/api/files/99999").json()["error"]["code"] == "file_not_found"
    first = c.post(f"/api/files/{fid}/summary").json()
    assert first["cached"] is False and first["fallback"] is False and first["summary"].startswith("Summary")
    second = c.post(f"/api/files/{fid}/summary", json={}).json()
    assert second["cached"] is True and second["summary"] == first["summary"]
    assert c.get(f"/api/files/{fid}").json()["summary_cached"] is True
    forced = c.post(f"/api/files/{fid}/summary", json={"force": True}).json()
    assert forced["cached"] is False and forced["summary"] != first["summary"]
    llm.down = True
    other = file_id(c, "cebu_bohol_trip_plan.docx")
    fb = c.post(f"/api/files/{other}/summary").json()
    llm.down = False
    assert fb["fallback"] is True and fb["summary"] and len(fb["summary"]) <= 403
    assert c.post(f"/api/files/{other}/summary").json()["fallback"] is False  # fallback was not cached


def test_history_baseline(env):
    c = env["client"]
    fid = file_id(c, "baguio_itinerary.pdf")
    ev = c.get(f"/api/files/{fid}/history").json()["events"]
    assert [e["event_type"] for e in ev] == ["baseline"] and ev[0]["source"] == "scan"


def test_list_files_by_status(env):
    c = env["client"]
    files = c.get("/api/files").json()["files"]
    assert len(files) == len(DOCS) and all(f["status"] == "indexed" for f in files)
    for k in ("id", "folder_id", "name", "extension", "path", "folder", "size_bytes", "created_at", "modified_at",
              "category", "status", "status_reason"):
        assert k in files[0], k
    assert all(f["size_bytes"] > 0 and f["category"] for f in files)
    bad = c.get("/api/files", params={"status": "skipped,error"}).json()["files"]
    assert {f["name"]: f["status_reason"] for f in bad} == BAD_FILES
    r = c.get("/api/files", params={"status": "indexed,bogus"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"


def test_search_overrides(env):
    c = env["client"]
    assert all(x["extension"] == ".pptx" for x in find(c, "slides", limit=50)["results"])
    loose = find(c, "slides", limit=50, ignore=["extensions"])
    assert loose["parsed"]["extensions"] == [] and {x["extension"] for x in loose["results"]} != {".pptx"}
    nodate = find(c, "kuryente bill last month", ignore=["date"])
    assert nodate["parsed"]["date_from"] is None
    assert {"meralco_bill_september.pdf", "meralco_bill_august.pdf"} <= {x["name"] for x in nodate["results"]}
    ranged = find(c, "", date_from="2100-01-01T00:00:00+08:00", date_to="2100-02-01T00:00:00+08:00")
    assert ranged["parsed"]["date_from"] == "2099-12-31T16:00:00+00:00"
    assert ranged["relaxed_filters"] is True  # nothing in 2100, so the date filter was relaxed (F3)
    both = find(c, "", date_from="2100-01-01T00:00:00Z", date_to="2100-02-01T00:00:00Z", ignore=["date"])
    assert both["parsed"]["date_from"] is None
    for body in ({"date_from": "2100-01-01T00:00:00Z"}, {"date_from": "2100-01-01T00:00:00",
                 "date_to": "2100-02-01T00:00:00"}, {"date_from": "2100-02-01T00:00:00Z",
                 "date_to": "2100-01-01T00:00:00Z"}, {"date_from": "soon", "date_to": "later"}, {"ignore": ["size"]}):
        r = c.post("/api/search", json={"query": "budget", **body})
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request", body


def test_recent_events_feed(env):
    c = env["client"]
    ev = c.get("/api/events").json()["events"]
    assert ev and all(e["event_type"] == "baseline" and e["name"] and e["path"] for e in ev)
    times = [e["occurred_at"] for e in ev]
    assert times == sorted(times, reverse=True)
    assert len(c.get("/api/events", params={"limit": 1}).json()["events"]) == 1
    assert c.get("/api/events", params={"type": "moved"}).json()["events"] == []
    assert c.get("/api/events", params={"type": "bogus"}).json()["error"]["code"] == "invalid_request"
    assert c.get("/api/events", params={"limit": 0}).status_code == 400


def test_open_endpoints_use_stored_path(env, monkeypatch):
    c = env["client"]
    opened = []
    monkeypatch.setattr(os_actions, "open_file", lambda p: opened.append(("file", p)))
    monkeypatch.setattr(os_actions, "open_folder", lambda p: opened.append(("folder", p)))
    fid = file_id(c, "baguio_itinerary.pdf")
    assert c.post(f"/api/files/{fid}/open").json() == {"ok": True}
    assert c.post(f"/api/files/{fid}/open-folder").json() == {"ok": True}
    assert opened[0][1].endswith("baguio_itinerary.pdf") and opened[0][1] == opened[1][1]

    def boom(p):
        raise os_actions.OsActionError("no app associated")
    monkeypatch.setattr(os_actions, "open_file", boom)
    r = c.post(f"/api/files/{fid}/open")
    assert r.status_code == 500 and r.json()["error"]["code"] == "os_error"


def test_search_while_embedder_loading_returns_503(env):
    ctx = env["client"].app.state.ctx
    ctx.embedder.ready.clear()
    try:
        r = env["client"].post("/api/search", json={"query": "budget"})
        assert r.status_code == 503 and r.json()["error"]["code"] == "embedder_not_ready"
        assert env["client"].post("/api/search", json={"query": "pdf"}).status_code == 200  # no semantic text
    finally:
        ctx.embedder.ready.set()


def test_exclusion_removes_files(env):
    c, demo, fid = env["client"], env["demo"], env["folder"]["id"]
    assert c.post(f"/api/folders/{fid}/exclusions", json={"path": "..\\.."}).status_code == 400
    assert c.post(f"/api/folders/{fid}/exclusions", json={"path": "Personal\\Hobbies"}).json() == {"ok": True}
    wait_job(c)
    assert all(r["name"] != "guitar_chords_practice.txt" for r in find(c, "guitar chords", limit=50)["results"])
    excl = c.get("/api/folders").json()["folders"][0]["exclusions"]
    assert len(excl) == 1 and excl[0].endswith("Personal\\Hobbies")


def test_missing_file_and_forbidden(env, monkeypatch):
    c, demo = env["client"], env["demo"]
    monkeypatch.setattr(os_actions, "open_file", lambda p: None)
    fid = file_id(c, "nbi_clearance_guide.txt")
    # Simulate the file vanishing while the app has not processed it yet: pause the watcher.
    ctx = c.app.state.ctx
    ctx.watcher.unwatch(env["folder"]["id"])
    hidden = demo / "Downloads" / "nbi_clearance_guide.txt"
    os.replace(hidden, env["base"] / "nbi_moved_away.txt")  # test-owned copy, not user data
    r = c.post(f"/api/files/{fid}/open")
    assert r.status_code == 404 and r.json()["error"]["code"] == "file_missing"
    wait_job(c)
    assert c.get(f"/api/files/{fid}").json()["status"] == "deleted"
    assert c.get(f"/api/files/{fid}/history").json()["events"][0]["event_type"] == "deleted"
    ctx.watcher.watch(env["folder"]["id"], str(demo))


def test_remove_folder_cascades_last(env):
    c = env["client"]
    fid = env["folder"]["id"]
    assert c.delete(f"/api/folders/{fid}").json() == {"ok": True}
    assert c.get("/api/folders").json()["folders"] == []
    assert find(c, "budget")["reason"] == "no_indexed_files"
    assert (env["demo"] / "Personal/Travel/baguio_itinerary.pdf").exists()  # disk untouched
