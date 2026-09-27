"""проверки цепочки и разбора планов.

Цель не покрытие ради покрытия, а защита тех мест, где мы уже обжигались:
даты, которых не существует; кадры без привязки; различение «не начат» и «нет
наблюдений»; форматы выгрузки.

    python -m pytest tests/ -q
"""

import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

from service.export import to_csv, to_html, to_xlsx      # noqa: E402
from service.pipeline import build_report, summary        # noqa: E402
from parse_schedule import classify_rows, parse_date     # noqa: E402


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


class TestРядКадров:
    """Простой по ряду кадров с камеры.

    Данных с камер у нас ещё нет, поэтому логика проверяется на построенных
    рядах: они задают ровно те случаи, ради которых код и написан.
    """

    @staticmethod
    def серия(минуты: list[int], боксы: list[list[float]], cls="excavator_crawler",
              camera="cam1"):
        return [{"image": f"{i}.jpg", "camera_id": camera,
                 "timestamp": f"2026-05-18T09:{m:02d}:00",
                 "detections": [{"class_ours": cls, "conf": 0.9, "bbox": b}]}
                for i, (m, b) in enumerate(zip(минуты, боксы))]

    def test_неподвижная_машина_считается_несместившейся(self):
        from activity_series import analyse
        кадры = self.серия(list(range(0, 24, 2)), [[0.2, 0.3, 0.3, 0.5]] * 12)
        row = analyse(кадры)["classes"][0]
        assert row["still"] == 11 and row["moved"] == 0
        assert row["still_share"] == 1.0

    def test_едущая_машина_считается_сместившейся(self):
        from activity_series import analyse
        боксы = [[0.1 + i * 0.05, 0.3, 0.2 + i * 0.05, 0.5] for i in range(12)]
        row = analyse(self.серия(list(range(0, 24, 2)), боксы))["classes"][0]
        assert row["moved"] == 11 and row["still"] == 0

    def test_мало_наблюдений_доля_не_оценивается(self):
        """Три пары — не выборка. Молчать честнее, чем назвать 100%."""
        from activity_series import analyse
        row = analyse(self.серия([0, 2, 4, 6], [[0.2, 0.3, 0.3, 0.5]] * 4))["classes"][0]
        assert "still_share" not in row
        assert "меньше порога" in row["basis"]

    def test_сдвиг_камеры_не_принимается_за_движение_техники(self):
        """Если сместилось всё сразу — подвинули камеру, а не поехала техника."""
        from activity_series import analyse
        def кадр(i, dx):
            return {"image": f"{i}.jpg", "camera_id": "cam1",
                    "timestamp": f"2026-05-18T09:{i * 2:02d}:00",
                    "detections": [{"class_ours": "excavator_crawler", "conf": 0.9,
                                    "bbox": [x + dx, 0.3, x + 0.1 + dx, 0.5]}
                                   for x in (0.1, 0.4, 0.7)]}
        кадры = [кадр(0, 0.0), кадр(1, 0.05)]
        res = analyse(кадры)
        assert res["meta"]["frames_skipped_camera_moved"] == 1
        assert res["classes"] == []

    def test_большой_разрыв_между_кадрами_не_сравнивается(self):
        """За час машина успеет уехать и вернуться — «не сместилась» пусто."""
        from activity_series import analyse
        res = analyse(self.серия([0, 59], [[0.2, 0.3, 0.3, 0.5]] * 2))
        assert res["meta"]["pairs_skipped_gap"] == 1
        assert res["classes"] == []

    def test_результат_несёт_оговорку(self):
        from activity_series import analyse
        res = analyse(self.серия([0, 2], [[0.2, 0.3, 0.3, 0.5]] * 2))
        assert "а не работа" in res["cannot_claim"]


