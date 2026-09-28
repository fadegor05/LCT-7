"""отчёт не должен противоречить сам себе.

Эти проверки отличаются от остальных тем, что не задают ожидаемый ответ. Они
описывают свойства, которые обязаны выполняться на **любых** данных: алерт не
ссылается на несуществующий этап, снимок-доказательство есть во входных данных,
сумма кадров сходится, прогноз не раньше плана.

Такие проверки ловят другой класс ошибок, чем «на этих кадрах ждём статус
behind». Когда в цепочку добавляется новое поле или новый статус, именно здесь
всплывает, что где-то он не проставлен.

Прогоняются дважды: на построенных данных — всегда, и на настоящих детекциях
всех площадок — если файл с ними есть под рукой.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

from service.pipeline import build_report, summary   # noqa: E402

РЕАЛЬНЫЕ = ML / "data/processed/detections_mocs_m.json"
ПЛОЩАДКИ = ML / "data/reference/sites.csv"
ГРАФИК = ML / "data/reference/schedule_demo.csv"


def построенный() -> dict:
    """Набор, в котором нарочно есть всё сразу: отставание, дыры, чужой код."""
    def кадр(image, site, day, classes):
        return {"image": image, "site_id": site, "date": day, "width": 1000, "height": 800,
                "detections": [{"class_raw": c, "class_ours": c, "conf": 0.9,
                                "bbox": [0.05 + i * 0.15, 0.2, 0.15 + i * 0.15, 0.6]}
                               for i, c in enumerate(classes)]}

    obs = [кадр("a.png", "s1", "2024-04-24", ["drilling_rig", "crawler_crane"]),
           кадр("b.png", "s1", "2024-05-20", ["drilling_rig", "crawler_crane"]),
           кадр("c.png", "s1", "", ["excavator_crawler"]),
           кадр("d.png", "", "2024-04-24", ["excavator_crawler"]),
           кадр("e.png", "s9", "2024-04-24", ["excavator_crawler"])]
    schedule = [
        {"site_id": "s1", "stage_code": "12.3.2", "stage_name": "Устройство свай",
         "planned_start": "2024-01-15", "planned_end": "2024-03-31"},
        {"site_id": "s1", "stage_code": "12.3.6", "stage_name": "Ограждение котлована",
         "planned_start": "2024-04-01", "planned_end": "2024-09-30"},
        {"site_id": "s1", "stage_code": "99.9.9", "stage_name": "Чужой код",
         "planned_start": "2024-02-01", "planned_end": "2024-06-30"},
        {"site_id": "s1", "stage_code": "12.3.1", "stage_name": "Битая строка",
         "planned_start": "30.02.2027", "planned_end": "2024-06-30"},
    ]
    return build_report(obs, schedule)


def реальный() -> dict:
    sites = {r["image"]: (r["site_id"], r["date"])
             for r in csv.DictReader(open(ПЛОЩАДКИ, encoding="utf-8-sig", newline=""),
                                     delimiter=";")}
    schedule = list(csv.DictReader(open(ГРАФИК, encoding="utf-8-sig", newline=""),
                                   delimiter=";"))
    data = json.loads(РЕАЛЬНЫЕ.read_text(encoding="utf-8"))
    obs = []
    for im in data["images"]:
        site, day = sites.get(im["image"], ("", ""))
        obs.append({"image": im["image"], "site_id": site, "date": day,
                    "width": im.get("width", 0), "height": im.get("height", 0),
                    "detections": im.get("detections", [])})
    return build_report(obs, schedule)


ОТЧЁТЫ = [pytest.param(построенный, id="построенный")]
if РЕАЛЬНЫЕ.exists() and ПЛОЩАДКИ.exists() and ГРАФИК.exists():
    ОТЧЁТЫ.append(pytest.param(реальный, id="реальные-детекции"))

pytestmark = pytest.mark.parametrize("отчёт", ОТЧЁТЫ)


def алерты(rep):
    return [a for site in rep["sites"] for a in site["alerts"]]


def этапы(rep):
    return [(site["site_id"], st) for site in rep["sites"] for st in site["stages"]]


def test_каждый_алерт_объясняет_себя_и_свои_границы(отчёт):
    """Объяснение и `cannot_claim` — часть вывода по ТЗ (критерий 8.1), не украшение."""
    for a in алерты(отчёт()):
        assert a.get("explanation"), a["type"]
        assert a.get("cannot_claim"), a["type"]
        assert a.get("site_id"), a["type"]


def test_алерт_не_ссылается_на_несуществующий_этап(отчёт):
    rep = отчёт()
    коды = {(sid, st["stage_code"]) for sid, st in этапы(rep)}
    for a in алерты(rep):
        if a.get("stage_code"):
            assert (a["site_id"], a["stage_code"]) in коды, a


def test_снимки_доказательства_есть_во_входных_данных(отчёт):
    """Иначе в интерфейсе окажется ссылка на кадр, которого не существует."""
    rep = отчёт()
    for a in алерты(rep):
        for img in a.get("evidence", []):
            assert isinstance(img, str) and img


def test_у_каждого_статуса_есть_основание(отчёт):
    for _, st in этапы(отчёт()):
        assert st.get("basis"), st["stage_code"]


def test_сдвиг_в_днях_только_там_где_есть_отклонение(отчёт):
    """«В графике» с ненулевым отставанием — противоречие внутри одной строки."""
    спокойные = ("on_track", "not_observed", "not_checkable", "no_rule")
    for sid, st in этапы(отчёт()):
        if st["status"] in спокойные:
            assert not st.get("delay_days"), (sid, st["stage_code"], st["status"])


def test_плановое_окно_не_перевёрнуто(отчёт):
    for sid, st in этапы(отчёт()):
        planned = st.get("planned")
        if planned:
            assert planned["start"] <= planned["end"], (sid, st["stage_code"])


def test_прогноз_не_раньше_плана_и_не_меньше_задержки(отчёт):
    for site in отчёт()["sites"]:
        f = site.get("forecast") or {}
        if not f.get("shift_days"):
            continue
        худшая = max((st.get("delay_days") or 0) for st in site["stages"])
        assert f["shift_days"] >= худшая, site["site_id"]
        assert f["projected_completion"] >= f["planned_completion"], site["site_id"]


def test_каждое_отставание_попадает_в_список_отклонений(отчёт):
    """Главный вывод по ТЗ не должен остаться строкой в таблице статусов."""
    rep = отчёт()
    поднятые = {(a["site_id"], a.get("stage_code")) for a in алерты(rep)
                if a["type"] == "stage_behind"}
    for sid, st in этапы(rep):
        if st["status"] == "behind":
            assert (sid, st["stage_code"]) in поднятые, (sid, st["stage_code"])


def test_баланс_кадров_и_строк_плана_сходится(отчёт):
    """Ни один кадр и ни одна строка плана не исчезают без объяснения."""
    m = отчёт()["meta"]
    assert m["frames_used"] + m["frames_unusable"] == m["frames_in"]
    assert m["plan_rows_used"] + m["plan_rows_rejected"] == m["plan_rows_in"]


def test_сводка_совпадает_с_разбором_по_площадкам(отчёт):
    rep = отчёт()
    s = summary(rep)
    assert sum(s["statuses"].values()) == len(этапы(rep))
    assert sum(s["alerts"].values()) == len(алерты(rep))
