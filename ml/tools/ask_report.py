"""вопрос по отчёту на естественном языке — с проверкой каждого числа в ответе.

Заказчик просил давать вывод по план-факту «в том числе на основе языковых
моделей» (Q&A 12:03). Сам вывод мы порождаем правилами и менять это не
собираемся (D-020): отчёт уходит в департамент, и каждое число там должно быть
прослеживаемо до нормы и снимка. Но читать отчёт из полусотни полей неудобно, и
вот здесь языковая модель на месте — она **пересказывает готовые данные**, а не
принимает решения.

Опасность очевидна: пересказывая, модель может подставить число, которого в
отчёте нет. Обычно с этим борются уговорами в запросе. Мы делаем иначе.

**Каждое число из ответа проверяется по исходным данным.** Все числа отчёта
собираются заранее в множество; после ответа из него извлекаются числа и
сверяются. Не нашли — ответ помечается `verified: false` и списком
неподтверждённых чисел, и подавать его как факт нельзя. Это не уговор, а
проверка: модель не может обойти её красноречием.

Ограничения, которые честно остаются:

- проверяются **числа**, а не смысл. Модель может верно назвать число и неверно
  его истолковать — от этого метод не спасает;
- отказ «в данных этого нет» мы просим, но гарантировать не можем;
- ответ — всегда пересказ отчёта. Единственный источник истины — сам отчёт, и
  ссылки на площадку и этап приводятся именно для того, чтобы можно было
  свериться.

    python tools/ask_report.py "где отставание и на сколько"
    python tools/ask_report.py "что с p03" --report data/processed/report.json
    python tools/ask_report.py "..." --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "tools"))

from suggest_stage_mapping import ask, from_env  # noqa: E402

SYSTEM = (
    "Ты отвечаешь на вопросы по отчёту о ходе строительных работ. Отвечай "
    "только по данным отчёта, кратко и по-русски. Если сведений в отчёте нет, "
    "так и скажи: «в данных этого нет». Не оценивай и не советуй — только "
    "пересказывай то, что в отчёте. Обязательно называй площадку и код этапа, "
    "о которых говоришь."
)

def normalise(text: str) -> str:
    """Склеивает разряды, разделённые пробелом: «4 500 000» → «4500000».

    Без этого проверка разбирала такое число на куски, каждый из которых
    по отдельности мог найтись в отчёте, и выдумка проходила незамеченной.
    """
    return re.sub(r"(?<=\d)[   ](?=\d{3}\b)", "", text)


def collect_numbers(data) -> set[str]:
    """Все числа, встречающиеся в отчёте, включая даты по частям.

    Дату `2024-03-31` раскладываем на части: модель законно напишет
    «31 марта 2024», и тогда в ответе окажутся 31 и 2024 по отдельности.
    """
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            found.add(str(node).rstrip("0").rstrip(".") if isinstance(node, float)
                      else str(node))
        elif isinstance(node, str):
            for part in re.findall(r"\d+", node):
                found.add(part.lstrip("0") or "0")
                found.add(part)

    walk(data)
    return found


def unverified(answer: str, known: set[str]) -> list[str]:
    """Числа из ответа, которых нет в отчёте.

    Список исключений намеренно не заводится: если число встречается в отчёте,
    оно уже в `known`, а «общеупотребительные» числа вроде 10 или 100 — ровно
    тот случай, где выдумка и прячется.

    **Чего проверка не умеет.** Она сверяет числа, а не их смысл: если модель
    назовёт верное число не про тот этап, проверка этого не заметит. И если
    выдуманное число случайно совпадёт с каким-нибудь другим числом отчёта, оно
    пройдёт. Поэтому проверка — сито, а не доказательство.
    """
    out = []
    for raw in re.findall(r"\d+(?:[.,]\d+)?", normalise(answer)):
        token = raw.replace(",", ".")
        plain = token.split(".")[0].lstrip("0") or "0"
        if token in known or plain in known:
            continue
        out.append(raw)
    return sorted(set(out))


def numbers_by_site(data: dict) -> dict[str, set[str]]:
    """Числа в разрезе площадок плюс общие числа отчёта.

    Нужно для второго уровня проверки. Первый ловит число, которого в отчёте
    нет вовсе; этот — число, которое в отчёте есть, но относится к другой
    площадке. Именно так выглядит самая правдоподобная ошибка пересказа.
    """
    out = {"_общие": collect_numbers(data.get("meta", {}))}
    for site in data.get("sites", []):
        out[site["site_id"]] = collect_numbers(site)
    return out


def misattributed(answer: str, by_site: dict[str, set[str]]) -> list[str]:
    """Числа, названные не про ту площадку.

    Ответ режется по упоминаниям площадок: всё, что сказано после «p03» и до
    следующего упоминания, считается сказанным про p03.
    """
    marks = list(re.finditer(r"\bp\d{2}\b", answer))
    if not marks:
        return []
    problems = []
    for i, mark in enumerate(marks):
        site = mark.group(0)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(answer)
        fragment = normalise(answer[mark.end():end])
        allowed = by_site.get(site, set()) | by_site.get("_общие", set())
        for raw in re.findall(r"\d+(?:[.,]\d+)?", fragment):
            token = raw.replace(",", ".")
            plain = token.split(".")[0].lstrip("0") or "0"
            if token in allowed or plain in allowed:
                continue
            problems.append(f"{site}: {raw}")
    return sorted(set(problems))


def compact(report: dict, site: str | None = None) -> dict:
    """Отчёт без служебных полей: модели нужен смысл, а не весь JSON.

    Выкидываем то, что не помогает ответить и только раздувает запрос: списки
    кадров-доказательств оставляем по паре штук, длинные основания — целиком,
    потому что именно из них берутся формулировки.
    """
    sites = [s for s in report.get("sites", [])
             if not site or s["site_id"] == site]
    out = []
    for s in sites:
        out.append({
            "site_id": s["site_id"],
            "as_of": s.get("as_of"),
            "observations": s.get("observations"),
            "observation_step_days": s.get("observation_step_days"),
            "stages": [{k: v for k, v in stage.items() if k != "engagement"}
                       for stage in s.get("stages", [])],
            "forecast": s.get("forecast"),
            "alerts": [{**{k: v for k, v in a.items() if k != "evidence"},
                        "evidence": a.get("evidence", [])[:2]}
                       for a in s.get("alerts", [])],
        })
    return {"meta": report.get("meta", {}), "sites": out}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", help="вопрос по отчёту")
    ap.add_argument("--report", type=Path, default=ML / "data/processed/report.json")
    ap.add_argument("--site", help="ограничить одной площадкой")
    ap.add_argument("--dry-run", action="store_true", help="показать запрос и выйти")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    data = compact(report, args.site)
    known = collect_numbers(data)

    prompt = (f"Отчёт:\n{json.dumps(data, ensure_ascii=False)}\n\n"
              f"Вопрос: {args.question}")

    base_url, api_key, model = (from_env("LLM_BASE_URL"), from_env("LLM_API_KEY"),
                                from_env("LLM_MODEL"))
    if args.dry_run or not (base_url and api_key and model):
        if not args.dry_run:
            print("Языковая модель не настроена (LLM_BASE_URL, LLM_API_KEY, "
                  "LLM_MODEL в ml/.env). Показываю запрос.\n")
        print(f"площадок в запросе: {len(data['sites'])}, "
              f"чисел для сверки: {len(known)}, размер запроса: {len(prompt)} знаков")
        print(prompt[:1200] + ("..." if len(prompt) > 1200 else ""))
        return 0

    answer = ask(prompt, base_url, api_key, model, timeout=args.timeout, system=SYSTEM)
    bad = unverified(answer, known)
    wrong_site = misattributed(answer, numbers_by_site(data))

    print(answer.strip())
    print("\n" + "-" * 60)
    if bad:
        print(f"НЕ ПРОЙДЕНО: этих чисел нет в отчёте — {', '.join(bad)}")
    if wrong_site:
        print(f"НЕ ПРОЙДЕНО: число есть в отчёте, но не по этой площадке — "
              f"{', '.join(wrong_site)}")
    if not bad and not wrong_site:
        print("Проверка пройдена: каждое число из ответа есть в отчёте и "
              "относится к названной площадке.")
    else:
        print("Ответ нельзя подавать как факт: сверьтесь с отчётом.")
    print("Проверяются числа, а не смысл: верное число может быть отнесено не к "
          "тому этапу, и этого проверка не увидит.")
    print("Источник истины — сам отчёт; ответ выше лишь пересказывает его.")
    return 0 if not (bad or wrong_site) else 2


if __name__ == "__main__":
    raise SystemExit(main())
