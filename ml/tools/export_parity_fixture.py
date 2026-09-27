#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Экспорт фикстуры для тестирования паритета: backend vs ML /report.

Собирает наблюдения из детекций MOCS и расписания, строит ML-отчёт и записывает
фиксированные данные для backend-теста в backend/tests/fixtures/ml_demo/.

Использование:
    python tools/export_parity_fixture.py [--output /path/to/fixtures]

Выходные файлы:
    - frames.json: наблюдения (image, site_id, date, width, height, detections)
    - schedule_demo.csv: копия расписания (через точку с запятой)
    - report.json: результат build_report() — статусы этапов и алерты
"""

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

# Добавляем ml в путь для импорта
ML = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML))
sys.path.insert(0, str(ML / "tools"))

import csv
from service.pipeline import build_report


def load_sites_csv(path: Path) -> dict[str, tuple[str, str]]:
    """sites.csv → {image: (site_id, date)}."""
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            result[row["image"]] = (row["site_id"].strip(), row.get("date", "").strip())
    return result


def load_detections_json(path: Path) -> dict[str, dict]:
    """detections_mocs_m.json → {image: {width, height, detections}}."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {img["image"]: img for img in data.get("images", [])}


def load_schedule_csv(path: Path) -> list[dict]:
    """schedule_demo.csv → [{site_id, stage_code, stage_name, planned_start, planned_end, note}]."""
    result = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            result.append({
                "site_id": row["site_id"].strip(),
                "stage_code": row["stage_code"].strip(),
                "stage_name": row["stage_name"].strip(),
                "planned_start": row["planned_start"].strip(),
                "planned_end": row["planned_end"].strip(),
                "note": row.get("note", "").strip(),
            })
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ML.parent / "backend" / "tests" / "fixtures" / "ml_demo",
        help="Директория для выходных файлов (default: backend/tests/fixtures/ml_demo)",
    )
    args = parser.parse_args()

    # Пути к входным данным
    detections_path = ML / "data" / "processed" / "detections_mocs_m.json"
    sites_path = ML / "data" / "reference" / "sites.csv"
    schedule_path = ML / "data" / "reference" / "schedule_demo.csv"

    # Проверяем наличие входных файлов
    for path in [detections_path, sites_path, schedule_path]:
        if not path.exists():
            print(f"❌ Файл не найден: {path}", file=sys.stderr)
            return 1

    # Загружаем данные
    print("📖 Загружаю данные...", file=sys.stderr)
    sites_map = load_sites_csv(sites_path)
    detections_map = load_detections_json(detections_path)
    schedule = load_schedule_csv(schedule_path)

    # Определяем площадки в расписании
    schedule_sites = {row["site_id"] for row in schedule}
    print(f"  Площадки в расписании: {sorted(schedule_sites)}", file=sys.stderr)

    # Собираем наблюдения
    print("🔍 Собираю наблюдения...", file=sys.stderr)
    observations = []
    skipped_images = 0
    images_in_schedule = 0

    for image_name, (site_id, date) in sorted(sites_map.items()):
        # Пропускаем если площадка не в расписании
        if site_id not in schedule_sites:
            continue

        images_in_schedule += 1

        # Пропускаем если нет детекций для этого кадра
        if image_name not in detections_map:
            print(f"  ⚠️  Детекции не найдены для {image_name}", file=sys.stderr)
            skipped_images += 1
            continue

        det_data = detections_map[image_name]
        observations.append({
            "image": image_name,
            "site_id": site_id,
            "date": date,
            "width": det_data.get("width", 0),
            "height": det_data.get("height", 0),
            "detections": det_data.get("detections", []),
        })

    print(f"  ✅ Собрано {len(observations)} наблюдений "
          f"({skipped_images} пропущено из {images_in_schedule})", file=sys.stderr)

    # Строим отчёт
    print("📊 Строю отчёт...", file=sys.stderr)
    report = build_report(observations, schedule)
    sites_count = len(report.get("sites", []))
    print(f"  ✅ Обработано {sites_count} площадок", file=sys.stderr)

    # Создаём выходную директорию
    args.output.mkdir(parents=True, exist_ok=True)

    # Записываем frames.json (отсортированный по ключам, красивый вывод)
    frames_path = args.output / "frames.json"
    with frames_path.open("w", encoding="utf-8") as f:
        # Сортируем наблюдения по image для детерминированности
        sorted_obs = sorted(observations, key=lambda x: x["image"])
        json.dump(sorted_obs, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"✅ Записан {frames_path}", file=sys.stderr)

    # Записываем копию schedule_demo.csv
    schedule_copy_path = args.output / "schedule_demo.csv"
    with schedule_copy_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["site_id", "stage_code", "stage_name", "planned_start", "planned_end", "note"],
            delimiter=";",
        )
        writer.writeheader()
        for row in schedule:
            writer.writerow(row)
    print(f"✅ Записан {schedule_copy_path}", file=sys.stderr)

    # Записываем report.json
    report_path = args.output / "report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"✅ Записан {report_path}", file=sys.stderr)

    print("✅ Готово!", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
