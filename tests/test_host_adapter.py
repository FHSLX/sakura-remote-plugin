from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

import http_server


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=")


class Artifacts:
    def __init__(self, root):
        self.root = root
        self.live = {}
        self.released = []
        self.sequence = 0

    def allocate(self, descriptor):
        self.sequence += 1
        identity = f"artifact_{self.sequence}"
        value = {"artifactId": identity, "mediaType": descriptor["mediaType"],
                 "path": str(self.root / (identity + descriptor["suffix"]))}
        self.live[identity] = value
        return dict(value)

    def commit(self, identity):
        value = self.live[identity]
        value["byteLength"] = Path(value["path"]).stat().st_size
        return {key: value[key] for key in ("artifactId", "mediaType", "byteLength")}

    def resolve(self, identity):
        return dict(self.live[identity])

    def release(self, identity):
        value = self.live.pop(identity)
        Path(value["path"]).unlink(missing_ok=True)
        self.released.append(identity)

    release_received = release


@pytest.fixture
def remote(tmp_path):
    artifacts = Artifacts(tmp_path)
    replies = [{"entryId": "reply-1", "characterId": "sakura", "kind": "assistant",
                "createdAt": "2026-09-28T12:00:00Z", "payload": {"segments": [
                    {"text": "", "translation": ""},
                    {"text": "こんにちは", "translation": "你好", "tone": "中性", "suppressTts": False},
                ]}}]
    calls = []

    def begin(*args):
        calls.append(args)
        return {"jobId": "conversation-1"}

    def speech_begin(character, entry, index):
        allocation = artifacts.allocate({"mediaType": "audio/wav", "suffix": ".wav"})
        Path(allocation["path"]).write_bytes(b"RIFF-test-audio")
        descriptor = artifacts.commit(allocation["artifactId"])
        speech.calls.append((character, entry, index))
        speech.results["speech-1"] = {"status": "completed", "result": {"artifact": descriptor}}
        return {"jobId": "speech-1"}

    conversation = SimpleNamespace(begin=begin, poll=lambda job: {"status": "completed", "result": {
        "character_id": "sakura", "historyEntryId": "reply-1", "segments": [
            {"segmentIndex": 1, "raw_content": "こんにちは", "content": "你好", "suppressTts": False},
        ]}}, cancel=lambda job: None)
    speech = SimpleNamespace(calls=[], results={}, begin=speech_begin,
                             poll=lambda job: speech.results.pop(job), cancel=lambda job: None)
    characters = SimpleNamespace(
        list=lambda: [{"id": "sakura", "displayName": "Sakura", "initialMessage": "hello", "current": True}],
        presentation=lambda: {"characterId": "sakura", "themeTokens": {"primary": "#123456"}},
        resolve_resource=lambda character, relative: str(tmp_path / relative),
    )
    visual = SimpleNamespace(current=lambda: {"target": {"characterId": "sakura", "resourceId": "portrait"},
                                               "type": "sakura.visual.portrait@1"})
    timeline = SimpleNamespace(read_recent=lambda request: {"entries": replies})
    service = http_server.RemoteService(tmp_path, conversation_service=conversation,
        character_service=characters, timeline_service=timeline, artifact_service=artifacts,
        speech_service=speech, visual_service=visual, logger=None)
    return SimpleNamespace(service=service, calls=calls, artifacts=artifacts, speech=speech,
                           conversation=conversation, replies=replies, root=tmp_path, visual=visual)


def test_text_uses_empty_descriptor_and_preserves_reply_identity(remote):
    reply = remote.service.chat("sakura", "你好")
    assert remote.calls == [("sakura", "你好", {})]
    assert reply["historyEntryId"] == "reply-1"
    assert reply["segments"][0]["segmentIndex"] == 1


def test_access_log_does_not_record_token_query(remote):
    remote.service.log_access("GET", "/api/state?token=private-token&character=sakura", ("127.0.0.1", 123), 200)
    record = json.loads((remote.root / "logs/remote-access.log").read_text(encoding="utf-8"))
    assert record["path"] == "/api/state"
    assert "private-token" not in json.dumps(record)


def test_image_is_committed_before_conversation(remote):
    remote.service.chat("sakura", "看图", "data:image/png;base64," + base64.b64encode(PNG).decode())
    descriptor = remote.calls[0][2]
    assert set(descriptor) == {"artifactId", "mediaType", "byteLength"}
    assert descriptor["mediaType"] == "image/png"
    assert descriptor["byteLength"] == len(PNG)
    assert Path(remote.artifacts.resolve(descriptor["artifactId"])["path"]).read_bytes() == PNG


def test_rejected_begin_releases_image(remote):
    def reject(*args):
        raise RuntimeError("CHAT_SESSION_STALE")
    remote.conversation.begin = reject
    with pytest.raises(RuntimeError, match="CHAT_SESSION_STALE"):
        remote.service.chat("sakura", "image", "data:image/png;base64," + base64.b64encode(PNG).decode())
    assert remote.artifacts.live == {}


