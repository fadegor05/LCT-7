"""языковая модель предлагает соответствие «название работы → наш этап».

Зачем именно здесь. Заказчик просил давать вывод по план-факту «в том числе на
основе языковых моделей» (Q&A 12:03). Но в сам вывод такую модель пускать
нельзя: отчёт уходит в департамент, и каждая цифра там должна быть прослеживаема
до правила и снимка. Есть, однако, место, где языковая модель уместна и
безопасна — **разбор названий работ из календарного плана заказчика**.

Задача ровно такая, для какой языковые модели и созданы: сопоставить
произвольную человеческую формулировку с закрытым списком. Сейчас это делают
регулярные выражения в `configs/stage_mapping.json`, и на присланном заказчиком
перечне из 374 строк они распознали **ноль** этапов: там свои формулировки.

Почему это безопасно, в отличие от генерации выводов:

1. **Модель не пишет текст, а выбирает из списка.** Ответ обязан быть кодом
   этапа из `configs/rules.json` либо словом `none`. Всё остальное отвергается
   на месте — проверяет код, а не доверие.
2. **Результат не применяется сам.** Это черновик соответствий, который человек
   просматривает и переносит в `configs/stage_mapping.json` руками. Между
   моделью и выводом стоит человек.
3. **Ошибка видна сразу.** Неверное соответствие обнаруживается при импорте
   плана, а не всплывает через месяц в отчёте цифрой без основания.

Провайдер не зашит: нужен адрес, совместимый с форматом chat completions, и это
покрывает и облачные сервисы, и локальную модель. Настройки — в `ml/.env`:

    LLM_BASE_URL=https://.../v1
    LLM_API_KEY=...
    LLM_MODEL=...

**Без настроек инструмент не падает**, а печатает, что именно он отправил бы, и
выходит. Это нужно, чтобы цепочка и тесты не зависели от внешнего сервиса.

    python tools/suggest_stage_mapping.py --names data/processed/unmapped.txt
    python tools/suggest_stage_mapping.py --plan "план.xlsx" --site p12
    python tools/suggest_stage_mapping.py --names имена.txt --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "tools"))

RULES = ML / "configs" / "rules.json"
MAPPING = ML / "configs" / "stage_mapping.json"

SYSTEM = (
    "Ты помогаешь сопоставить названия строительных работ из календарного плана "
    "с закрытым списком этапов. Отвечай только кодом этапа из списка или словом "
    "none, если подходящего этапа нет. Никаких пояснений."
)


def from_env(key: str) -> str | None:
    """Значение из окружения либо из ml/.env; .env в git не попадает."""
    value = os.environ.get(key)
    if value:
        return value
    env = ML / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip() or None
    return None


def load_stages() -> dict[str, str]:
    data = json.loads(RULES.read_text(encoding="utf-8"))
    return {r["stage_code"]: r["stage_name"] for r in data["rules"]}


def already_mapped(name: str) -> str | None:
    """Что скажет действующая таблица регулярных выражений."""
    data = json.loads(MAPPING.read_text(encoding="utf-8"))
    for rule in data["rules"]:
        if re.search(rule["pattern"], name, re.IGNORECASE):
            return rule["stage_code"]
    return None


def build_prompt(names: list[str], stages: dict[str, str]) -> str:
    catalog = "\n".join(f"{code} — {title}" for code, title in stages.items())
    listed = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(names))
    return (f"Список этапов:\n{catalog}\n\n"
            f"Названия работ:\n{listed}\n\n"
            f"Для каждой работы верни строку вида «номер|код_этапа». "
            f"Если подходящего этапа нет — «номер|none». "
            f"Ровно {len(names)} строк, без заголовков и пояснений.")


def ask(prompt: str, base_url: str, api_key: str, model: str, timeout: int = 120) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return data["choices"][0]["message"]["content"]


def parse_answer(text: str, names: list[str], stages: dict[str, str]) -> list[dict]:
    """Ответ модели → предложения. Всё, что вне списка этапов, отбрасывается.

    Проверяет код, а не доверие: модель может ответить что угодно, включая
    правдоподобно выглядящий, но несуществующий код этапа.
    """
    out, rejected = [], 0
    for line in text.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 2:
            continue
        index, code = parts[0].strip(), parts[1].strip()
        if not index.isdigit():
            continue
        position = int(index) - 1
        if not 0 <= position < len(names):
            continue
        if code == "none":
            continue
        if code not in stages:
            rejected += 1
            continue
        out.append({"name": names[position], "stage_code": code,
                    "stage_name": stages[code], "source": "llm-suggestion"})
    if rejected:
        print(f"отброшено ответов с несуществующим кодом этапа: {rejected}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", type=Path, help="файл со списком названий работ, по одному в строке")
    ap.add_argument("--plan", type=Path, help="план заказчика: взять из него нераспознанные работы")
    ap.add_argument("--site", default="p00", help="идентификатор площадки для разбора плана")
    ap.add_argument("--limit", type=int, default=60, help="сколько названий отправлять за раз")
    ap.add_argument("--dry-run", action="store_true", help="показать запрос и выйти")
    ap.add_argument("-o", "--out", type=Path,
                    default=ML / "data/processed/stage_mapping_suggested.json")
    args = ap.parse_args()

    stages = load_stages()
    names: list[str] = []

    if args.plan:
        from parse_schedule import classify_rows, load_mapping, read_pdf, read_xlsx
        suffix = args.plan.suffix.lower()
        if suffix not in (".xlsx", ".pdf"):
            raise SystemExit(f"формат «{suffix}» не поддерживается: нужен .xlsx или .pdf")
        raw = read_xlsx(args.plan) if suffix == ".xlsx" else read_pdf(args.plan)
        _, skipped, _, _, _ = classify_rows(raw, load_mapping(MAPPING), args.site)
        names = skipped
    elif args.names:
        names = [line.strip() for line in
                 args.names.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        raise SystemExit("нужен --names или --plan")

    # Убираем дубликаты, сохраняя порядок: в планах одна работа повторяется
    # десятками строк по секциям, и платить за неё десять раз незачем.
    unique = list(dict.fromkeys(names))[:args.limit]
    print(f"названий без соответствия: {len(names)}, уникальных к разбору: {len(unique)}")
    if not unique:
        print("разбирать нечего: действующая таблица покрывает все названия")
        return 0

    prompt = build_prompt(unique, stages)
    base_url, api_key, model = (from_env("LLM_BASE_URL"), from_env("LLM_API_KEY"),
                                from_env("LLM_MODEL"))

    if args.dry_run or not (base_url and api_key and model):
        if not args.dry_run:
            print("\nЯзыковая модель не настроена: нет LLM_BASE_URL, LLM_API_KEY или "
                  "LLM_MODEL в ml/.env.\nПоказываю запрос, который был бы отправлен.\n")
        print("--- системная часть ---")
        print(SYSTEM)
        print("\n--- запрос ---")
        print(prompt[:1500] + ("..." if len(prompt) > 1500 else ""))
        return 0

    print(f"модель: {model}")
    answer = ask(prompt, base_url, api_key, model)
    suggestions = parse_answer(answer, unique, stages)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "_comment": ("Черновик соответствий, предложенный языковой моделью. "
                     "Сам по себе НЕ применяется: перенесите проверенные строки в "
                     "configs/stage_mapping.json руками. Между моделью и выводом "
                     "стоит человек — это условие, при котором языковая модель "
                     "вообще допущена в проект."),
        "model": model,
        "suggestions": suggestions,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nпредложено соответствий: {len(suggestions)} из {len(unique)}")
    for s in suggestions[:12]:
        print(f"   {s['stage_code']:<14}{s['name'][:60]}")
    print(f"\nчерновик: {args.out}")
    print("Проверьте и перенесите нужное в configs/stage_mapping.json — "
          "автоматически он не применяется.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
