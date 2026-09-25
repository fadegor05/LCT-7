"""выгрузка отчёта в файлы: CSV, XLSX, HTML для печати.

Заказчик — департамент: выводы попадают в документооборот, а JSON туда не
приложишь. Три формата закрывают разные нужды:

- **CSV** — в Excel и любые таблицы, для ручной работы со списком отклонений;
- **XLSX** — два листа (статусы и алерты) с заголовками, чтобы открыть и читать;
- **HTML** — для печати и сохранения в PDF средствами браузера (отдельная
  библиотека ради этого не нужна).

Оговорки `cannot_claim` переносятся во все форматы: это часть вывода, а не
примечание для разработчика.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from html import escape

STATUS_RU = {
    "ahead": "опережение",
    "on_track": "в графике",
    "behind": "отставание",
    "not_started": "не начат",
    "not_observed": "нет наблюдений",
    "not_checkable": "не проверяется по технике",
    "no_rule": "нет правила в методике",
}

ALERT_RU = {
    "stage_behind": "отставание этапа",
    "stage_not_started": "этап не начат",
    "stage_stalled": "этап не сменяется",
    "missing_equipment": "не хватает техники",
    "unexpected_equipment": "непредусмотренная техника",
    "no_progress": "нет изменений",
    "unusable_data": "данные вне анализа",
    "plan_invalid": "строки плана не разобраны",
    "unknown_stages": "этапы вне методики",
}


def _stage_rows(report: dict) -> list[list]:
    rows = []
    for site in report["sites"]:
        for stage in site["stages"]:
            planned = stage.get("planned") or {}
            rows.append([
                site["site_id"], site.get("as_of") or "",
                stage["stage_code"], stage["stage_name"],
                planned.get("start", ""), planned.get("end", ""),
                STATUS_RU.get(stage["status"], stage["status"]),
                stage.get("delay_days", ""), stage.get("basis", ""),
            ])
    return rows


def _alert_rows(report: dict) -> list[list]:
    rows = []
    for site in report["sites"]:
        for alert in site.get("alerts", []):
            window = alert.get("window") or {}
            rows.append([
                site["site_id"],
                ALERT_RU.get(alert["type"], alert["type"]),
                alert.get("stage_code", ""),
                window.get("from", ""), window.get("to", ""),
                alert.get("confidence", ""),
                alert.get("explanation", ""),
                alert.get("cannot_claim", ""),
                ", ".join(alert.get("evidence", [])[:4]),
            ])
    return rows


STAGE_HEAD = ["Площадка", "Наблюдения на дату", "Код этапа", "Этап",
              "План: начало", "План: окончание", "Статус", "Отклонение, дн.", "Основание"]
ALERT_HEAD = ["Площадка", "Тип отклонения", "Код этапа", "Период с", "Период по",
              "Уверенность", "Описание", "Чего система не утверждает", "Снимки"]


def to_csv(report: dict, what: str = "stages") -> bytes:
    """CSV с разделителем «точка с запятой» и BOM: так Excel открывает без плясок."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    if what == "alerts":
        writer.writerow(ALERT_HEAD)
        writer.writerows(_alert_rows(report))
    else:
        writer.writerow(STAGE_HEAD)
        writer.writerows(_stage_rows(report))
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def _sheet_xml(head: list[str], rows: list[list]) -> str:
    def cell(ref: str, value) -> str:
        text = escape(str(value if value is not None else ""))
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'

    def col(i: int) -> str:
        name, i = "", i
        while True:
            name = chr(ord("A") + i % 26) + name
            i = i // 26 - 1
            if i < 0:
                return name

    out = [f'<row r="1">' + "".join(cell(col(i) + "1", h) for i, h in enumerate(head)) + "</row>"]
    for n, row in enumerate(rows, start=2):
        out.append(f'<row r="{n}">' + "".join(cell(col(i) + str(n), v)
                                              for i, v in enumerate(row)) + "</row>")
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>" + "".join(out) + "</sheetData></worksheet>")


def to_xlsx(report: dict) -> bytes:
    """Два листа: статусы этапов и отклонения.

    Файл собирается вручную из XML: тянуть openpyxl ради двух таблиц незачем,
    а лишняя зависимость в образе — лишний вес и лишний риск.
    """
    sheets = [("Статусы", STAGE_HEAD, _stage_rows(report)),
              ("Отклонения", ALERT_HEAD, _alert_rows(report))]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                             'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(sheets) + 1))
                   + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   "</Relationships>")
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                             for i, (name, _, _) in enumerate(sheets, start=1))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" '
                             'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                             f'Target="worksheets/sheet{i}.xml"/>'
                             for i in range(1, len(sheets) + 1))
                   + "</Relationships>")
        for i, (_, head, rows) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(head, rows))
    return buf.getvalue()


def to_html(report: dict, title: str = "Отчёт о ходе работ") -> bytes:
    """Страница для печати: браузер сохранит её в PDF без отдельной библиотеки."""
    meta = report.get("meta", {})
    made = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")

    def table(head: list[str], rows: list[list]) -> str:
        if not rows:
            return "<p class='empty'>Записей нет.</p>"
        th = "".join(f"<th>{escape(h)}</th>" for h in head)
        tr = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>"
                     for row in rows)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

    def forecast_block(site: dict) -> str:
        """Прогноз печатается словами: в документообороте читают текст, не JSON."""
        f = site.get("forecast") or {}
        if not f.get("shift_days"):
            return ""
        return (f"<p><b>{escape(str(site['site_id']))}:</b> сдвиг "
                f"{f['shift_days']} дн., завершение "
                f"{escape(str(f.get('planned_completion', '')))} → "
                f"{escape(str(f.get('projected_completion', '')))}. "
                f"<i>{escape(str(f.get('assumption', '')))}.</i></p>")

    forecasts = "".join(forecast_block(site) for site in report["sites"])
    forecast_html = ("<h2>Прогноз сроков</h2>" + forecasts +
                     "<p class='empty'>Срок не рассчитан по объёму выполненных работ: "
                     "объём по снимкам не измеряется. Это перенос наблюдаемой задержки "
                     "по графику.</p>") if forecasts else ""

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
 body {{ font: 14px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #1c1d22; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }}
 .sub {{ color: #666; margin-bottom: 20px; }}
 table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; font-size: 12px; }}
 th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }}
 th {{ background: #f4f4f6; }}
 .empty {{ color: #666; }}
 .note {{ background: #fff8e6; border-left: 3px solid #e0a800; padding: 10px 14px; margin: 18px 0; }}
 @media print {{ body {{ margin: 0; }} table {{ page-break-inside: auto; }} tr {{ page-break-inside: avoid; }} }}
</style></head><body>
<h1>{escape(title)}</h1>
<div class="sub">Сформирован {made} · площадок: {meta.get('sites', '—')} ·
 наблюдений: {meta.get('observations', '—')} · кадров использовано:
 {meta.get('frames_used', '—')} из {meta.get('frames_in', '—')}</div>
<h2>Статусы этапов</h2>
{table(STAGE_HEAD, _stage_rows(report))}
<h2>Отклонения</h2>
{table(ALERT_HEAD, _alert_rows(report))}
{forecast_html}
<div class="note"><b>Как читать.</b> «Нет наблюдений» — утверждение о наших данных,
 а не о стройке: снимков за период не было. «Не проверяется по технике» — этап,
 который по видимой технике определить нельзя. Колонка «чего система не
 утверждает» — обязательная часть вывода, а не примечание.</div>
</body></html>""".encode("utf-8")