class TestГрязныйПлан:
    """Реальные планы приходят с ошибками, и одна строка не должна валить всё.

    Каждая проверка здесь — случай, найденный сквозным прогоном сервиса, а не
    придуманный: в присланном заказчиком файле были и несуществующие даты, и
    повторяющиеся этапы.
    """

    НАБЛЮДЕНИЕ = staticmethod(lambda: [frame("a.png", "s1", "2024-04-24", СВАИ)])

    def test_битая_дата_не_роняет_весь_план(self):
        плохой = [dict(SCHEDULE[0], planned_start="30.02.2027")]
        report = build_report(self.НАБЛЮДЕНИЕ(), плохой)
        assert report["meta"]["plan_rows_rejected"] == 1
        assert any(a["type"] == "plan_invalid" for a in report["sites"][0]["alerts"])

    def test_площадка_с_полностью_битым_планом_не_исчезает(self):
        """Иначе предупреждение пропадёт вместе с площадкой — худший исход."""
        плохой = [dict(SCHEDULE[0], planned_end="30.02.2027")]
        report = build_report(self.НАБЛЮДЕНИЕ(), плохой)
        assert len(report["sites"]) == 1
        assert report["sites"][0]["stages"] == []

    def test_окончание_раньше_начала_отбраковано(self):
        """Иначе цепочка честно посчитает отставание в сто дней из ничего."""
        плохой = [dict(SCHEDULE[0], planned_start="2024-06-01", planned_end="2024-01-01")]
        report = build_report(self.НАБЛЮДЕНИЕ(), плохой)
        assert report["meta"]["plan_rows_rejected"] == 1
        assert report["sites"][0]["stages"] == []

    def test_повторяющийся_этап_сводится_в_одну_строку(self):
        двойной = [SCHEDULE[0], dict(SCHEDULE[0], planned_end="2024-05-31")]
        report = build_report(self.НАБЛЮДЕНИЕ(), двойной)
        stages = report["sites"][0]["stages"]
        assert len(stages) == 1
        assert stages[0]["planned"]["end"] == "2024-05-31"   # берём самое позднее

    def test_код_без_правила_отличается_от_непроверяемого_этапа(self):
        """«Нет правила» — дыра в настройке, «не проверяется» — свойство этапа.

        Смешать их значит: план с чужой нумерацией целиком станет «не
        проверяется», и система будет молча выглядеть работающей.
        """
        чужой = [dict(SCHEDULE[0], stage_code="99.9.9", stage_name="Чужой код")]
        report = build_report(self.НАБЛЮДЕНИЕ(), чужой)
        assert report["sites"][0]["stages"][0]["status"] == "no_rule"
        assert any(a["type"] == "unknown_stages" for a in report["sites"][0]["alerts"])


def test_копёр_подтверждает_забивные_сваи():
    """Найдено сквозным прогоном: на p09 девять копров, а этап числился не начатым.

    Методика знала только буронабивные сваи (нужны буровая и кран). Забивные
    погружаются копровой установкой, и отдельный кран по норме не нужен.
    """
    obs = [frame("a.png", "s1", "2024-02-10", ["pile_driver"])]
    assert build_report(obs, SCHEDULE)["sites"][0]["stages"][0]["status"] == "on_track"


class TestРазборПлана:
    """Баланс строк: каждая строка файла обязана попасть ровно в одну корзину.

    Проверка не формальная. На реальном файле заказчика (374 строки) отчёт о
    разборе объяснял судьбу 284, а 90 исчезали без следа: у них просто не было
    дат. Строка «12.3.1 Устройство котлована» была среди них — оператор увидел
    бы знакомый этап в плане и решил, что тот под контролем.
    """

    МАППИНГ = [(re.compile("котлован", re.I), "12.3.1", "Устройство котлована")]

    @staticmethod
    def строка(name, num="1", start="", end=""):
        return {"num": num, "name": name, "start": start, "end": end}

    def test_баланс_сходится(self):
        raw = [self.строка("Устройство котлована", start="2024-01-15", end="2024-03-31"),
               self.строка("Устройство котлована без дат"),
               self.строка("Монтаж лифтов", start="2024-01-15", end="2024-03-31"),
               self.строка("Котлован с битой датой", start="30.02.2027", end="2024-03-31")]
        out, skipped, bad, no_dates, _ = classify_rows(raw, self.МАППИНГ, "s1")
        assert len(out) + len(skipped) + len(no_dates) == len(raw)

    def test_этап_без_дат_виден_отдельно(self):
        """Самый опасный случай: название знакомое, а выводов не будет."""
        raw = [self.строка("Устройство котлована")]
        _, _, _, no_dates, mapped = classify_rows(raw, self.МАППИНГ, "s1")
        assert len(no_dates) == 1
        assert mapped == [("12.3.1", "Устройство котлована")]

    def test_битая_дата_считается_и_не_прерывает_разбор(self):
        raw = [self.строка("Устройство котлована", start="30.02.2027", end="2024-03-31"),
               self.строка("Устройство котлована", start="2024-01-15", end="2024-03-31")]
        out, _, bad, _, _ = classify_rows(raw, self.МАППИНГ, "s1")
        assert len(bad) == 1 and len(out) == 1

    def test_строка_без_нашего_этапа_не_попадает_в_план(self):
        raw = [self.строка("Монтаж слаботочных систем", start="2024-01-15", end="2024-03-31")]
        out, skipped, _, _, _ = classify_rows(raw, self.МАППИНГ, "s1")
        assert out == [] and len(skipped) == 1


