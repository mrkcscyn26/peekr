"""T-10: live history (F5) through the watcher and reconciliation while the app was closed (F6).
These tests change files only inside a temporary test folder."""

import os
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import FakeLLM, make_cfg, wait_for, wait_job


def write_txt(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def events_for(client, name):
    out = client.post("/api/search", json={"query": name, "limit": 50}).json()
    for r in out["results"]:
        if r["name"] == name:
            return r["file_id"], [e["event_type"] for e in client.get(f"/api/files/{r['file_id']}/history").json()["events"]]
    return None, []


def history_of(client, fid):
    return [e["event_type"] for e in client.get(f"/api/files/{fid}/history").json()["events"]]


@pytest.fixture
def live(tmp_path, embedder):
    root = tmp_path / "watched"
    write_txt(root / "School" / "notes_biology.txt", "Biology notes about mangrove ecosystems and fish nurseries.")
    write_txt(root / "Finance" / "rent.txt", "Rent receipt for the apartment, PHP 12,000 paid in cash.")
    app = create_app(make_cfg(tmp_path / "data"), embedder=embedder, llm=FakeLLM())
    with TestClient(app) as c:
        fid = c.post("/api/folders", json={"path": str(root)}).json()["folder"]["id"]
        c.post("/api/index/start", json={"folder_id": fid})
        wait_job(c)
        assert wait_for(lambda: fid in c.app.state.ctx.watcher.watching())
        yield c, root, tmp_path


def test_live_create_edit_rename_move_delete(live):
    c, root, _ = live
    fid, ev = events_for(c, "notes_biology.txt")
    assert ev == ["baseline"]

    write_txt(root / "School" / "new_lesson.txt", "Lesson plan about the water cycle: evaporation and condensation.")
    new_id = wait_for(lambda: events_for(c, "new_lesson.txt")[0])
    assert new_id and history_of(c, new_id) == ["created"]

    with open(root / "School" / "notes_biology.txt", "a", encoding="utf-8") as fh:
        fh.write("\nAdded: crabs and shrimp also live in mangroves.")
    assert wait_for(lambda: history_of(c, fid)[0] == "modified")
    snippet = c.post("/api/search", json={"query": "crabs shrimp mangroves"}).json()["results"][0]
    assert snippet["file_id"] == fid

    os.rename(root / "School" / "notes_biology.txt", root / "School" / "bio_notes.txt")
    assert wait_for(lambda: history_of(c, fid)[0] == "renamed")
    assert c.get(f"/api/files/{fid}").json()["name"] == "bio_notes.txt"

    (root / "Archive").mkdir()
    shutil.move(str(root / "School" / "bio_notes.txt"), str(root / "Archive" / "bio_notes.txt"))
    assert wait_for(lambda: history_of(c, fid)[0] == "moved")
    assert c.get(f"/api/files/{fid}").json()["path"].endswith(os.path.join("Archive", "bio_notes.txt"))

    os.remove(root / "Archive" / "bio_notes.txt")
    assert wait_for(lambda: history_of(c, fid)[0] == "deleted", timeout=20)
    assert c.get(f"/api/files/{fid}").json()["status"] == "deleted"
    assert history_of(c, fid) == ["deleted", "moved", "renamed", "modified", "baseline"]
    assert all(r["file_id"] != fid for r in c.post("/api/search", json={"query": "mangrove"}).json()["results"])


def test_temp_files_ignored(live):
    c, root, _ = live
    write_txt(root / "School" / "~$temp.docx", "owner file")
    write_txt(root / "School" / "download.tmp", "partial")
    time.sleep(2.5)
    c.app.state.ctx.indexer.wait_idle(30)
    names = {r["name"] for r in c.post("/api/search", json={"query": "", "limit": 50}).json()["results"]}
    assert names == {"notes_biology.txt", "rent.txt"}


def test_reconcile_changes_made_while_closed(tmp_path, embedder):
    root = tmp_path / "docs"
    write_txt(root / "a" / "keep.txt", "Unchanged note about guitar practice and chords.")
    write_txt(root / "a" / "edit.txt", "Original budget plan for December.")
    write_txt(root / "a" / "rename_me.txt", "Passport appointment checklist and requirements.")
    write_txt(root / "a" / "move_me.txt", "Vaccination schedule for the puppy.")
    write_txt(root / "a" / "delete_me.txt", "Old grocery list with rice and eggs.")
    cfg = make_cfg(tmp_path / "data")
    with TestClient(create_app(cfg, embedder=embedder, llm=FakeLLM())) as c:
        fid = c.post("/api/folders", json={"path": str(root)}).json()["folder"]["id"]
        c.post("/api/index/start", json={"folder_id": fid})
        wait_job(c)
        ids = {n: events_for(c, n)[0] for n in ("keep.txt", "edit.txt", "rename_me.txt", "move_me.txt", "delete_me.txt")}
    # app closed: change files
    time.sleep(0.05)
    with open(root / "a" / "edit.txt", "a", encoding="utf-8") as fh:
        fh.write(" Updated with Noche Buena budget.")
    os.rename(root / "a" / "rename_me.txt", root / "a" / "renamed.txt")
    (root / "b").mkdir()
    shutil.move(str(root / "a" / "move_me.txt"), str(root / "b" / "move_me.txt"))
    os.remove(root / "a" / "delete_me.txt")
    write_txt(root / "b" / "brand_new.txt", "New note about the Baguio trip itinerary.")
    with TestClient(create_app(cfg, embedder=embedder, llm=FakeLLM())) as c:
        st = wait_job(c)  # startup reconciliation (F1 step 7)
        assert st["kind"] == "rescan" and st["state"] == "done" and st["unchanged"] == 1
        assert history_of(c, ids["keep.txt"]) == ["baseline"]
        assert history_of(c, ids["edit.txt"]) == ["modified", "baseline"]
        assert history_of(c, ids["rename_me.txt"]) == ["renamed", "baseline"]
        assert history_of(c, ids["move_me.txt"]) == ["moved", "baseline"]
        assert history_of(c, ids["delete_me.txt"]) == ["deleted", "baseline"]
        new_id, ev = events_for(c, "brand_new.txt")
        assert ev == ["created"]
        srcs = {e["source"] for e in c.get(f"/api/files/{ids['edit.txt']}/history").json()["events"][:1]}
        assert srcs == {"reconcile"}


def test_unavailable_folder_files_not_deleted(tmp_path, embedder):
    root = tmp_path / "usb"
    write_txt(root / "x.txt", "Notes saved on a removable drive about the thesis.")
    cfg = make_cfg(tmp_path / "data")
    with TestClient(create_app(cfg, embedder=embedder, llm=FakeLLM())) as c:
        fid = c.post("/api/folders", json={"path": str(root)}).json()["folder"]["id"]
        c.post("/api/index/start", json={"folder_id": fid})
        wait_job(c)
        xid = events_for(c, "x.txt")[0]
    os.rename(root, tmp_path / "usb_unplugged")  # simulate a disconnected drive
    with TestClient(create_app(cfg, embedder=embedder, llm=FakeLLM())) as c:
        st = wait_job(c)
        assert st["unavailable_folders"] == [fid]
        assert c.get("/api/folders").json()["folders"][0]["available"] is False
        assert c.get(f"/api/files/{xid}").json()["status"] == "indexed"
        assert history_of(c, xid) == ["baseline"]
