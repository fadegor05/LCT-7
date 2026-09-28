"""определение стадии по виду площадки, а не только по технике (Q&A 22:27).

Заказчик спросил прямо: можно ли понять стадию по тому, как выглядит объект, —
котлован, шпунтовое ограждение, плита, каркас, — а не только по стоящей технике.
Вопрос честный и проверяемый, поэтому мы его и проверяем замером, а не
рассуждением.

Как устроена проверка:

- **метка** — стадия по виду сцены: `prep` (площадка расчищена, техника
  планирует), `piling` (свайные работы, копры и обсадные трубы), `pit`
  (открытый котлован, земляные работы), `substructure` (плита, стены и колонны
  подземной части), `superstructure` (каркас выше нуля). Размечено на всех 100
  выданных кадрах, файл `data/reference/scene_stage.csv`;
- **признаки вида** — выходы замороженной ResNet-50 (ImageNet), обучается только
  линейный слой. Так мы отвечаем на вопрос «есть ли стадия в картинке», а не
  «можем ли мы обучить большую модель на 100 кадрах»;
- **признаки техники** — счётчики наших 25 классов на кадре. Это базовый уровень:
  ровно то, что система умеет и без вида сцены;
- **проверка** — по площадкам (leave-one-site-out). Кадры одной стройки похожи
  между собой, и обычное случайное разбиение дало бы завышенную цифру: модель
  запомнила бы площадку, а не стадию. Кадры без привязки к площадке в замер не
  идут вовсе — по ним нельзя гарантировать, что стройка не попала и в обучение.

Вывод замера печатается в конце и записан в `EXPERIMENTS.md`.

    python tools/scene_stage.py                 # пять стадий
    python tools/scene_stage.py --task piling   # свайные работы против всего
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

ML = Path(__file__).resolve().parents[1]
IMAGES = ML / "data" / "raw" / "dataset" / "images" / "Строительная_техника"
LABELS = ML / "data" / "reference" / "scene_stage.csv"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Варианты задачи. Пять стадий на 59 кадрах — заведомо мало, поэтому мы честно
# проверяем и укрупнённые постановки: вдруг сигнал есть, но не такой дробный.
TASKS = {
    "stage": lambda s: s,
    "coarse": lambda s: {"finishing": "above", "superstructure": "above",
                         "substructure": "above"}.get(s, s),
    "piling": lambda s: s if s == "piling" else "other",
    "pit": lambda s: s if s == "pit" else "other",
}


def read_labels() -> list[dict]:
    with open(LABELS, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def imread(path: Path) -> np.ndarray | None:
    """cv2.imread не открывает пути с кириллицей — читаем через буфер."""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def visual_features(names: list[str]) -> np.ndarray:
    """Признаки замороженной ResNet-50: 2048 чисел на кадр."""
    from torchvision import models, transforms

    net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    net.fc = nn.Identity()
    net.eval().to(DEVICE)
    prep = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((384, 384), antialias=True),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    out = []
    with torch.no_grad():
        for name in names:
            img = imread(IMAGES / name)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            batch = prep(rgb).unsqueeze(0).to(DEVICE)
            out.append(net(batch).cpu().numpy()[0])
    return np.stack(out)


def equipment_features(names: list[str], dets_path: Path) -> tuple[np.ndarray, list[str]]:
    """Базовый уровень: сколько машин каждого класса видно на кадре."""
    data = json.loads(dets_path.read_text(encoding="utf-8"))
    by_image = {item["image"]: item.get("detections", []) for item in data["images"]}
    classes = sorted({d["class_ours"] for dets in by_image.values() for d in dets})
    rows = []
    for name in names:
        counts = Counter(d["class_ours"] for d in by_image.get(name, []))
        rows.append([counts.get(c, 0) for c in classes])
    return np.array(rows, dtype=np.float32), classes


def fit_linear(x: np.ndarray, y: np.ndarray, n_classes: int, epochs: int = 300) -> nn.Module:
    """Линейный классификатор с весовым затуханием.

    Обучается только он: признаки заморожены. На 50 кадрах это единственный
    честный вариант — всё остальное переобучится на площадку.
    """
    # Фиксируем начальное приближение: без этого разные запуски дают разброс
    # в несколько процентов, и сравнение «вид против техники» теряет смысл.
    torch.manual_seed(0)
    model = nn.Linear(x.shape[1], n_classes).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=0.05)
    xt = torch.tensor(x, dtype=torch.float32, device=DEVICE)
    yt = torch.tensor(y, dtype=torch.long, device=DEVICE)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
        opt.zero_grad()
        loss_fn(model(xt), yt).backward()
        opt.step()
    return model.eval()


def leave_site_out(x: np.ndarray, y: np.ndarray, sites: list[str],
                   n_classes: int) -> tuple[float, list[tuple[str, int, int]]]:
    """Обучаем на всех площадках кроме одной, проверяем на ней. И так по кругу."""
    correct, per_site = 0, []
    for site in sorted(set(sites)):
        test = np.array([s == site for s in sites])
        if test.sum() == 0 or (~test).sum() < 5:
            continue
        mean, std = x[~test].mean(0), x[~test].std(0) + 1e-6
        model = fit_linear((x[~test] - mean) / std, y[~test], n_classes)
        with torch.no_grad():
            xt = torch.tensor((x[test] - mean) / std, dtype=torch.float32, device=DEVICE)
            pred = model(xt).argmax(1).cpu().numpy()
        hit = int((pred == y[test]).sum())
        correct += hit
        per_site.append((site, hit, int(test.sum())))
    total = sum(n for _, _, n in per_site)
    return (correct / total if total else 0.0), per_site


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dets", default="data/processed/detections_mocs_m.json",
                    help="детекции нашей модели для базового уровня «по технике»")
    ap.add_argument("--task", default="stage", choices=sorted(TASKS),
                    help="какую метку предсказываем: все стадии или одна против всех")
    args = ap.parse_args()

    rows = [r for r in read_labels() if r["site_id"]]
    for row in rows:
        row["appearance_stage"] = TASKS[args.task](row["appearance_stage"])
    # Кадры без площадки выбрасываем: по ним нельзя гарантировать, что та же
    # стройка не попала в обучение, и проверка перестанет быть честной.
    stages = sorted({r["appearance_stage"] for r in rows})
    idx = {s: i for i, s in enumerate(stages)}
    names = [r["image"] for r in rows]
    sites = [r["site_id"] for r in rows]
    y = np.array([idx[r["appearance_stage"]] for r in rows])

    print(f"кадров с известной площадкой: {len(rows)}, площадок: {len(set(sites))}")
    print("стадии:", dict(Counter(r["appearance_stage"] for r in rows)))

    common = Counter(y).most_common(1)[0][1] / len(y)
    print(f"\nбаза «всегда самая частая стадия»: {common:.3f}")

    xe, classes = equipment_features(names, ML / args.dets)
    acc_e, per_e = leave_site_out(xe, y, sites, len(stages))
    print(f"только по технике ({len(classes)} классов): {acc_e:.3f}")

    xv = visual_features(names)
    acc_v, per_v = leave_site_out(xv, y, sites, len(stages))
    print(f"по виду сцены (ResNet-50, заморожена): {acc_v:.3f}")

    xb = np.hstack([xv, xe * 10])  # счётчики мельче признаков, поднимаем масштаб
    acc_b, _ = leave_site_out(xb, y, sites, len(stages))
    print(f"вид + техника вместе: {acc_b:.3f}")

    print("\nпо площадкам (вид сцены):")
    for site, hit, n in per_v:
        print(f"  {site}: {hit}/{n}")


if __name__ == "__main__":
    main()
