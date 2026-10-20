"""Заливка трёх демо-объектов на стенд через API (как на стенде clean-mvp).

    uv run --no-project --with httpx python deploy/demo/load_demo.py \\
        --api https://<стенд>/api --login <логин> --password <пароль> \\
        --data ~/Desktop/demo/Демо-объекты [--only 123] [--replace]

Данные — папка «Демо-объекты» (кадры организаторов в git не входят):
  1 · Спорткомплекс · Березники · 4 камеры/   график .xlsx, cam01…cam05 · <название>/*.jpg
  2 · Жилой дом · демо по кадрам организаторов/   график.csv, кадры.csv, cam01 · …/
  3 · Жилой дом с подземной автостоянкой · Москва/   график.csv, кадры.csv, фотоотчёт/

Кадры уходят пачками по 50, дальше их обрабатывает фоновая очередь стенда: скрипт ждёт,
пока она опустеет, и печатает итог по объекту. Березники (904 кадра) обрабатываются около
получаса — упор в ML. --replace удаляет объекты с теми же именами перед заливкой.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import httpx

# Рабочие зоны камер — как на стенде clean-mvp
ZONES = {
    "Спорткомплекс · Березники": {
        "К-1 · вход и здание": [
            [0.1853, 0.125],
            [0.3906, 0.9792],
            [0.9755, 0.9733],
            [0.9822, 0.0089],
            [0.1987, 0.0208],
        ],
        "К-2 · склад и сети": [
            [0.0982, 0.4554],
            [0.5201, 0.1161],
            [0.9152, 0.0804],
            [0.9866, 0.0833],
            [0.9933, 0.9852],
            [0.1563, 0.9852],
        ],
        "К-4 · земляные работы": [
            [0.1183, 0.7679],
            [0.0134, 0.3214],
            [0.0268, 0.0298],
            [0.9643, 0.0566],
            [0.9732, 0.9792],
            [0.1875, 0.9078],
        ],
    },
    "Жилой дом · демо": {
        "К-1 · котлован": [[0.05, 0.35], [0.95, 0.35], [0.95, 0.98], [0.05, 0.98]]
    },
}
NAMES = {
    "1": "Спорткомплекс · Березники",
    "2": "Жилой дом · демо",
    "3": "Жилой дом с подземной автостоянкой",
}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--api", default="http://localhost/api")
    ap.add_argument("--login", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument(
        "--data", type=Path, default=Path.home() / "Desktop/demo/Демо-объекты"
    )
    ap.add_argument(
        "--only",
        default="123",
        help="какие объекты: 1 — Березники, 2 — демо, 3 — Москва",
    )
    ap.add_argument(
        "--replace", action="store_true", help="удалить объекты с теми же именами"
    )
    args = ap.parse_args()

    api = httpx.Client(base_url=args.api, timeout=900)
    r = api.post("/auth/login", json={"login": args.login, "password": args.password})
    r.raise_for_status()
    api.headers["authorization"] = f"Bearer {r.json()['access_token']}"

    def ok(r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            print("  !!", r.request.method, r.request.url, r.status_code, r.text[:300])
            r.raise_for_status()
        return r

    existing = {s["name"]: s["id"] for s in ok(api.get("/sites")).json()}
    for key in args.only:
        name = NAMES[key]
        if name in existing:
            if not args.replace:
                sys.exit(
                    f"Объект «{name}» уже есть: --replace удалит его перед заливкой"
                )
            ok(api.delete(f"/sites/{existing[name]}"))
            print("удалён", name)

    def site(
        name: str, address: str, object_type: str, workdays: list[int], schedule: Path
    ) -> str:
        sid = ok(
            api.post(
                "/sites",
                json={
                    "name": name,
                    "address": address,
                    "object_type": object_type,
                    "workdays": workdays,
                },
            )
        ).json()["id"]
        mime = (
            "text/csv"
            if schedule.suffix == ".csv"
            else ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        )
        rep = ok(
            api.post(
                f"/sites/{sid}/schedule/import",
                files={"file": (schedule.name, schedule.read_bytes(), mime)},
                data={"mode": "builtin"},
            )
        ).json()
        print(
            f"  график: этапов {len(rep['stages'])}, замечаний {len(rep.get('issues', []))}"
        )
        ok(api.get(f"/sites/{sid}/methodology"))
        print(
            "  базовые комплекты:",
            ok(api.post(f"/sites/{sid}/methodology/apply-defaults")).json(),
        )
        return sid

    def camera(sid: str, site_name: str, name: str) -> str:
        body: dict = {"name": name}
        if zone := ZONES.get(site_name, {}).get(name):
            body["zone"] = zone
            # «К-1 · вход и здание» → зона «Вход и здание»
            if " · " in name:
                label = name.split(" · ", 1)[1]
                body["zone_name"] = label[:1].upper() + label[1:]
        return ok(api.post(f"/sites/{sid}/cameras", json=body)).json()["id"]

    def upload(sid: str, cam: str, paths: list[Path]) -> dict[str, dict]:
        ids: dict[str, dict] = {}
        for i in range(0, len(paths), 50):
            files = [
                (
                    "files",
                    (
                        p.name,
                        p.read_bytes(),
                        "image/png" if p.suffix == ".png" else "image/jpeg",
                    ),
                )
                for p in paths[i : i + 50]
            ]
            rep = ok(
                api.post(f"/sites/{sid}/photos", data={"camera_id": cam}, files=files)
            ).json()
            for it in rep["items"]:
                if it.get("photo"):
                    ids[it["filename"]] = it["photo"]
                elif it.get("error"):
                    print("    ошибка", it["filename"], it["error"])
        return ids

    def wait_queue(sid: str) -> None:
        t = time.time()
        while True:
            p = ok(api.get(f"/sites/{sid}/photos/progress")).json()
            left = p["queued"] + p["processing"]
            if left == 0:
                break
            print(
                f"    обработка: осталось {left} (+{time.time() - t:.0f} с)", end="\r"
            )
            time.sleep(5)
        time.sleep(
            5
        )  # закрытие пачек и пересчёт объекта идут сразу за последним кадром
        print(f"    обработка закончена за {time.time() - t:.0f} с" + " " * 20)

    def summary(sid: str) -> None:
        sm = ok(api.get(f"/sites/{sid}/assessment/summary")).json()
        print(
            "  итог:",
            sm["verdict"],
            sm["delay_days_min"],
            sm["delay_days_max"],
            "|",
            sm.get("reason"),
        )
        for d in ok(api.get(f"/sites/{sid}/assessment/deviations")).json():
            print(f"    {d['severity']:9} {d.get('title') or d['type']}")

    def manual_dates(
        sid: str, ids: dict[str, dict], rows: list[dict], column: str
    ) -> None:
        for row in rows:
            if row["файл"] in ids:
                ok(
                    api.patch(
                        f"/sites/{sid}/photos/{ids[row['файл']]['id']}/date",
                        json={"captured_on": row[column]},
                    )
                )

    root: Path = args.data
    if "2" in args.only:
        d = root / "2 · Жилой дом · демо по кадрам организаторов"
        print("== Жилой дом · демо")
        sid = site(
            NAMES["2"],
            "г. Москва · демонстрационный объект",
            "housing",
            [0, 1, 2, 3, 4],
            d / "график.csv",
        )
        rows = list(
            csv.DictReader(
                (d / "кадры.csv").read_text(encoding="utf-8").splitlines(),
                delimiter=";",
            )
        )
        for folder, cam_name in (
            ("cam01 · котлован", "К-1 · котлован"),
            ("cam02 · свайное поле", "К-2 · свайное поле"),
        ):
            cid = camera(sid, NAMES["2"], cam_name)
            mine = [r for r in rows if r["камера"] == folder]
            ids = upload(sid, cid, [d / folder / r["файл"] for r in mine])
            wait_queue(sid)
            manual_dates(sid, ids, mine, "дата")
        summary(sid)
    if "3" in args.only:
        d = root / "3 · Жилой дом с подземной автостоянкой · Москва"
        print("== Москва")
        sid = site(
            NAMES["3"],
            "г. Москва, ЮЗАО, Обручевский район",
            "housing",
            [0, 1, 2, 3, 4],
            d / "график.csv",
        )
        cid = camera(sid, NAMES["3"], "Фотоотчёт")
        rows = list(
            csv.DictReader(
                (d / "кадры.csv").read_text(encoding="utf-8").splitlines(),
                delimiter=";",
            )
        )
        folder = d / "фотоотчёт"
        ids = upload(sid, cid, [next(folder.rglob(r["файл"])) for r in rows])
        wait_queue(sid)
        manual_dates(sid, ids, rows, "дата съёмки (по подписи на снимке)")
        summary(sid)
    if "1" in args.only:
        d = root / "1 · Спорткомплекс · Березники · 4 камеры"
        print("== Березники")
        sid = site(
            NAMES["1"],
            "г. Березники · универсальный спортивный комплекс",
            "education",
            [0, 1, 2, 3, 4],
            next(d.glob("*.xlsx")),
        )
        # Как инженер на стенде clean-mvp: благоустройство вне обзора камер; «30.02.2027» у
        # каркаса в файле не дата — плановое начало каркаса 15.08.2026
        for rule in ok(api.get(f"/sites/{sid}/methodology")).json():
            if rule["stage_name"] and re.search(
                "благоустройству|Вертикальная планировка", rule["stage_name"]
            ):
                ok(
                    api.patch(
                        f"/sites/{sid}/methodology/rules/{rule['id']}",
                        json={
                            "is_verifiable": False,
                            "unverifiable_reason": "Вне обзора камер объекта",
                        },
                    )
                )
        stage = next(
            x
            for x in ok(api.get(f"/sites/{sid}/schedule")).json()["stages"]
            if "несущих" in x["name"]
        )
        ok(
            api.patch(
                f"/sites/{sid}/schedule/stages/{stage['id']}",
                json={"planned_start": "2026-08-15"},
            )
        )
        for camdir in sorted(
            p for p in d.iterdir() if p.is_dir() and p.name.startswith("cam")
        ):
            m = re.match(r"cam0*(\d+)\s*·?\s*(.*)", camdir.name)
            assert m, camdir.name
            cid = camera(sid, NAMES["1"], f"К-{m.group(1)} · {m.group(2)}")
            print(
                f"  {camdir.name}: {len(upload(sid, cid, sorted(camdir.glob('*.jpg'))))} отправлено"
            )
        wait_queue(sid)
        summary(sid)


if __name__ == "__main__":
    main()