@pytest.mark.parametrize("image", ["file:///private.png", "data:text/plain;base64,aGVsbG8=", "data:image/png;base64,!bad!"])
def test_invalid_image_never_reaches_conversation(remote, image):
    with pytest.raises(ValueError):
        remote.service.chat("sakura", "image", image)
    assert remote.calls == []
    assert remote.artifacts.live == {}


def test_history_preserves_legacy_http_projection(remote):
    remote.replies.insert(0, {"entryId": "human-1", "characterId": "sakura", "kind": "human",
                             "createdAt": "today", "payload": {"text": "question"}})
    history = remote.service.history("sakura")
    assert [(item["role"], item["content"]) for item in history] == [("user", "question"), ("assistant", "你好")]
    assert history[1]["raw_content"] == "こんにちは"


@pytest.mark.parametrize("resource_root", [".", "visuals/portrait"])
def test_portrait_uses_current_resource_and_parses_entry(remote, resource_root):
    manifest = {"visuals": {"default": "other", "resources": [
        {"id": "other", "type": "sakura.visual.portrait@1", "root": ".", "entry": "absent.json"},
        {"id": "portrait", "type": "sakura.visual.portrait@1", "root": resource_root, "entry": "resource.json"},
    ]}}
    (remote.root / "character.json").write_text(json.dumps(manifest), encoding="utf-8")
    root = remote.root / resource_root
    root.mkdir(parents=True, exist_ok=True)
    (root / "resource.json").write_text(json.dumps({"default": "portrait.png", "expressions": {"happy": "happy.png"}}), encoding="utf-8")
    (root / "portrait.png").write_bytes(PNG)
    (root / "happy.png").write_bytes(PNG + b"expression")
    assert remote.service.portrait_bytes("sakura", "__default__") == ("image/png", PNG)
    assert remote.service.portrait_bytes("sakura", "happy") == ("image/png", PNG + b"expression")


def test_legacy_portrait_remains_supported(remote):
    (remote.root / "character.json").write_text(json.dumps({"portrait": {"default": "portrait.png"}}), encoding="utf-8")
    (remote.root / "portrait.png").write_bytes(PNG)
    assert remote.service.portrait_bytes("sakura", "__default__") == ("image/png", PNG)


def test_missing_visual_does_not_guess_default_resource(remote):
    remote.visual.current = lambda: {"target": None, "reasonCode": "VISUAL_NOT_BOUND"}
    assert remote.service._portrait_map("sakura") == {}


def test_speech_reads_and_releases_each_delivery_beyond_old_limit(remote):
    for _ in range(20):
        assert remote.service.synthesize("sakura", "ignored input", "ignored tone", history_entry_id="reply-1", segment_index=1) == b"RIFF-test-audio"
        assert remote.artifacts.live == {}
    assert remote.speech.calls == [("sakura", "reply-1", 1)] * 20
    assert len(remote.artifacts.released) == 20


@pytest.mark.parametrize("text", ["こんにちは", "你好"])
def test_old_client_text_matches_saved_segment_at_original_index(remote, text):
    assert remote.service.synthesize("sakura", text) == b"RIFF-test-audio"
    assert remote.speech.calls == [("sakura", "reply-1", 1)]


@pytest.mark.parametrize("payload", [{"text": "arbitrary synthesis"}, {"history_entry_id": "reply-1", "segment_index": True}])
def test_unmatched_text_or_invalid_index_never_requests_speech(remote, payload):
    with pytest.raises(ValueError):
        remote.service.synthesize("sakura", **payload)
    assert remote.speech.calls == []


def test_stale_character_never_requests_speech(remote):
    with pytest.raises(ValueError):
        remote.service.synthesize("another", "こんにちは")
    assert remote.speech.calls == []


def test_audio_read_failure_still_releases_delivery(remote):
    resolve = remote.artifacts.resolve
    def missing_file(identity):
        value = resolve(identity)
        Path(value["path"]).unlink()
        return value
    remote.artifacts.resolve = missing_file
    with pytest.raises(FileNotFoundError):
        remote.service.synthesize("sakura", history_entry_id="reply-1", segment_index=1)
    assert remote.artifacts.live == {}


def test_speech_timeout_cancels_job(remote, monkeypatch):
    calls = []
    remote.speech.begin = lambda *args: {"jobId": "pending"}
    remote.speech.cancel = lambda job: calls.append(job)
    monkeypatch.setattr(http_server, "TTS_TIMEOUT_SECONDS", 0)
    with pytest.raises(TimeoutError):
        remote.service.synthesize("sakura", history_entry_id="reply-1", segment_index=1)
    assert calls == ["pending"]


def test_http_accepts_stable_and_legacy_audio_requests(remote):
    server = http_server.RemoteHTTPServer(("127.0.0.1", 0), http_server._build_handler(remote.service, "test-token"))
    server.service = remote.service
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for payload in ({"history_entry_id": "reply-1", "segment_index": 1}, {"text": "你好"}):
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/api/tts",
                data=json.dumps({"token": "test-token", "character_id": "sakura", **payload}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                assert response.headers["Content-Type"] == "audio/wav"
                assert response.read() == b"RIFF-test-audio"
            assert remote.artifacts.live == {}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
