"""HTTP API в режиме заглушки (через FastAPI TestClient)."""

import asyncio
import io
import time

import httpx
from PIL import Image

from backend.app import config
from backend.app.main import app
from backend.app.model_manager import manager
from tests.conftest import make_image_bytes


def upload(path_client, url, data: bytes, name="board.jpg", mime="image/jpeg"):
    return path_client.post(url, files={"image": (name, data, mime)})


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True


def test_models_list(client):
    models = client.get("/api/models").json()
    assert [m["id"] for m in models] == ["mock"]
    assert models[0]["active"] and models[0]["loaded"] and models[0]["error"] is None


def test_analyze_full_response(client):
    body = upload(client, "/api/analyze", make_image_bytes(640, 480)).json()
    assert body["model"] == "mock"
    assert body["image_size"] == {"width": 640, "height": 480}
    assert body["summary"]["total"] == len(body["detections"]) == 3
    assert body["verdict"]["status"] in ("ok", "warning", "reject")
    assert {d["category"] for d in body["verdict"]["defects"]} <= {c["id"] for c in config.TZ_CATEGORIES}
    assert [i["id"] for i in body["tz_checklist"]] == [c["id"] for c in config.TZ_CATEGORIES]


def test_analyze_applies_exif_rotation(client):
    image = Image.new("RGB", (200, 100))
    exif = image.getexif()
    exif[0x0112] = 6   # телефон "на боку"
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif.tobytes())
    body = upload(client, "/api/analyze", buffer.getvalue()).json()
    assert body["image_size"] == {"width": 100, "height": 200}


def test_analyze_rejects_empty_and_garbage(client):
    empty = upload(client, "/api/analyze", b"")
    garbage = upload(client, "/api/analyze", b"not an image", name="x.txt", mime="text/plain")
    assert empty.status_code == 400 and empty.json()["detail"] == "Пустой файл"
    assert garbage.status_code == 400


def test_frame_is_smoothed(client):
    frame = make_image_bytes(640, 480)
    first = upload(client, "/api/frame", frame).json()
    second = upload(client, "/api/frame", frame).json()
    assert first["detections"] == []          # ещё не подтверждены
    assert len(second["detections"]) == 3     # подтверждены со 2-го кадра


def test_activate_unknown_model_is_404(client):
    response = client.post("/api/models/nope/activate")
    assert response.status_code == 404
    assert "mock" in response.json()["detail"]


def test_activate_resets_smoother(client):
    frame = make_image_bytes()
    upload(client, "/api/frame", frame)
    upload(client, "/api/frame", frame)
    assert client.post("/api/models/mock/activate").status_code == 200
    assert upload(client, "/api/frame", frame).json()["detections"] == []


def test_metrics_include_reference_data(client):
    body = client.get("/api/metrics").json()
    assert body["models"]
    assert len(body["tz_categories"]) == len(config.TZ_CATEGORIES)
    for info in body["class_info"].values():
        assert {"label", "category", "approximate"} <= set(info)


def test_examples_listing_and_path_safety(client, tmp_path, monkeypatch):
    (tmp_path / "01_board.jpg").write_bytes(make_image_bytes())
    (tmp_path / "notes.txt").write_text("не картинка", encoding="utf-8")
    monkeypatch.setattr(config, "EXAMPLES_DIR", tmp_path)

    assert [e["name"] for e in client.get("/api/examples").json()] == ["01_board.jpg"]
    assert client.get("/api/examples/01_board.jpg").status_code == 200
    for bad in ["notes.txt", "../requirements.txt", "..%2Fbackend%2Fapp%2Fconfig.py", "nope.jpg"]:
        assert client.get(f"/api/examples/{bad}").status_code == 404, bad


def test_examples_without_folder(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXAMPLES_DIR", tmp_path / "missing")
    assert client.get("/api/examples").json() == []


def test_server_responds_during_slow_inference(monkeypatch):
    # регрессия: инференс шёл прямо в event loop и замораживал весь сервер
    model = manager.get_active()
    original = model.predict
    monkeypatch.setattr(model, "predict", lambda image: (time.sleep(1.0), original(image))[1])

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # Время — от отправки медленного запроса: если инференс блокирует
            # event loop, растянется уже sleep ниже, и замер "после паузы"
            # ошибку бы не увидел.
            t0 = time.perf_counter()
            slow = asyncio.create_task(ac.post(
                "/api/analyze", files={"image": ("a.jpg", make_image_bytes(), "image/jpeg")}))
            await asyncio.sleep(0.1)
            health = await ac.get("/api/health")
            health_done = time.perf_counter() - t0
            await slow
            return health.status_code, health_done

    status, health_done = asyncio.run(scenario())
    assert status == 200
    assert health_done < 0.6   # ответ пришёл, не дожидаясь секундного инференса
