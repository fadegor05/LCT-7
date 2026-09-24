"""второй этап: классификатор вырезов «кран / буровая / копёр / башенный кран».

Зачем: главная ошибка детектора — путаница крана с буровой (15 случаев в обе
стороны на p03/p08). У них одинаковая гусеничная база и высокая вертикаль;
различие — в устройстве вертикали, и на вырезе 224x224 оно видно, а на полном
кадре машина занимает несколько процентов площади.

Детектор не меняем: он ищет объект, классификатор уточняет класс внутри группы.
Задача классификатора проще — не искать, а различить.

Магистраль берём предобученную на ImageNet и дообучаем целиком: своих данных
мало (3.4 тыс. вырезов), учить с нуля нечего. Разрез по площадкам тот же, что у
детектора: p03 и p08 только в проверке.
"""

import argparse, json
from collections import Counter
from pathlib import Path

ML = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ML / "data/interim/crops")
    ap.add_argument("--arch", default="convnext_tiny",
                    choices=["resnet18", "convnext_tiny", "swin_t", "efficientnet_b0"])
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--out", type=Path, default=ML / "weights")
    args = ap.parse_args()

    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms, models

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # аугментация умеренная: мачта и стрела — вертикальные структуры, поворот
    # и сильный сдвиг их искажают, а именно по ним мы и различаем классы
    tf_train = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.75, 1.0), ratio=(0.85, 1.18)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.25, 0.25, 0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    tf_val = transforms.Compose([
        transforms.Resize(224), transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    tr = datasets.ImageFolder(args.data / "train", tf_train)
    va = datasets.ImageFolder(args.data / "val", tf_val)
    classes = tr.classes
    print("классы:", classes)
    print("обучение:", dict(Counter(classes[y] for _, y in tr.samples)))
    print("проверка:", dict(Counter(va.classes[y] for _, y in va.samples)))

    # веса классов: копров у нас десятки против тысяч кранов
    counts = Counter(y for _, y in tr.samples)
    w = torch.tensor([len(tr) / (len(classes) * counts[i]) for i in range(len(classes))],
                     dtype=torch.float, device=dev)
    print("веса классов:", [round(float(x), 2) for x in w])

    dl_tr = DataLoader(tr, batch_size=args.batch, shuffle=True, num_workers=0, drop_last=True)
    dl_va = DataLoader(va, batch_size=args.batch, shuffle=False, num_workers=0)

    net = getattr(models, args.arch)(weights="DEFAULT")
    head = {"resnet18": "fc", "convnext_tiny": "classifier", "swin_t": "head",
            "efficientnet_b0": "classifier"}[args.arch]
    mod = getattr(net, head)
    if isinstance(mod, nn.Sequential):
        idx = len(mod) - 1
        mod[idx] = nn.Linear(mod[idx].in_features, len(classes))
    else:
        setattr(net, head, nn.Linear(mod.in_features, len(classes)))
    net = net.to(dev)

    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    lossf = nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)

    best, best_state = 0.0, None
    for ep in range(1, args.epochs + 1):
        net.train()
        for x, y in dl_tr:
            x, y = x.to(dev), y.to(dev)
            opt.zero_grad()
            loss = lossf(net(x), y)
            loss.backward()
            opt.step()
        sched.step()

        net.eval()
        conf = Counter(); ok = tot = 0
        with torch.no_grad():
            for x, y in dl_va:
                pred = net(x.to(dev)).argmax(1).cpu()
                for t, p in zip(y.tolist(), pred.tolist()):
                    conf[(classes[t], classes[p])] += 1
                    ok += t == p; tot += 1
        # сбалансированная точность: классы в проверке неравные
        per = {}
        for c in classes:
            n = sum(v for (t, _), v in conf.items() if t == c)
            hit = conf[(c, c)]
            if n:
                per[c] = hit / n
        bal = sum(per.values()) / len(per) if per else 0
        print(f"эпоха {ep:>2}: точность {ok/tot:.3f}, сбалансированная {bal:.3f}  " +
              " ".join(f"{c}:{per.get(c, 0):.2f}" for c in classes))
        if bal > best:
            best, best_state = bal, {k: v.cpu().clone() for k, v in net.state_dict().items()}
            best_conf = dict(conf)

    args.out.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": best_state, "classes": classes, "arch": args.arch},
               args.out / f"crop_cls_{args.arch}.pt")
    print(f"\nлучшая сбалансированная точность: {best:.3f}")
    print("матрица ошибок (истина -> предсказание):")
    for (t, p), n in sorted(best_conf.items(), key=lambda kv: -kv[1]):
        mark = "" if t == p else "   <-"
        print(f"  {t:<14} -> {p:<14}{n}{mark}")
    (args.out / f"crop_cls_{args.arch}.json").write_text(
        json.dumps({"classes": classes, "balanced_acc": best,
                    "confusion": {f"{t}->{p}": n for (t, p), n in best_conf.items()}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    main()
