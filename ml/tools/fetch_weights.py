"""загрузка весов детектора из приватного репозитория HuggingFace.

Веса в git не хранятся: 42 МБ, а `.gitignore` исключает `*.pt`. На новой машине
и на сервере их надо откуда-то взять — отсюда.

Репозиторий приватный: снимки организаторов и всё производное от них не должны
быть публичными (D-005). Нужен токен с правом чтения — переменная окружения
`HF_TOKEN` либо строка в `ml/.env`.

    python tools/fetch_weights.py              # PyTorch-версия, 42 МБ
    python tools/fetch_weights.py --onnx       # ONNX, 78 МБ, без ultralytics в рантайме
"""

import argparse, os
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
REPO = "Gatarez/lct7-construction-detector"


def token() -> str:
    """Токен из окружения либо из ml/.env. В git .env не попадает."""
    tok = os.environ.get("HF_TOKEN")
    if tok:
        return tok
    env = ML / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("HF_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(
        "нет токена HuggingFace: положите HF_TOKEN=... в ml/.env или в переменные окружения.\n"
        "Репозиторий приватный, без токена веса не скачать.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--onnx", action="store_true", help="взять ONNX вместо PyTorch")
    ap.add_argument("--out", type=Path, default=ML / "weights")
    args = ap.parse_args()

    from huggingface_hub import hf_hub_download

    name = "mocs_m_best.onnx" if args.onnx else "mocs_m_best.pt"
    args.out.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(repo_id=args.repo, filename=name, token=token(),
                           local_dir=str(args.out))
    size = Path(path).stat().st_size / 1048576
    print(f"скачано: {path} ({size:.0f} МБ)")
    print("описание модели и ограничения: docs/MODEL_CARD.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
