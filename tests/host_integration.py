"""真实 Sakura 宿主、插件子进程与 HTTP；设置 SAKURA_SOURCE 后显式运行。"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace

SAKURA = Path(os.environ["SAKURA_SOURCE"]).resolve()
sys.path.insert(0, str(SAKURA))

from app.config.character_loader import CharacterRegistry
from app.core_host.plugin_runtime_application import PluginRuntimeApplication
from app.core_host.real_chat import RealChatBoundary
from app.core_host.tts_boundary import TTSBoundary
from app.plugin_sdk.sakura_assistant_contract import ChatReply, ChatSegment
from app.plugin_sdk.sakura_tools import ToolRegistry
from app.plugins.installer import LocalPluginInstaller
from app.plugins.inventory import PluginDesiredStateStore, PluginInventory
from app.storage.paths import StoragePaths
from app.storage.runtime_roots import RuntimeRoots
from app.storage.timeline import TimelineKind, TimelineStore

PLUGIN = Path(__file__).resolve().parents[1]
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=")

VOICE_FIXTURE = '''from pathlib import Path
import wave
class Plugin:
    def setup(self, context):
        self.artifacts = context.get("sakura.host.artifacts")
        self.jobs = {}
        self.count = 0
        context.provide("fixture.voice", self, exports=("status", "begin", "poll", "cancel", "calls"))
        context.get("sakura.tts").registerProvider({"providerId":"fixture.voice", "serviceKey":"fixture.voice", "label":"Fixture"})
    def status(self): return {"available":True}
    def calls(self): return self.count
    def begin(self, request):
        self.count += 1
        job = "voice-job-" + str(self.count)
        allocation = self.artifacts.allocate({"mediaType":"audio/wav", "suffix":".wav"})
        with wave.open(allocation["path"], "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b"\\x01\\x00" * 160)
        self.jobs[job] = self.artifacts.commit(allocation["artifactId"])
        return job
    def poll(self, job): return {"state":"succeeded", "artifact":self.jobs.pop(job)}
    def cancel(self, job): return False
'''


def test_remote_http_with_real_conversation_speech_and_portrait(tmp_path):
    distribution, user = tmp_path / "distribution", tmp_path / "user"
    bundled = distribution / "plugins/builtin"
    bundled.mkdir(parents=True)
    for name in ("sakura_tts_hub", "sakura_portrait"):
        shutil.copytree(SAKURA / "plugins/builtin" / name, bundled / name)
    voice = bundled / "fixture_voice"
    voice.mkdir()
    (voice / "plugin.py").write_text(VOICE_FIXTURE, encoding="utf-8")
    (voice / "plugin.yaml").write_text('''api: 4
id: fixture.voice
name: Fixture
version: 1.0.0
entry: plugin:Plugin
enabled: true
provides: [fixture.voice]
requires: [sakura.tts, sakura.host.artifacts]
''', encoding="utf-8")
    character = user / "characters/sakura"
    portrait = character / "visuals/portrait"
    portrait.mkdir(parents=True)
    (character / "card.md").write_text("fixture", encoding="utf-8")
    (character / "character.json").write_text(json.dumps({
        "id": "sakura", "display_name": "Sakura", "card": "card.md", "visuals": {
            "default": "portrait", "resources": [{"id": "portrait", "type": "sakura.visual.portrait@1",
                "root": "visuals/portrait", "entry": "resource.json"}]}}), encoding="utf-8")
    (portrait / "resource.json").write_text(json.dumps({"default": "default.png", "expressions": {"happy": "happy.png"}}), encoding="utf-8")
    (portrait / "default.png").write_bytes(PNG)
    (portrait / "happy.png").write_bytes(PNG)
    config = user / "config"
    config.mkdir()
    (config / "characters.yaml").write_text("current_character_id: sakura\n", encoding="utf-8")
    (config / "plugin-migrations.json").write_bytes((SAKURA / "desktop/src-tauri/src/new_user_plugin_migrations.json").read_bytes())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    for plugin_id, data in {
        "sakura.remote": {"enabled": True, "host": "127.0.0.1", "port": port, "token": "fixture-token"},
        "sakura.tts": {"selections": {"sakura": {"enabled": True, "provider": "fixture.voice"}}},
    }.items():
        path = user / "data/plugins" / plugin_id / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    package = tmp_path / "remote.zip"
    with zipfile.ZipFile(package, "w") as archive:
        for path in PLUGIN.rglob("*"):
            if path.is_file() and not {".git", "__pycache__", ".pytest_cache"} & set(path.parts):
                archive.write(path, "remote/" + path.relative_to(PLUGIN).as_posix())
    roots = RuntimeRoots(distribution, user)
    LocalPluginInstaller(roots).install(package, "zip")
    PluginDesiredStateStore(user).write({"sakura.remote": True})
    timeline = TimelineStore(StoragePaths(user).timeline_database())
    timeline.initialize()
    requests, events = [], []

    def run_turn(request, **kwargs):
        requests.append(request)
        if request.get("attachment"):
            segments = [ChatSegment("image accepted", translation="收到图片")]
        else:
            segments = [ChatSegment("")] + [ChatSegment(f"speech {i}", translation=f"译文 {i}") for i in range(20)]
        return SimpleNamespace(reply=ChatReply(segments), actions=[])

    session = SimpleNamespace(character=CharacterRegistry(user).get("sakura"),
        runtime=SimpleNamespace(set_context_providers=lambda values: None, finish_trace_operation=lambda *args, **kwargs: True),
        assistant=SimpleNamespace(run_turn=run_turn, commit_result=lambda commit: commit(), release=lambda *args, **kwargs: None),
        descriptor=lambda: {}, tool_actions=None, memory_boundary=None, visual_binding=None)
    app = PluginRuntimeApplication(roots, "remote-integration", ToolRegistry(),
        PluginInventory(roots).scan().runtime_specs, call_timeout=3)
    tts = TTSBoundary("remote-integration", "credential", user, session_provider=lambda: session,
                      plugin_application_provider=lambda: app)
    chat = RealChatBoundary("remote-integration", "credential", user, session_provider=lambda: session,
        timeline_store=timeline, event_publisher=events.append, plugin_application_provider=lambda: app,
        segment_authorizer=tts.authorize_segment)
    app.bind_chat_boundary(chat)
    app.bind_tts_boundary(tts)

    def http(route, data=None):
        if data is None:
            route += ("&" if "?" in route else "?") + "token=fixture-token"
        else:
            data = {"token": "fixture-token", **data}
        request = urllib.request.Request(f"http://127.0.0.1:{port}" + route,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read()
            return json.loads(body) if response.headers["Content-Type"].startswith("application/json") else body

    try:
        app.start()
        app.bind_session(session)
        deadline = time.monotonic() + 8
        while True:
            status = next(item for item in app.settings_snapshot()["plugins"] if item["pluginId"] == "sakura.remote")
            assert status["state"] == "active", status
            values = next(item["values"] for item in status["sections"] if item["sectionId"] == "sakura_remote")
            assert not values["error"], values
            if values["running"] == "运行中":
                break
            assert time.monotonic() < deadline, values
        state = http("/api/state")
        assert {item["key"] for item in state["portraits"]} == {"__default__", "happy"}
        assert http("/asset/portrait?character=sakura&key=happy") == PNG
        reply = http("/api/chat", {"character_id": "sakura", "text": "text only"})
        assert reply["historyEntryId"]
        assert reply["segments"][1]["segmentIndex"] == 1
        assert requests[0]["message"] == "text only"
        for index in range(1, 21):
            audio = http("/api/tts", {"character_id": "sakura", "history_entry_id": reply["historyEntryId"], "segment_index": index})
            assert audio.startswith(b"RIFF")
            assert app._host_services.artifact_count == 0
        assert app.call_service("fixture.voice", "calls") == 20
        assert http("/api/tts", {"character_id": "sakura", "text": "译文 0"}).startswith(b"RIFF")
        assert app.call_service("fixture.voice", "calls") == 20
        assert app._host_services.artifact_count == 0
        upload = http("/api/upload", {"media_type": "image/png", "data": base64.b64encode(PNG).decode()})
        image_reply = http("/api/chat", {"character_id": "sakura", "text": "see image", "image_asset": upload["url"]})
        assert image_reply["reply"] == "收到图片"
        assert requests[1]["attachment"]["observations"][0]["data_url"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
        assert [entry.kind for entry in timeline.read_all("sakura")] == [
            TimelineKind.HUMAN, TimelineKind.ASSISTANT,
            TimelineKind.HUMAN, TimelineKind.OBSERVATION, TimelineKind.ASSISTANT,
        ]
        assert app._host_services.artifact_count == 0
        assert [event["name"] for event in events] == ["host.chat.started", "host.chat.completed"] * 2
        history = http("/api/history?character_id=sakura")
        assert history["history"][-1]["content"] == "收到图片"
        assert len(tts._recordings.scan_and_prune()) == 20
    finally:
        app.close()
        chat.close()
        tts.close()
