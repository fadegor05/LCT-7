"""проверки цепочки и разбора планов.

Цель не покрытие ради покрытия, а защита тех мест, где мы уже обжигались:
даты, которых не существует; кадры без привязки; различение «не начат» и «нет
наблюдений»; форматы выгрузки.

    python -m pytest tests/ -q
"""

import sys
import zipfile
from datetime import date
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

from service.export import to_csv, to_html, to_xlsx      # noqa: E402
from service.pipeline import build_report, summary        # noqa: E402
from parse_schedule import parse_date                     # noqa: E402


def frame(name, site, day, classes):
    """Кадр с детекциями: каждой машине своя рамка, чтобы dedup их не схлопнул."""
    dets = []
    for i, cls in enumerate(classes):
        x = 0.05 + i * 0.15
        dets.append({"class_raw": cls, "class_ours": cls, "conf": 0.9,
                     "bbox": [x, 0.2, x + 0.1, 0.6]})
    return {"image": name, "site_id": site, "date": day,
            "width": 1000, "height": 800, "detections": dets}


SCHEDULE = [{"site_id": "s1", "stage_code": "12.3.2", "stage_name": "Устройство свай",
             "planned_start": "2024-01-15", "planned_end": "2024-03-31"}]

# Комплект, подтверждающий сваи: по ГЭСН 05-01-028-01 нужен не только буровой
# станок, но и кран для установки арматурных каркасов. Одна машина этап не
# доказывает — это и есть проверяемая связь «этап → техника».
СВАИ = ["drilling_rig", "crawler_crane"]


class TestДаты:
    def test_несуществующая_дата_не_роняет_разбор(self):
        """В реальном плане заказчика 13 строк содержали «30.02.2027»."""
        value, why = parse_date("30.02.2027")
        assert value is None
        assert "некорректная" in why

    def test_число_excel(self):
        assert parse_date("46122")[0] == date(2026, 4, 10)

    def test_дата_с_днём_недели(self):
        """Выгрузка MS Project пишет «Пт 07.06.19»."""
        assert parse_date("Пт 07.06.19")[0] == date(2019, 6, 7)

    def test_пустое_значение(self):
        assert parse_date("")[0] is None


class TestСтатусы:
    def test_отставание_когда_работы_после_срока(self):
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
        report = build_report(obs, SCHEDULE)
        stage = report["sites"][0]["stages"][0]
        assert stage["status"] == "behind"
        assert stage["delay_days"] == 24

    def test_в_графике_когда_работы_в_окне(self):
        obs = [frame("a.png", "s1", "2024-02-10", СВАИ)]
        assert build_report(obs, SCHEDULE)["sites"][0]["stages"][0]["status"] == "on_track"

    def test_не_начат_отличается_от_нет_наблюдений(self):
        """Первое — утверждение о стройке, второе — о наших данных.

        Смешать их значит выдать отсутствие снимков за отсутствие работ.
        """
        поздно = build_report([frame("a.png", "s1", "2024-04-24", ["excavator_crawler"])],
                              SCHEDULE)["sites"][0]["stages"][0]
        рано = build_report([frame("a.png", "s1", "2024-01-05", ["excavator_crawler"])],
                            SCHEDULE)["sites"][0]["stages"][0]
        assert поздно["status"] == "not_started"
        assert рано["status"] == "not_observed"

    def test_неполный_комплект_не_подтверждает_этап(self):
        """Буровая без крана — этап не подтверждён: по норме нужен весь комплект."""
        obs = [frame("a.png", "s1", "2024-02-10", ["drilling_rig"])]
        assert build_report(obs, SCHEDULE)["sites"][0]["stages"][0]["status"] != "on_track"

    def test_универсальная_техника_не_подтверждает_этап(self):
        """Экскаватор встречается на половине этапов и сваи не доказывает.

        Это ядро методики: подтверждение требует специфичного класса либо
        полного набора по норме.
        """
        obs = [frame("a.png", "s1", "2024-02-10", ["excavator_crawler"])]
        assert build_report(obs, SCHEDULE)["sites"][0]["stages"][0]["status"] != "on_track"