class TestПлощадкаБезПлана:
    def test_снимки_без_плана_не_исчезают_молча(self):
        """Снимки сняты и обработаны, а сравнивать не с чем.

        Без счётчика для заказчика это выглядит так, будто объекта не
        существует: кадры учтены как использованные, а в отчёте о площадке нет
        ни слова. Найдено сквозным прогоном на реальных данных — так пропадала
        площадка p07.
        """
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ),
               frame("b.png", "чужая", "2024-04-24", СВАИ)]
        meta = build_report(obs, SCHEDULE)["meta"]
        assert meta["sites_without_plan"] == ["чужая"]
        assert meta["frames_without_plan"] == 1

    def test_когда_все_площадки_в_плане_счётчик_пуст(self):
        obs = [frame("a.png", "s1", "2024-04-24", СВАИ)]
        meta = build_report(obs, SCHEDULE)["meta"]
        assert meta["sites_without_plan"] == []


class TestРеестрНеподвижнойТехники:
    """Техника, внесённая оператором, не должна выдавать себя за распознанную.

    Башенный кран стоит неделями на одной точке, и детектор на низком близком
    ракурсе не находит его ни разу из тринадцати (E26). В эксплуатации это
    решается настройкой, а не дообучением. Но раз вывод опирается на ручной
    ввод, отчёт обязан сказать об этом сам.
    """

    ПЛАН = [{"site_id": "s1", "stage_code": "12.4.28",
             "stage_name": "Монолитный каркас выше отметки 0",
             "planned_start": "2024-01-15", "planned_end": "2024-06-30"}]

    @staticmethod
    def кадр(classes, registered=()):
        dets = []
        for i, cls in enumerate(classes):
            x = 0.05 + i * 0.15
            dets.append({"class_raw": cls, "class_ours": cls, "conf": 0.9,
                         "bbox": [x, 0.2, x + 0.1, 0.6], "source": "detected"})
        for i, cls in enumerate(registered):
            x = 0.60 + i * 0.15
            dets.append({"class_raw": cls, "class_ours": cls,
                         "bbox": [x, 0.02, x + 0.1, 0.3], "source": "registered"})
        return {"image": "a.png", "site_id": "s1", "date": "2024-03-10",
                "width": 1000, "height": 800, "detections": dets}

    def test_без_реестра_этап_не_подтверждается(self):
        """Комплекту нужен башенный кран, а детектор его не видит."""
        report = build_report([self.кадр(["concrete_mixer"])], self.ПЛАН)
        assert report["sites"][0]["stages"][0]["status"] != "on_track"

    def test_с_реестром_этап_подтверждается(self):
        report = build_report([self.кадр(["concrete_mixer"], ["tower_crane"])], self.ПЛАН)
        assert report["sites"][0]["stages"][0]["status"] == "on_track"

    def test_отчёт_сам_сообщает_об_источнике(self):
        site = build_report([self.кадр(["concrete_mixer"], ["tower_crane"])],
                            self.ПЛАН)["sites"][0]
        alert = [a for a in site["alerts"] if a["type"] == "registered_equipment"]
        assert alert, [a["type"] for a in site["alerts"]]
        assert "не распознана" in alert[0]["explanation"]
        assert "не наблюдение" in alert[0]["cannot_claim"]

    def test_запись_реестра_не_режется_порогом_уверенности(self):
        """У утверждения оператора нет уверенности — выдумывать её нельзя."""
        obs = [self.кадр(["concrete_mixer"], ["tower_crane"])]
        assert all("conf" not in d for d in obs[0]["detections"]
                   if d["source"] == "registered")
        report = build_report(obs, self.ПЛАН, conf=0.9)
        assert report["sites"][0]["stages"][0]["status"] == "on_track"

    def test_распознанное_не_подменяется_записью(self):
        """Если система видит машину сама, реестр не должен её удваивать."""
        кадр = self.кадр(["concrete_mixer", "tower_crane"], ["tower_crane"])
        кадр["detections"][1]["bbox"] = [0.60, 0.02, 0.70, 0.30]   # та же зона
        state = build_report([кадр], self.ПЛАН)
        assert state["sites"][0]["stages"][0]["status"] == "on_track"
