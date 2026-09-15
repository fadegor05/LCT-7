# -*- coding: utf-8 -*-
"""Сличает выгрузку read_date_stamp.py с эталонной разметкой дат.

Recall считается от числа кадров, на которых штамп физически есть, а не от
общего числа снимков: кадры без штампа в знаменатель не входят.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

DEFAULT_TRUTH = Path("data/reference/date_stamps_groundtruth.csv")
DEFAULT_PRED = Path("data/processed/date_stamps.json")


def load_truth(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {r["image"]: r["expected_date"] for r in csv.DictReader(fh, delimiter=";")}


def load_pred(path: Path) -> dict[str, str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["image"]: (r["date"] or "") for r in rows}


def evaluate(truth: dict[str, str], pred: dict[str, str]) -> tuple[dict, list]:
    correct, wrong, missed, false_positive = [], [], [], []

    for image, expected in truth.items():
        got = pred.get(image, "")
        if expected and got == expected:
            correct.append(image)
        elif expected and got:
            wrong.append((image, expected, got))
        elif expected:
            missed.append((image, expected, ""))
        elif got:
            false_positive.append((image, "", got))

    with_stamp = sum(1 for v in truth.values() if v)
    recognized = sum(1 for image, v in truth.items() if v and pred.get(image))

    summary = {
        "снимков": len(truth),
        "со штампом": with_stamp,
        "распознано": recognized,
        "верно": len(correct),
        "recall": round(len(correct) / with_stamp, 4) if with_stamp else None,
        "precision": round(len(correct) / recognized, 4) if recognized else None,
        "ошибок": len(wrong),
        "пропусков": len(missed),
        "ложных срабатываний": len(false_positive),
    }
    discrepancies = ([("ОШИБКА", *w) for w in wrong]
                     + [("ПРОПУСК", *m) for m in missed]
                     + [("ЛОЖНОЕ", *f) for f in false_positive])
    return summary, discrepancies


def main() -> int:
    ap = argparse.ArgumentParser(description="Оценка распознавания дат по эталону")
    ap.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    ap.add_argument("--pred", type=Path, default=DEFAULT_PRED)
    ap.add_argument("--min-recall", type=float, help="завершиться с ошибкой, если recall ниже")
    ap.add_argument("--min-precision", type=float, help="завершиться с ошибкой, если precision ниже")
    args = ap.parse_args()

    missing = [p for p in (args.truth, args.pred) if not p.exists()]
    if missing:
        print("не найдено: " + ", ".join(str(p) for p in missing), file=sys.stderr)
        return 2

    summary, discrepancies = evaluate(load_truth(args.truth), load_pred(args.pred))

    width = max(len(k) for k in summary)
    for key, value in summary.items():
        print(f"{key:<{width}}  {value}")

    if discrepancies:
        print("\nрасхождения:")
        for kind, image, expected, got in sorted(discrepancies, key=lambda d: d[1]):
            print(f"  {kind:<8} {image:<22} эталон: {expected or '—':<12} получено: {got or '—'}")

    below = []
    if args.min_recall is not None and (summary["recall"] or 0) < args.min_recall:
        below.append(f"recall {summary['recall']} < {args.min_recall}")
    if args.min_precision is not None and (summary["precision"] or 0) < args.min_precision:
        below.append(f"precision {summary['precision']} < {args.min_precision}")
    if below:
        print("\nниже порога: " + "; ".join(below), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
