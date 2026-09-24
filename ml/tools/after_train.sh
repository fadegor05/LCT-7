#!/bin/sh
# ждёт конца обучения и считает обе метрики; результат в runs/<имя>_report.txt
# нужен, потому что Claude выполняет шаги только когда с ним говорят, а прогон идёт часами
NAME="${1:-mocs_mix}"
cd "D:/ML/ЛЦТ/ml" || exit 1
P="D:/ML/ЛЦТ/.venv/Scripts/python.exe"
export PYTHONIOENCODING=utf-8
OUT="runs/${NAME}_report.txt"

echo "жду конца обучения $NAME..." > "$OUT"
while ! tr -d '\000' < "runs/$NAME.log" | grep -aqE "epochs completed|Traceback|CUDA out of memory"; do
  sleep 60
done
tr -d '\000' < "runs/$NAME.log" | grep -aE "EarlyStopping: |epochs completed" | tail -2 >> "$OUT"

cp "runs/$NAME/weights/best.pt" "weights/${NAME}_best.pt" || exit 1
echo "--- прогон по всем кадрам" >> "$OUT"
$P tools/detect_finetuned.py "data/raw/dataset/images/Строительная_техника" \
   --weights "weights/${NAME}_best.pt" --out "data/processed/detections_${NAME}.json" 2>&1 | tail -3 >> "$OUT"

echo "--- сравнение на p03+p08" >> "$OUT"
$P - "$NAME" >> "$OUT" 2>&1 <<'PYEOF'
import sys; sys.path.insert(0,"tools")
from eval_groups import load_gt, evaluate, dets_from_json
name=sys.argv[1]; gt=load_gt({"p03","p08"})
print(f"{'модель':<22}{'mAP50':>7}{'P':>6}{'R':>6}{'F0.5':>7} | бурение AP/P/R | башкран AP/R")
for tag,f in [("прежняя (full_x)","detections_full_x.json"),(name,f"detections_{name}.json")]:
    r=evaluate(dets_from_json("data/processed/"+f), gt)
    d=r["groups"].get("drilling",{}); t=r["groups"].get("tower_crane",{})
    print(f"{tag:<22}{r['map50']:>7.3f}{r['precision']:>6.2f}{r['recall']:>6.2f}{r['f05']:>7.2f} | "
          f"{d.get('ap50',0):.3f} {d.get('p',0):.2f} {d.get('r',0):.2f} | {t.get('ap50',0):.3f} {t.get('r',0):.2f}")
PYEOF

echo "--- статусы этапов" >> "$OUT"
$P - "$NAME" >> "$OUT" 2>&1 <<'PYEOF'
import json,subprocess,sys
name=sys.argv[1]; P=r"D:/ML/ЛЦТ/.venv/Scripts/python.exe"
def st(p):
    d=json.load(open(p,encoding="utf-8")); s=d["sites"] if "sites" in d else d
    return {(x["site_id"],g["stage_code"]):g["status"] for x in s for g in x["stages"]}
def chain(det,conf,tag):
    subprocess.run([P,"tools/site_state.py","--detections",det,"--conf",str(conf),"--out",f"data/processed/_a{tag}.json"],capture_output=True)
    subprocess.run([P,"tools/match_schedule.py","--state",f"data/processed/_a{tag}.json","-o",f"data/processed/_b{tag}.json"],capture_output=True)
    return st(f"data/processed/_b{tag}.json")
o=chain("data/processed/detections_oracle.json",0.01,"o")
for tag,f in (("прежняя","detections_full_x.json"),(name,f"detections_{name}.json")):
    for conf in (0.25,0.4,0.5):
        m=chain("data/processed/"+f,conf,"m"); keys=sorted(set(o)|set(m))
        print(f"{tag:<10} conf {conf}: {sum(1 for k in keys if o.get(k)==m.get(k))}/{len(keys)}")
PYEOF
echo "=== ГОТОВО" >> "$OUT"