class TestДырыВДанных:
    def test_кадр_без_даты_не_теряется_молча(self):
        obs = [frame("a.png", "s1", "2024-02-10", СВАИ),
               frame("b.png", "s1", "", СВАИ)]
        report = build_report(obs, SCHEDULE)
        assert report["meta"]["frames_unusable"] == 1
        assert any(a["type"] == "unusable_data" for a in report["sites"][0]["alerts"])

    def test_алерт_объясняет_чего_нельзя_утверждать(self):
        obs = [frame("a.png", "s1", "2024-02-10", СВАИ),
               frame("b.png", "s1", "", СВАИ)]
        alert = [a for a in build_report(obs, SCHEDULE)["sites"][0]["alerts"]
                 if a["type"] == "unusable_data"][0]
        assert "не означает отсутствия работ" in alert["cannot_claim"]

    def test_кадр_без_площадки_не_ломает_отчёт(self):
        obs = [frame("a.png", "", "2024-02-10", СВАИ)]
        report = build_report(obs, SCHEDULE)
        assert report["meta"]["observations"] == 0
        assert report["sites"][0]["stages"][0]["status"] == "not_observed"


class TestВыгрузка:
    def _report(self):
        return build_report([frame("a.png", "s1", "2024-04-24", СВАИ)], SCHEDULE)

    def test_csv_открывается_в_excel(self):
        """BOM нужен, иначе Excel показывает кириллицу кракозябрами."""
        data = to_csv(self._report())
        assert data.startswith(b"\xef\xbb\xbf")
        assert "Площадка" in data.decode("utf-8-sig")

    def test_xlsx_это_валидный_архив_с_двумя_листами(self):
        names = zipfile.ZipFile(__import__("io").BytesIO(to_xlsx(self._report()))).namelist()
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names

    def test_html_содержит_оговорку(self):
        assert "не утверждает" in to_html(self._report()).decode("utf-8")


class TestСводка:
    def test_считает_статусы_и_алерты(self):
        report = build_report([frame("a.png", "s1", "2024-04-24", СВАИ)], SCHEDULE)
        s = summary(report)
        assert s["statuses"]["behind"] == 1
        assert s["sites"] == 1


class TestПрогноз:
    """Прогноз — арифметика графика, а не модель производительности.

    Проверяем ровно два свойства: сдвиг появляется только при задержке и
    равен ей; оговорка про объём работ едет вместе с числом.
    """

    ДВА_ЭТАПА = SCHEDULE + [
        {"site_id": "s1", "stage_code": "12.3.6", "stage_name": "Монолит выше нуля",
         "planned_start": "2024-04-01", "planned_end": "2024-09-30"},
    ]

    def test_в_графике_сдвига_нет(self):
        obs = [frame("a.png", "s1", "2024-02-10", СВАИ)]
        f = build_report(obs, self.ДВА_ЭТАПА)["sites"][0]["forecast"]
        assert f["shift_days"] == 0

    def test_задержка_переносится_на_завершение(self):
        """Сваи видны через 24 дня после срока — на столько же съезжает весь план."""
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
        f = build_report(obs, self.ДВА_ЭТАПА)["sites"][0]["forecast"]
        assert f["shift_days"] == 24
        assert f["planned_completion"] == "2024-09-30"
        assert f["projected_completion"] == "2024-10-24"

    def test_сдвиг_достаётся_последующему_этапу(self):
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
        f = build_report(obs, self.ДВА_ЭТАПА)["sites"][0]["forecast"]
        позже = [s for s in f["stages"] if s["stage_code"] == "12.3.6"]
        assert позже and позже[0]["shift_days"] == 24

    def test_прогноз_несёт_оговорку(self):
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
        f = build_report(obs, self.ДВА_ЭТАПА)["sites"][0]["forecast"]
        assert "объём по снимкам не измеряется" in f["cannot_claim"]
        assert "верхняя оценка" in f["assumption"]


def test_прогноз_попадает_в_печатную_форму():
    obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
    html = to_html(build_report(obs, TestПрогноз.ДВА_ЭТАПА)).decode("utf-8")
    assert "Прогноз сроков" in html
    assert "2024-10-24" in html
