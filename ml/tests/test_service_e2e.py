"""сквозной прогон HTTP-сервиса: реальный кадр и грязные входные данные.

Отдельно от `test_pipeline.py`, потому что здесь поднимается настоящее
приложение и грузится модель: проверка медленная и требует весов. Без весов файл
пропускается целиком, чтобы быстрые проверки оставались быстрыми.

Смысл этих проверок не в том, что сервис не падает, — он не падал и до них. Все
четыре изъяна, найденные первым таким прогоном (E23), возвращали код 200 и
правдоподобный ответ. Опаснее падения именно это: заметить нечем.

    python -m pytest tests/test_service_e2e.py -q
"""

import io
import sys
import zipfile
from pathlib import Path

import pytest

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

from service.detector import DEFAULT_WEIGHTS  # noqa: E402

pytestmark = pytest.mark.skipif(not Path(DEFAULT_WEIGHTS).exists(),
                                reason="нет весов: python tools/fetch_weights.py")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from service.app import app
    with TestClient(app) as c:      # TestClient как контекст поднимает lifespan
        yield c


def кадр(image="a.png", site="s1", day="2024-04-24", classes=("drilling_rig", "crawler_crane"),
         bbox=None):
    return {"image": image, "site_id": site, "date": day, "width": 1000, "height": 800,
            "detections": [{"class_raw": c, "class_ours": c, "conf": 0.9,
                            "bbox": bbox or [0.05 + i * 0.15, 0.2, 0.15 + i * 0.15, 0.6]}
                           for i, c in enumerate(classes)]}


ПЛАН = [{"site_id": "s1", "stage_code": "12.3.2", "stage_name": "Устройство свай",
         "planned_start": "2024-01-15", "planned_end": "2024-03-31"}]
ЗАПРОС = {"observations": [кадр()], "schedule": ПЛАН}


class TestРучки:
    def test_health(self, client):
        assert client.get("/health").json()["model_loaded"]

    def test_meta_называет_веса(self, client):
        assert "weights" in str(client.get("/meta").json()).lower()

    def test_автодокументация_открывается(self, client):
        """По ТЗ прототип должен быть доступен жюри — это и есть точка входа."""
        assert client.get("/docs").status_code == 200


class TestОтчёт:
    def test_нормальный_ход(self, client):
        d = client.post("/report", json=ЗАПРОС).json()
        assert d["sites"][0]["stages"][0]["status"] == "behind"
        assert "forecast" in d["sites"][0]
        assert "summary" in d

    def test_без_наблюдений_400(self, client):
        assert client.post("/report", json={"observations": [], "schedule": ПЛАН}).status_code == 400

    def test_без_плана_400(self, client):
        assert client.post("/report", json={"observations": [кадр()],
                                            "schedule": []}).status_code == 400

    def test_conf_вне_диапазона_422(self, client):
        assert client.post("/report", json={**ЗАПРОС, "conf": 1.5}).status_code == 422

    @pytest.mark.parametrize("bbox,имя", [
        ([-0.5, -0.5, 2.0, 2.0], "вне кадра"),
        ([0.6, 0.6, 0.2, 0.2], "перевёрнутая"),
        ([0.3, 0.3, 0.3, 0.3], "нулевая"),
    ])
    def test_кривая_рамка_не_роняет(self, client, bbox, имя):
        r = client.post("/report", json={"observations": [кадр(bbox=bbox)], "schedule": ПЛАН})
        assert r.status_code == 200, имя

    def test_неизвестный_класс_техники_не_роняет(self, client):
        r = client.post("/report", json={"observations": [кадр(classes=("летающая_тарелка",))],
                                         "schedule": ПЛАН})
        assert r.status_code == 200

    def test_битая_дата_в_плане_не_роняет_запрос(self, client):
        """В присланном заказчиком файле таких строк 13 из 67."""
        план = [dict(ПЛАН[0], planned_start="30.02.2027")]
        d = client.post("/report", json={"observations": [кадр()], "schedule": план}).json()
        assert d["meta"]["plan_rows_rejected"] == 1
        assert any(a["type"] == "plan_invalid" for a in d["sites"][0]["alerts"])

    def test_чужой_код_этапа_отличим_от_непроверяемого(self, client):
        план = [dict(ПЛАН[0], stage_code="99.9.9")]
        d = client.post("/report", json={"observations": [кадр()], "schedule": план}).json()
        assert d["sites"][0]["stages"][0]["status"] == "no_rule"
        assert any(a["type"] == "unknown_stages" for a in d["sites"][0]["alerts"])


class TestВыгрузка:
    @pytest.mark.parametrize("fmt", ["csv", "xlsx", "html"])
    def test_формат_отдаётся(self, client, fmt):
        assert client.post(f"/report/export?fmt={fmt}", json=ЗАПРОС).status_code == 200

    def test_xlsx_открывается_как_архив(self, client):
        body = client.post("/report/export?fmt=xlsx", json=ЗАПРОС).content
        assert "xl/worksheets/sheet1.xml" in zipfile.ZipFile(io.BytesIO(body)).namelist()

    def test_неизвестный_формат_422(self, client):
        assert client.post("/report/export?fmt=pdf", json=ЗАПРОС).status_code == 422


class TestДетекция:
    @staticmethod
    def снимок():
        folder = ML / "data/raw/dataset/images/Строительная_техника"
        files = sorted(folder.glob("*.png")) or sorted(folder.glob("*.jpg"))
        if not files:
            pytest.skip("нет исходных снимков")
        return files[0]

    def test_реальный_кадр_и_доли_вместо_пикселей(self, client):
        img = self.снимок()
        d = client.post("/detect", files={"file": (img.name, img.read_bytes(), "image/png")}).json()
        assert d["width"] > 0
        assert all(0 <= v <= 1 for x in d["detections"] for v in x["bbox"])

    def test_кириллица_в_имени_файла(self, client):
        """OpenCV не открывает кириллические пути — проверяем, что обходной путь жив."""
        img = self.снимок()
        r = client.post("/detect", files={"file": ("кадр площадки.png", img.read_bytes(),
                                                   "image/png")})
        assert r.status_code == 200

    def test_пустой_файл_400(self, client):
        assert client.post("/detect", files={"file": ("e.png", b"", "image/png")}).status_code == 400

    def test_мусор_вместо_картинки_422(self, client):
        r = client.post("/detect", files={"file": ("x.png", b"not an image", "image/png")})
        assert r.status_code == 422

    def test_файл_сверх_лимита_413(self, client):
        big = b"\x89PNG" + b"\0" * (21 * 1024 * 1024)
        assert client.post("/detect", files={"file": ("big.png", big,
                                                      "image/png")}).status_code == 413
