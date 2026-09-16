# PART K — Модели и инструменты для первых экспериментов
_статус: done (2026-09-15); источников: 70; подтверждено: 56 (первоисточник открыт и прочитан, ✔), 14 — поисковые сниппеты/сторонние разборы (помечены «сниппет»)_

> Правило: цифры/лицензии взяты из первоисточников (README, model card, arXiv, docs), ссылки в колонке «Источник» → список источников в конце файла. `[UNVERIFIED]` — не подтверждено первоисточником. `[HYP]` — гипотеза команды, проверять в экспериментах.

## Блок 1. Open-vocabulary детекторы

| Модель | Веса открыты | Лицензия | Zero-shot качество | Скорость | Fine-grained по тексту | Риск | Источник |
|---|---|---|---|---|---|---|---|
| Grounding DINO 1.0 (T/B) | Да (Swin-T, Swin-B) | Apache-2.0 | COCO zero-shot 48.4 AP (T); LVIS minival 28.8 AP (T, по замеру MMDet) | CPU ~1.85 с/изобр. (i9, OpenCV DNN / ORT, размер входа не указан) | Слабое на редких классах (LVIS 28.8), но лучший из zero-shot в индустриальном бенчмарке [частично UNVERIFIED] | Медленный на CPU; сборка CUDA-расширения (`_C`) капризна | S3, S4, S18, S20 |
| MM-Grounding-DINO-T (OpenMMLab) | Да | Apache-2.0 (mmdetection) [лицензию страницы конфигов не видно — UNVERIFIED для весов] | COCO 50.4; LVIS minival 41.4; ODinW13 53.3 / ODinW35 28.4 | как GD-T (та же архитектура) [HYP] | Лучше GD 1.0 на LVIS (+12.6 AP) | Тяжёлый стек mmdet/mmcv на Windows | S4 |
| Grounding DINO 1.5 / 1.6 Pro, Edge | **Нет — только API** (DeepDataSpace, токен) | Apache-2.0 только на код API-клиента | 1.5 Pro: COCO 54.3, LVIS-minival 55.7, LVIS-val 47.6, ODinW35 30.2; 1.6 Pro: COCO 55.4, LVIS-minival 57.7 | облако | высокое на LVIS rare (56.1) | Облако = снимки уходят наружу; платные квоты; нельзя положить в открытый репо | S1, S21 |
| «Grounding DINO 2.0» | **Не найдено** такого релиза | — | — | — | — | Не существует как публичный релиз (на 09.2026 не найден) | S21, S23 |
| DINO-X Pro / Edge (+ T-Rex2) | **Нет — только API** | Apache-2.0 только на код API | Pro: COCO 56.0, LVIS-minival 59.7 (rare 63.3), LVIS-val 52.4; Edge: LVIS 42.0 | облако | лучший LVIS rare среди найденных | То же, что GD1.5: облако, квоты, закрыто | S2, S23 |
| OWLv2 (B/16, L/14) | Да (HF `google/owlv2-*`) | Apache-2.0 | L/14: LVIS rare 44.6 AP (self-training OWL-ST); B/16 ~0.2B | CPU ~1.07 с/изобр. (i9, OpenCV DNN) | Хорош на редких LVIS; на индустриальных данных уступил GD [частично UNVERIFIED] | Model card: «research output»; вход 960×960 → мелкие объекты на 1200×810 теряются [HYP] | S11, S12, S18 |
| YOLO-World v2.1 (S…X) | Да | **GPL-3.0** (оригинал AILab-CVC); в Ultralytics — AGPL-3.0 | LVIS AP: S 18.5 / M 24.1 / L 26.8 / X 28.6 (640) | Real-time на GPU; ONNX/TFLite INT8 экспорт | Слабее всех на редких классах | Лицензия copyleft; качество zero-shot низкое | S10 |
| YOLOE (v8/11/**26**) | Да | **AGPL-3.0** (THU-MIG + Ultralytics) | LVIS minival: 11-L 35.2 (APr 29.1); v8-L 35.9; **26x 40.6** (text) / 38.5 (visual); 26n 24.7 | T4: 11-S 301 FPS, 11-L 130 FPS; iPhone 11-S 73 FPS; экспорт ONNX/OpenVINO с «запечёнными» классами | Средне; есть **visual prompt** (дать 1–2 примера бокса буровой) — ключевая фича для fine-grained | AGPL; после `set_classes()` классы фиксированы в экспорте | S8, S9 |
| Florence-2 (base 0.23B / large 0.77B) | Да | **MIT** | COCO zero-shot 37.5 mAP (large); ft 43.4 | лёгкий, но генеративный (seq2seq) [скорость CPU UNVERIFIED] | `<CAPTION_TO_PHRASE_GROUNDING>`, `<OD>`; нет confidence score у боксов [UNVERIFIED] | `trust_remote_code=True`; нет скоров → сложно ставить порог | S13 |
| SAM 3 (0.85–0.9B) / SAM 3.1 (27.03.2026) | Да, **gated** HF (запрос доступа) | **SAM License** (кастомная Meta: royalty-free, коммерция разрешена, но: запрет reverse engineering, экспорт-контроль, Meta может менять условия) | LVIS box 48.5 / mask 52.4; COCO box 56.4; ODinW13 10-shot 71.8 | 30 мс/изобр. на **H200** (100+ объектов); CPU не заявлен, требует CUDA 12.6 | Детекция по тексту — **да** (все экземпляры по noun phrase). Авторы: «atomic visual concepts», не для длинных выражений/рассуждений → нужен SAM 3 Agent + MLLM | Тяжёлый для ноутбука без GPU; gated веса; не OSI-лицензия | S5, S6, S7, S22 |
| Qwen3-VL (2B/4B/8B/32B, 30B-A3B, 235B-A22B) | Да | Apache-2.0 | Grounding боксами/точками (относительные координаты); цифр ODinW/COCO в README нет [UNVERIFIED] | 2B/4B — десятки секунд на CPU [UNVERIFIED] | Лучше всех понимает описания («машина с мачтой и шнеком на гусеницах») [HYP]; в RF100-VL Qwen2.5-VL <2% на мед. доменах | Низкий recall и дубли на плотных сценах (известная проблема MLLM-детекции, мотивация Rex-Omni) | S14, S16, S17 |
| Rex-Omni (3B, на Qwen2.5-VL-3B) | Да (HF, AWQ-версия) | **IDEA License 1.0 + Qwen RESEARCH LICENSE** (база) → риск некоммерческих ограничений | Заявлено ≈/выше GD и DINO на COCO/LVIS zero-shot (CVPR 2026) [цифры не извлечены — UNVERIFIED] | GPU/vLLM | Сильная MLLM-детекция по тексту [HYP] | Research-лицензия базы; нужен GPU | S15, S16 |

### Карточки

**K01. Grounding DINO 1.0 / MM-Grounding-DINO** — единственная *открытая* ветка Grounding DINO. Версии 1.5/1.6/DINO-X — только API, «2.0» не существует. MM-GDINO-T заметно лучше оригинала на LVIS (41.4 vs 28.8), что важно для длинного хвоста классов техники. Для псевдоразметки 100–300 кадров скорость 1–2 с/кадр на CPU приемлема (офлайн). Промпт — классы через « . ».

**K02. GD 1.5/1.6, DINO-X, T-Rex2 (IDEA, API)** — топ zero-shot качество (DINO-X Pro LVIS rare 63.3), но только облако DeepDataSpace. Для открытого репо и демо без интернета не годится; допустимо разве что как «оракул» для разовой проверки качества псевдоразметки (если команда согласна отправлять снимки в Китай — вопрос приватности).

**K03. OWLv2** — Apache-2.0, в `transformers` из коробки, ~1 с/кадр CPU. Сильный на редких классах LVIS. Подходит как второй «голос» в ансамбле псевдоразметки (GD + OWLv2 → WBF).

**K04. YOLO-World v2.1** — самый быстрый из «старых» OVD, но LVIS AP ≤ 28.6 и GPL-3.0. Практически вытеснен YOLOE.

**K05. YOLOE / YOLOE-26** — лучший вариант «zero-shot baseline, который реально работает в реальном времени на CPU»: text/visual/prompt-free (словарь 4585 имён), экспорт в ONNX/OpenVINO. YOLOE-26x даёт 40.6 LVIS AP. Visual prompt позволяет отличать буровую установку от гусеничного крана по 1–3 примерам-боксам. Лицензия AGPL-3.0 (для открытого репо — ок, см. Блок 2).

**K06. Florence-2** — MIT, маленький, мультизадачный (детекция + phrase grounding + OCR в одной модели → может закрыть и OCR даты). COCO zero-shot 37.5. Минус: генеративный вывод без скоров, `trust_remote_code`.

**K07. SAM 3 / 3.1** — вышел 19.11.2025, **умеет детекцию по тексту** (все экземпляры концепта, боксы+маски), COCO box 56.4, LVIS box 48.5. Минусы для нас: 0.85–0.9B параметров, требует CUDA, gated веса, кастомная лицензия. Хорош как офлайн-разметчик на GPU (Colab/Kaggle), не как CPU-демо.

**K08. VLM (Qwen3-VL, Rex-Omni)** — Qwen3-VL (Apache-2.0, 2B–235B, окт. 2025) выдаёт боксы по сложным описаниям, но MLLM-детекция страдает низким recall/дубликатами на многообъектных сценах (прямо указано как мотивация Rex-Omni). Rex-Omni (3B, CVPR 2026) это исправляет, но база под Qwen Research License. Роль: *верификатор* спорных fine-grained боксов (crop → «это буровая установка или гусеничный кран?»), а не основной детектор.

**K09. Общая проблема zero-shot** — RF100-VL (NeurIPS 2025): GroundingDINO и Qwen2.5-VL <2% на сложных доменах; решение — few-shot/инструкции с визуальными примерами. Индустриальный бенчмарк (подземные шахты, MDPI Sensors 2026): fine-tuned YOLO (AP50 0.88–0.91, лучший YOLO26s) «существенно» обходит zero-shot OVD (YOLO-World, GD, OWL-ViT, OWLv2) [точные zero-shot цифры не извлечены — страница 403]. OVD нестабильны при искажениях/сдвиге домена (COCO-O/-C/-DC) — снег, дымка, дрон. → Zero-shot годится как псевдоразметка + ручная правка, но не как финальная модель.

**K10. Fine-grained по тексту (буровая vs гусеничный кран, автокран vs кран-манипулятор)** — ни в одном источнике прямых замеров на этих классах нет → `[HYP]`: CLIP-подобные текстовые энкодеры (OWLv2, YOLO-World/YOLOE, GD) плохо различают узкоспециальные термины; ожидаемо лучше работают (а) visual prompts YOLOE/T-Rex-подобные, (b) описательные промпты («crawler crane with lattice boom», «drilling rig with vertical mast»), (c) VLM-верификация кропов. Проверить в E1 на 20–30 кадрах.

## Блок 2. Компактные детекторы

**Какая версия Ultralytics последняя (на 15.09.2026):** YOLO26 (январь 2026) — актуальная стабильная линейка; пакет `ultralytics` v8.4.152 (14.09.2026). **YOLO27 НЕ выпущен**: есть страница-превью, но «weights, package support, and a launch date are not currently available» (S27, S28). YOLOE-26 и поддержка SAM 3.1 уже в пакете.

| Модель | Версия/дата | COCO mAP50-95 | CPU latency | Лицензия | Fine-tune | Комментарий | Источник |
|---|---|---|---|---|---|---|---|
| **Ultralytics YOLO26** n/s/m/l/x | янв. 2026; пакет 8.4.152 (14.09.2026) | 40.9 / 48.6 / 53.1 / 55.0 / 57.5 | **CPU ONNX: 38.9 / 87.2 / 220 / 286 / 526 мс** (640 px, офиц. таблица); «до 43% быстрее YOLO11n на CPU» | **AGPL-3.0** / Enterprise | Самый простой: YOLO-txt, `yolo train`, экспорт ONNX/OpenVINO одной командой | NMS-free end-to-end, без DFL, STAL (small-target-aware assignment) — полезно для мелкой техники | S24, S25, S28 |
| Ultralytics YOLO11 | 2024 (предыдущее поколение) | — [не извлекалось] | медленнее YOLO26n на CPU до 43% (заявление Ultralytics) | AGPL-3.0 | как YOLO26 | Смысла брать вместо YOLO26 нет, кроме совместимости | S24 |
| **RF-DETR** N/S/M/L (XL/2XL) | пакет `rfdetr` **1.10.1 (07.09.2026)** | N 48.4 (384px) / S 53.0 (512) / M 54.7 (576) / L 56.5 (704); XL 58.6; 2XL 60.1 | **Офиц. CPU-цифр нет** (T4 TRT FP16: N 2.3 мс … L 6.8 мс). 30M+ параметров ViT → на CPU заметно тяжелее YOLO26n/s [частично UNVERIFIED] | **Apache-2.0: N–L + все seg**; **XL/2XL — PML 1.0** (не открытая) | COCO-формат, pip-пакет; DINOv2-бэкбон хорошо переносится на малые датасеты; RF100-VL L: 61.2 AP50:95 | Лучший «разрешительный» кандидат по качеству; для <1000 кадров DETR с DINOv2 обычно выигрывает у CNN [HYP] | S26, S39, S41 |
| **D-FINE** N/S/M/L/X | послед. релиз 07.11.2024 | 42.8 / 48.5 / 52.3 / 54.0 / 55.8 (+ O365-претрен) | нет офиц. CPU; экспорт **ONNX / TensorRT / OpenVINO** | Apache-2.0 | COCO-формат, конфиги, `remap_mscoco_category=False` | Стабильная база DEIM; меньше «удобств», чем Ultralytics | S29 |
| **DEIM** (D-FINE / RT-DETRv2) | CVPR 2025 | DEIM-D-FINE N 43.0 / S 49.0 / M 52.7 / L 54.7 / X 56.5 | как D-FINE | Apache-2.0 | COCO-формат; быстрее сходится (меньше эпох) | Хорош для короткого дедлайна | S37 |
| **DEIMv2** Atto…X (DINOv3) | 26.09.2025 | Atto 23.8 / Pico 38.5 / N 43.0 / S 50.9 / M 53.0 / L 56.0 / X 57.8 | нет CPU; ONNX-экспорт; Pico 1.5M парам. | **Смешанная**: README — «DEIMv2 License» + коммерция по запросу (LICENSE-файл 404); по сторонним разборам размеры < S (HGNetv2) — Apache-2.0, **S/M/L/X — дополнительно DINOv3 License** (Meta, не OSI, запрет военного/ITAR — S62) → `[частично UNVERIFIED]` | COCO-формат | Лучший AP на параметр; лицензия S–X осложнена DINOv3 | S30, S62, S69 |
| **RT-DETRv2** S/M/L/X | 24.07.2024 | 48.1 / 51.9 / 53.4 / 54.3 | OpenCV-бенчмарк «RT-DETR» на i9: ~100 мс ORT (вариант/вход не указаны) | Apache-2.0 | COCO-формат; также есть в Ultralytics (AGPL-обёртка!) и HF transformers | Зрелый, много туториалов | S31, S18 |
| **RT-DETRv4** S/M/L/X | код+веса 17.11.2025; ECCV 2026 | 49.8 / 53.7 / 55.4 / 57.0 | T4: 3.66 / 5.91 / 8.07 / 12.9 мс; CPU нет | Apache-2.0 | COCO-формат; для обучения нужен DINOv3-учитель (конфиг путей) | Инференс = обычный RT-DETR (учитель только в обучении — по смыслу дистилляции, в README явно не сказано [UNVERIFIED]) | S38 |
| **YOLOX** Nano…X | активн. разработка ~2022–2023 | Nano 25.8 / Tiny 32.8 (416) / S 40.5 / M 46.9 / L 49.7 / X 51.1 | нативные демо **OpenVINO / ONNX / ncnn** | Apache-2.0 | Туториал custom-датасета, VOC/COCO | Устарел по точности, но «чистая» лицензия и CPU-деплой | S32 |
| **PP-YOLOE+** s/m/l/x | PaddleDetection 2.8 | 43.7 / 49.8 / 52.9 / 54.7 | V100/TRT FPS; ONNX только batch=1; OpenVINO через туториал | Apache-2.0 | Экосистема Paddle (отдельный фреймворк) | Лишний стек для команды на PyTorch | S33 |
| **LibreYOLO** (обёртка) | 2026, `pip install libreyolo` | — (реимплементации YOLOX, YOLOv9, RF-DETR, D-FINE, RTMDet…) | — | **MIT, «No AGPL anywhere»** (заявление сайта) | единый API train/val | Молодой проект; зрелость `[UNVERIFIED]` | S40 |

**CPU-бенчмарки (независимые):** OpenCV 5 DNN wiki (06.2026, Intel i9, ORT 1.25.1): YOLOv8 ~13 мс, YOLOv5 ~8.7 мс, RT-DETR ~100 мс, OWLv2 ~1.5 с, Grounding DINO ~1.86 с (размеры входа не указаны) — порядок разницы CNN-YOLO vs DETR vs OVD ≈ 1 : 8 : 150 (S18). Сторонние сравнения: «RF-DETR не публикует CPU-латентность» (S41).

**Расчёт для наших снимков (1200×810)** `[расчёт, не замер]`: латентность ∝ пикселям входа. imgsz 640→1280 ≈ ×4 FLOPs. YOLO26s@640 87 мс → @1280 ≈ 350 мс на CPU той же машины; YOLO26n@1280 ≈ 150 мс.

### SAHI / slicing для мелких объектов
- SAHI: **MIT**, поддерживает Ultralytics (YOLO26/11/YOLOE), HF (RT-DETR, GroundingDINO), RF-DETR, MMDet, Detectron2, TorchVision (S34, S36).
- Прирост (ICIP 2022, VisDrone/xView — аэро-снимки): slicing-инференс **+6.8 / +5.1 / +5.3 AP** (FCOS/VFNet/TOOD); со slicing-aided fine-tune — **+12.7 / +13.4 / +14.5 AP** кумулятивно (S35).
- Цена: число прямых проходов = число тайлов (+1 при full-image). `[расчёт]` 1200×810, тайл 640, overlap 0.2 → 2×2 = 4 тайла + полный кадр = **~5× латентность** + merge (NMS/NMM). Альтернатива дешевле: один проход на imgsz 1280 (≈4× FLOPs, без склейки).
- `[HYP]` Для наших кадров (техника обычно 50–400 px) SAHI полезен на дроновых/дальних кадрах; включать условно (по доле мелких боксов) — даёт аргумент «скорость» жюри.

### Лицензия AGPL-3.0 (Ultralytics) — последствия для открытого репо
1. Ultralytics прямо: AGPL подходит, если «comfortable open-sourcing your entire project under AGPL-3.0»; хакатон/«build in public» — легитимный кейс (S25).
2. **Обученные веса по позиции Ultralytics тоже под AGPL-3.0** («covers the training code and the models produced») (S25) — юридически спорно, но исходить надо из этого.
3. Сетевое использование (SaaS/API/веб-демо) = распространение по AGPL §13 → пользователям сервиса нужно давать исходники. Открытый репо это покрывает.
4. **Практическое следствие:** если в репо `import ultralytics` (включая YOLOE, RT-DETR-обёртку, SAM через ultralytics), лицензия всего репо должна быть AGPL-3.0-совместимой; поставить MIT/Apache на весь репо некорректно. Если заказчик (город/подрядчик) захочет закрытое внедрение — нужна Enterprise-лицензия или переобучение на Apache-модели.
5. Mitigation: держать детектор за интерфейсом `Detector` (модульность — критерий жюри) и иметь Apache-альтернативу (RF-DETR N–L, D-FINE/DEIM, RT-DETRv2/v4, YOLOX) — переключение конфигом.

### Источники Блока 2 (дополнительно к S18, S24–S27)
- S28 Ultralytics releases (v8.4.143–152, сент. 2026; YOLO27 не выпущен) — https://github.com/ultralytics/ultralytics/releases ✔
- S29 Peterande/D-FINE — https://github.com/Peterande/D-FINE ✔
- S30 Intellindust-AI-Lab/DEIMv2 — https://github.com/Intellindust-AI-Lab/DEIMv2 ✔ (LICENSE-файл 404)
- S31 lyuwenyu/RT-DETR (v2) — https://github.com/lyuwenyu/RT-DETR ✔
- S32 Megvii-BaseDetection/YOLOX — https://github.com/Megvii-BaseDetection/YOLOX ✔
- S33 PaddleDetection PP-YOLOE README — https://github.com/PaddlePaddle/PaddleDetection/blob/release/2.8/configs/ppyoloe/README.md ✔
- S34 obss/sahi — https://github.com/obss/sahi ✔
- S35 SAHI paper arXiv 2202.06934 — https://arxiv.org/abs/2202.06934 ✔
- S36 SAHI LICENSE (MIT) — https://raw.githubusercontent.com/obss/sahi/main/LICENSE ✔
- S37 ShihuaHuang95/DEIM — https://github.com/ShihuaHuang95/DEIM ✔
- S38 RT-DETRs/RT-DETRv4 — https://github.com/RT-DETRs/RT-DETRv4 ✔ (+ arXiv 2510.25257)
- S39 PyPI rfdetr 1.10.1 — https://pypi.org/project/rfdetr/ ✔
- S40 LibreYOLO — https://www.libreyolo.com/ ✔
- S41 Codersera «RF-DETR vs YOLO26» — https://codersera.com/blog/rf-detr-vs-yolo26-object-detection-comparison-2026/ (сниппет)
- S42 YOLO26 сторонний разбор arXiv 2509.25164 — https://arxiv.org/html/2509.25164v4 (сниппет)

## Блок 3. Разметка

| Инструмент | Версия/дата | Лицензия | Windows, без облака | Встроенная авторазметка | Экспорт bbox | Для 100–300 кадров | Риск | Источник |
|---|---|---|---|---|---|---|---|---|
| **X-AnyLabeling** | **v4.0.0 (05.08.2026)** | GPL-3.0 (сам инструмент; на наш код/разметку не распространяется, т.к. отдельное приложение) [юр. трактовка — HYP] | **Да**: готовый exe + `pip install x-anylabeling-cvhub`; локальный ONNX Runtime (CPU), TensorRT, OpenCV DNN; удалённо vLLM/SGLang | **Grounding DINO, YOLO-World, YOLOE, SAM/SAM2/SAM3, Florence-2, Qwen3-VL, RF-DETR, PaddleOCR**; batch-разметка всей папки | **YOLO, COCO**, VOC, DOTA, MOT, MASK, PPOCR, MMGD, VLM-R1, ShareGPT | **Самый быстрый путь**: текстовый промпт → батч по папке → ручная правка, всё в одном окне | Однопользовательский (нет ревью/ролей); качество промптов = качество zero-shot | S43 |
| **CVAT Community** | v2.74.0 (26.08.2026) [сниппет] | **MIT** | Только **Docker + WSL2** (Docker Desktop, Chrome — единственный поддерживаемый браузер); nuclio-функции для ИИ — отдельный compose | Community: nuclio-функции (SAM, IOG, YOLOv7, RetinaNet, Faster/Mask RCNN, TransT, SAM2 tracker); свои модели — nuclio (Docker). **Встроенная SAM2/SAM3 авторазметка и HF/Roboflow-интеграции — только Online/Enterprise** | **YOLO, Ultralytics YOLO (TXT/YAML), COCO**, VOC, KITTI и 20+ форматов | Хорош для 2–4 разметчиков параллельно и ревью; для 1 человека на ноутбуке избыточен | Тяжёлая установка на Windows (WSL2, nuclio), ~десятки минут настройки [HYP] | S44, S45, S46, S47 |
| **Label Studio** + ML backend | — (актуальная ветка develop) | Apache-2.0 (и LS, и ml-backend) | LS: `pip install label-studio` работает на Windows (иногда нужны wheel для lxml); **ML backend — через docker-compose** (на Windows проблема CRLF в `start.sh` → `core.autocrlf false`) | Примеры backend: **Grounding DINO, SAM 2, YOLO**, MMDetection, OCR (EasyOCR, PaddleOCR, Tesseract) | **COCO, YOLO**, Pascal VOC; координаты в % (нужна конвертация); картинки в экспорт не вшиваются | Гибко (active learning), но больше «сантехники», чем X-AnyLabeling | Докер для backend; экспорт без изображений | S48, S49, S50 |
| **Roboflow Annotate** | SaaS | Проприетарный сервис | **Нет — облако** | Auto-label (кредиты), SAM-подобные инструменты | YOLO/COCO и др. | Удобно, но **Public (бесплатный) план: «Data and models are open source on Roboflow Universe»**, скачивание весов недоступно; приватность — Core **$79/мес (годовая) / $99/мес**, 30–50 кредитов | Утечка снимков заказчика в публичный доступ; не соответствует «без облака» | S51 |

**Вывод по разметке (факты + `[HYP]`-оценки):**
1. Для 100–300 изображений, одного-двух ML-инженеров, Windows и без облака **X-AnyLabeling — наименьшее трение**: ставится exe, внутри уже есть GD/YOLOE/SAM3/Florence-2/Qwen3-VL, батч-авторазметка папки, экспорт в YOLO и COCO (S43).
2. Альтернатива «код-first»: собственный скрипт псевдоразметки (GD/MM-GDINO + OWLv2/YOLOE → WBF → YOLO-txt), затем импорт в X-AnyLabeling только для правки. Плюс: воспроизводимость в репо (жюри видит пайплайн), минус: +0.5 дня кода [HYP].
3. CVAT оправдан, если размечают 3+ человека параллельно; но SAM2/SAM3-авторазметка «из коробки» — платная (S45), а свои модели — через nuclio/Docker.
4. Roboflow бесплатно = публично (S51) → для снимков заказчика не использовать, либо только если данные уже открытые по условиям кейса `[проверить условия хакатона — UNVERIFIED]`.
5. `[HYP]` Ожидаемая скорость правки псевдоразметки: ~30–90 с на кадр с 5–10 объектами → 100 кадров ≈ 1–2.5 ч на человека; с нуля (без псевдоразметки) — в 2–3 раза дольше. Замерить на первых 20 кадрах.
6. Формат хранения «истины»: COCO JSON (подходит RF-DETR/D-FINE/DEIM/RT-DETR) + автоконвертация в YOLO-txt (Ultralytics); X-AnyLabeling и CVAT экспортируют оба.

### Источники Блока 3
- S43 CVHub520/X-AnyLabeling — https://github.com/CVHub520/X-AnyLabeling ✔
- S44 CVAT docs «AI models» — https://docs.cvat.ai/docs/annotation/auto-annotation/ai-models/ ✔
- S45 cvat-ai/cvat (MIT; SAM2/SAM3 авторазметка в Online/Enterprise) — https://github.com/cvat-ai/cvat ✔
- S46 CVAT Installation Guide (Windows: WSL2 + Docker Desktop + Chrome) — https://docs.cvat.ai/docs/administration/community/basics/installation/ (сниппет)
- S47 CVAT auto-annotation blog / версия 2.74.0 — https://www.cvat.ai/resources/blog/automated-data-labeling-in-cvat (сниппет)
- S48 HumanSignal/label-studio — https://github.com/HumanSignal/label-studio ✔
- S49 HumanSignal/label-studio-ml-backend — https://github.com/HumanSignal/label-studio-ml-backend ✔
- S50 Label Studio export formats — https://labelstud.io/guide/export ✔
- S51 Roboflow pricing — https://roboflow.com/pricing ✔

## Блок 4. OCR и группировка снимков

### 4.1 OCR вшитой даты (ДД.ММ.ГГГГ, цветной оверлей, обычно правый нижний угол)

| Движок | Версия/дата | Лицензия | CPU | Цифры на сложном фоне | Простота | Риск | Источник |
|---|---|---|---|---|---|---|---|
| **PaddleOCR / PP-OCRv6** (tiny 1.5M / small / medium 34.5M) | PaddleOCR **3.7.0 (11.06.2026)**; PP-OCRv6 вышел с 3.7 | Apache-2.0 | Xeon 8350C, полный пайплайн: **OpenVINO tiny 0.20 с / small 0.59 с / medium 1.40 с**; ORT 0.22 / 0.61 / 3.31 с. Есть режим «только распознавание» | Лучший из открытых по заявлениям: medium det Hmean 86.2, rec 83.2 (усреднение по бенчмарку PaddleOCR, не цифры на оверлеях); +4.6 det / +5.1 rec к PP-OCRv5_server; 50 языков вкл. латиницу | `pip`, Windows-гайд, ONNX/OpenVINO | Зависимость от paddlepaddle (или конвертация в ONNX); цифры бенчмарка — на документах/сценах, не на наших оверлеях | S52, S53, S54 |
| **EasyOCR** (CRAFT + CRNN) | 1.7.2 (24.09.2024) — редкие релизы | Apache-2.0 | `gpu=False`; ~0.7 с/стр. в стороннем сравнении | Средне [HYP]; allowlist-параметр в README не описан → `[UNVERIFIED]` | Очень простой API | 476 открытых issues, авто-закрытие через 6 мес. → слабая поддержка; ~500 МБ моделей (сниппет) | S55, S59 |
| **Tesseract 5.x** | 5.x | Apache-2.0 `[не открывал LICENSE — UNVERIFIED]` | Самый быстрый на CPU: ~0.45 с/стр. (стороннее сравнение) | **Плохо без препроцессинга**: документация требует бинаризацию, ~300 DPI; «большие поля вокруг одного слова/цифры создают проблемы»; `tessedit_char_whitelist` (цифры), `--psm 7` (одна строка) | Нужна обвязка (кроп, HSV-маска, масштаб) | Цветной текст на снегу/небе → ошибки бинаризации [HYP] | S58, S59 |
| **docTR / OnnxTR** (DBNet/FAST + CRNN/PARSeq/ViTSTR) | docTR 1.1.0; OnnxTR 0.9.0 | Apache-2.0 (оба) | **OnnxTR на i7-14700K: 0.25–0.57 с/стр., INT8 0.14–0.38 с** (docTR на PyTorch 0.60–1.29 с) | PARSeq — сильный scene-text распознаватель [HYP]; можно давать готовый кроп строки | Без PyTorch/TF (только ONNX Runtime: CPU/OpenVINO) | Меньше сообщества, чем у Paddle | S56, S57 |
| **VLM-OCR** (Florence-2 `<OCR>`/`<OCR_WITH_REGION>`, Qwen3-VL, PaddleOCR-VL 1.6) | Florence-2 (MIT); Qwen3-VL (Apache-2.0, OCR на 32 языках — сниппет); PaddleOCR-VL 1.6 | MIT / Apache-2.0 | Секунды–десятки секунд на CPU [HYP] | Устойчивы к фону и шрифтам, «понимают» формат даты из промпта [HYP]; риск галлюцинаций цифр | Одна модель, промпт | Медленно; галлюцинации → только как fallback | S13, S52, S70 |

**Рекомендуемая схема OCR (`[HYP]`, проверить в E0):** (1) кроп ROI правого нижнего угла (~30%×15% кадра), при неудаче — остальные углы; (2) усиление: HSV-маски под оранжевый/красный/жёлтый/белый + масштаб ×2–3; (3) распознавание *только строки* (PP-OCRv6 tiny/small rec или OnnxTR PARSeq), без детектора текста на всём кадре; (4) regex `\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b` + валидация (день ≤31, месяц ≤12, год в разумном диапазоне) + консистентность внутри серии; (5) VLM-fallback только для «не распознано». Метрика: exact-match по ~75 датированным кадрам (GT размечается за ~15 мин). Цель «нет даты» (~25 кадров) — отдельно, как precision «не выдумать дату».

### 4.2 Группировка снимков по площадкам (одна площадка, разные месяцы/ракурсы/сезон)

| Метод | Лицензия | Нужно обучение | Смена ракурса / сезона | CPU на 100 кадров | Комментарий | Источник |
|---|---|---|---|---|---|---|
| **CLIP / SigLIP 2** (base 0.4B, 20.02.2025) | Apache-2.0 (SigLIP 2) | Нет | Семантика «что на кадре», а не «какое это место» → риск склеить все зимние стройки [HYP] | секунды [HYP] | Хороший baseline и для zero-shot фильтра «есть ли техника» | S63 |
| **DINOv2** (ViT-S 21M / B 86M / L 300M / g 1.1B) | **Apache-2.0 (код и основные веса)** | Нет | Instance-level признаки лучше CLIP для «того же объекта» [HYP]; CLS или GeM по патчам | < 1 мин (ViT-B) [HYP] | Самый безопасный по лицензии backbone | S60 |
| **DINOv3** (ViT-S…7B, ConvNeXt; 14.08.2025) | **DINOv3 License** (Meta, не OSI: коммерция разрешена, запрет военного/ITAR, reverse engineering; gated) | Нет | Сильнее DINOv2 [UNVERIFIED для VPR] | как DINOv2 | Лицензионно сложнее, gated | S61, S62 |
| **AnyLoc** (DINOv2 + VLAD/GeM) | BSD-3-Clause | **Нет** (готовые словари VLAD) | Спроектирован для «unstructured» мест, смены условий (RA-L 2023) | GPU рекоменд.; на CPU ViT-G медленно — брать ViT-B [HYP] | Хорош именно для «ракурс+сезон» | S64 |
| **MixVPR** (ResNet-50, GSV-Cities) | `[не указана в README — UNVERIFIED]` | Нет (готовые веса) | Pitts30k R@1 91.6, MSLS-val 88.2 — уличные панорамы, не стройки | быстро (ResNet-50) | Дескрипторы 4096/512/128 | S65 |
| **MegaLoc** (CVPRW 2025) | **MIT** | Нет; `torch.hub.load("gmberton/MegaLoc","get_trained_model")` | SOTA на большинстве VPR-датасетов (заявлено), indoor+outdoor | ~ как ViT-B [HYP]; дескриптор 8448-d | Один вызов, лучший «из коробки» кандидат | S66 |
| **LightGlue + ALIKED/DISK** (геом. верификация) | LightGlue Apache-2.0; ALIKED BSD-3; DISK Apache; **SuperPoint — ограничительная лицензия** | Нет | Лучший сигнал «то же место» при перекрытии кадров (число инлайеров) | i7-10700K: ~20 FPS @512 kp. `[расчёт]` 100×top-5 = 500 пар ≈ 25–60 с; все 4950 пар — несколько минут | Только re-ranking top-k после глобальных эмбеддингов | S67 |
| **Кластеризация: HDBSCAN** (sklearn ≥1.3) | BSD (sklearn) | — | — | мгновенно | `min_cluster_size` по умолч. 5 → для серий 2–10 кадров ставить 2–3; `metric="cosine"` или `precomputed`; шум = −1 (одиночные кадры) | S68 |

**Что реально сработает на ~100 снимках (`[HYP]`):** обучать ничего не нужно. Схема: глобальные эмбеддинги (DINOv2-B GeM и/или MegaLoc) → матрица косинусных расстояний → re-ranking top-5 соседей через LightGlue+ALIKED (инлайеры) → комбинированная матрица → агломеративная кластеризация с порогом или HDBSCAN (`min_cluster_size=2`, `precomputed`). OCR-дата используется для упорядочивания внутри кластера, не для кластеризации. На 100 кадрах всё считается за 1–2 мин на CPU. Метрика: ручная GT групп (~20 мин) → pairwise F1 / ARI. Главный риск — «сезонная» склейка (снег) у CLIP-подобных эмбеддингов; mitigation — геометрическая верификация и VPR-модели.

### Источники Блока 4
- S52 PaddlePaddle/PaddleOCR (3.7.0, PaddleOCR-VL 1.6) — https://github.com/PaddlePaddle/PaddleOCR ✔
- S53 PP-OCRv6 docs — http://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html ✔
- S54 PP-OCRv6 HF blog / анонс — https://huggingface.co/blog/PaddlePaddle/pp-ocrv6 (сниппет; расходится с docs по det: +4.9 vs +4.6 — в таблице взято из docs)
- S55 JaidedAI/EasyOCR — https://github.com/JaidedAI/EasyOCR ✔
- S56 mindee/doctr — https://github.com/mindee/doctr ✔
- S57 felixdittrich92/OnnxTR — https://github.com/felixdittrich92/OnnxTR ✔
- S58 Tesseract «Improving the quality of the output» — https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html ✔
- S59 Сторонние сравнения OCR (скорость CPU Tesseract/EasyOCR/PaddleOCR, инвойсы) — https://invoicedataextraction.com/blog/python-ocr-library-comparison-invoices ; https://toon-beerten.medium.com/ocr-comparison-tesseract-versus-easyocr-vs-paddleocr-vs-mmocr-a362d9c79e66 (сниппеты)
- S60 facebookresearch/dinov2 — https://github.com/facebookresearch/dinov2 ✔
- S61 facebookresearch/dinov3 — https://github.com/facebookresearch/dinov3 ✔
- S62 DINOv3 LICENSE.md — https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md ✔
- S63 HF google/siglip2-base-patch16-224 — https://huggingface.co/google/siglip2-base-patch16-224 ✔
- S64 AnyLoc/AnyLoc — https://github.com/AnyLoc/AnyLoc ✔
- S65 amaralibey/MixVPR — https://github.com/amaralibey/MixVPR ✔
- S66 gmberton/MegaLoc — https://github.com/gmberton/MegaLoc ✔
- S67 cvg/LightGlue — https://github.com/cvg/LightGlue ✔
- S68 scikit-learn HDBSCAN — https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html ✔
- S69 Лицензии DEIMv2 по размерам (сторонний разбор) — https://www.libreyolo.com/docs/models/deim ; https://playground.roboflow.com/models/intellindust-ai-lab/deim (сниппеты)
- S70 Qwen3-VL обзор (OCR 32 языка, даты релиза) — https://docs.kanaries.net/articles/qwen3-vl (сниппет)

## Ключевые выводы (8–10)

1. **«Grounding DINO 2.0» не существует**; открыт только Grounding DINO 1.0 (+ MM-Grounding-DINO от OpenMMLab, LVIS minival 41.4 против 28.8). GD 1.5/1.6, DINO-X, T-Rex2 — **только облачный API** (Apache-2.0 лишь на клиентский код) → в открытый офлайн-репо не годятся (S1–S4, S21).
2. **SAM 3 (19.11.2025) и SAM 3.1 (27.03.2026) реально детектируют по тексту** все экземпляры концепта (COCO box 56.4, LVIS box 48.5), но 0.85–0.9B параметров, CUDA, gated веса, кастомная SAM License → инструмент офлайн-разметки на GPU, не CPU-демо (S5–S7).
3. **Zero-shot ≠ финальная модель**: RF100-VL показывает <2% у GroundingDINO/Qwen2.5-VL на сложных доменах; в индустриальном бенчмарке fine-tuned YOLO (лучший YOLO26s) «существенно» обходит zero-shot OVD. Роль OVD — псевдоразметка + baseline (S17, S20).
4. **Fine-grained различение по тексту не подтверждено ни одним источником** для наших классов → проверять экспериментально; лучшие рычаги: visual prompts (YOLOE), описательные промпты, VLM-верификация кропов (Qwen3-VL) [HYP].
5. **Последняя стабильная Ultralytics — YOLO26 (янв. 2026), YOLO27 не выпущен** (пакет 8.4.152, 14.09.2026). YOLO26 — лучший по CPU: n 38.9 мс / s 87.2 мс (ONNX, 640 px) при 40.9 / 48.6 mAP (S24, S28).
6. **Ultralytics = AGPL-3.0, включая обученные веса** (позиция Ultralytics) → весь репо под AGPL-совместимую лицензию; закрытое внедрение заказчиком потребует Enterprise. Apache-альтернативы с сопоставимым COCO AP: RF-DETR N–L, D-FINE, DEIM, RT-DETRv2/v4, YOLOX; MIT-обёртка LibreYOLO (S25, S26, S29–S40).
7. **Скрытые лицензионные ловушки «Apache»-моделей:** RF-DETR XL/2XL — PML 1.0; DEIMv2 S–X — бэкбон DINOv3 под DINOv3 License (не OSI, запрет военного применения); YOLO-World — GPL-3.0; Rex-Omni — база под Qwen Research License (S26, S30, S62, S69, S10, S15).
8. **Для CPU у DETR-семейства официальных CPU-цифр нет**; независимый бенчмарк OpenCV даёт порядок CNN-YOLO : RT-DETR : OVD ≈ 13 мс : 100 мс : 1–2 с (i9). SAHI даёт +5–7 AP на мелких объектах (до +13–15 с slicing-fine-tune), но ~5× время на наших кадрах → включать условно (S18, S35).
9. **Разметка**: X-AnyLabeling v4.0.0 (exe для Windows, встроенные GD/YOLOE/SAM3/Florence-2/Qwen3-VL/RF-DETR, экспорт YOLO+COCO) — минимальное трение; CVAT — MIT, но Docker+WSL2 и платная SAM2/SAM3-авторазметка; Roboflow Free = данные публично на Universe (S43–S51).
10. **OCR и группировка решаются без обучения**: PP-OCRv6 (Apache-2.0, OpenVINO tiny 0.2 с на полный пайплайн) / OnnxTR на кропе угла + regex-валидация; группировка — DINOv2/MegaLoc эмбеддинги + LightGlue-верификация + HDBSCAN/агломеративная (S52–S68).

## Shortlist для экспериментов E0 (OCR+группировка), E1 (zero-shot), E2 (fine-tune)

> Без выбора единственного победителя — каждый эксперимент сравнивает 2–3 кандидата на одной и той же мини-разметке.

### E0 — OCR даты + группировка по площадкам
| # | Кандидат | Плюсы | Минусы / trade-off |
|---|---|---|---|
| E0-A | **PP-OCRv6 small/tiny (rec на кропе, OpenVINO) + DINOv2-B (GeM) + HDBSCAN** | Всё Apache/BSD; самый сильный open OCR по заявлениям; быстро | Зависимость paddlepaddle; DINOv2 без VPR-дообучения может путать похожие стройки |
| E0-B | **OnnxTR (PARSeq) или Tesseract+HSV-препроцессинг + MegaLoc/AnyLoc + LightGlue(ALIKED) re-rank + агломеративная** | Только ONNX Runtime; VPR-модели заточены под смену ракурса/сезона; геометрия даёт объяснимость | Больше кода препроцессинга; MegaLoc 8448-d; LightGlue добавляет ~1 мин |
| E0-C | **VLM-fallback (Florence-2 `<OCR>`, MIT) + SigLIP 2 эмбеддинги** | Устойчивость к шрифтам/цветам; SigLIP 2 заодно даёт zero-shot теги сцены | Медленно на CPU, риск галлюцинаций цифр; семантическая, а не «местная» кластеризация |

### E1 — Zero-shot baseline и псевдоразметка
| # | Кандидат | Плюсы | Минусы / trade-off |
|---|---|---|---|
| E1-A | **MM-Grounding-DINO-T / GroundingDINO-T (Apache-2.0)** (+ OWLv2 для WBF-ансамбля) | Лучшее открытое text-grounding качество (COCO 50.4, LVIS 41.4); Apache; есть в X-AnyLabeling | 1–2 с/кадр CPU; слаб на редких узких терминах; mmdet-стек на Windows |
| E1-B | **YOLOE-26 (s/m/x) text + visual prompts (AGPL-3.0)** | Real-time на CPU, экспорт ONNX/OpenVINO; visual prompt для «буровая vs гусеничный кран»; LVIS 40.6 (26x) | AGPL; классы «запекаются» при экспорте; ниже SAM3/DINO-X по качеству |
| E1-C | **SAM 3 на GPU (Colab/Kaggle) как офлайн-разметчик + Qwen3-VL-4B/8B как верификатор кропов** | Лучший открытый text-детектор (COCO box 56.4); VLM различает описания | SAM License + gated, нужен GPU; MLLM медленный и с низким recall — только для спорных боксов |

### E2 — Fine-tune компактного детектора под CPU
| # | Кандидат | Плюсы | Минусы / trade-off |
|---|---|---|---|
| E2-A | **Ultralytics YOLO26 s/m (AGPL-3.0)** | Самый быстрый CPU (87 / 220 мс @640 ONNX), STAL для мелких объектов, обучение и экспорт одной командой, SAHI из коробки | AGPL на репо и веса; Enterprise для закрытого внедрения |
| E2-B | **RF-DETR S/M (Apache-2.0, `rfdetr` 1.10.1)** | DINOv2-бэкбон — сильный перенос на малые датасеты (RF100-VL); COCO 53.0/54.7; чистая лицензия | Нет офиц. CPU-цифр, ViT тяжелее на CPU; XL/2XL не использовать (PML) |
| E2-C | **DEIM-D-FINE S/M или RT-DETRv4-S (Apache-2.0)** | COCO 49.0–52.7 / 49.8; быстрая сходимость (DEIM); ONNX/OpenVINO (D-FINE) | Меньше «удобств» (конфиги, COCO-формат вручную); RT-DETRv4 требует DINOv3-учителя при обучении; DEIMv2 S+ — DINOv3 License |

**Общая рекомендация по протоколу:** одинаковый split (серии площадок не должны пересекаться между train/val — иначе утечка по ракурсам одной площадки), единый COCO-GT, замер латентности на одном ноутбуке CPU (ONNX Runtime/OpenVINO, imgsz 640 и 1280, с/без SAHI), лицензия модели — отдельной колонкой в итоговой таблице.

## Источники
- S1 IDEA Grounding-DINO-1.5-API README — https://github.com/IDEA-Research/Grounding-DINO-1.5-API ✔
- S2 IDEA DINO-X-API README — https://github.com/IDEA-Research/DINO-X-API/blob/main/README.md ✔
- S3 IDEA GroundingDINO (1.0) — https://github.com/IDEA-Research/GroundingDINO ✔
- S4 MM-Grounding-DINO (mmdetection) — https://github.com/open-mmlab/mmdetection/blob/main/configs/mm_grounding_dino/README.md ✔
- S5 facebookresearch/sam3 — https://github.com/facebookresearch/sam3 ✔
- S6 HF facebook/sam3 — https://huggingface.co/facebook/sam3 ✔
- S7 SAM 3 paper arXiv 2511.16719 — https://arxiv.org/html/2511.16719 ✔
- S8 THU-MIG/yoloe — https://github.com/THU-MIG/yoloe ✔
- S9 Ultralytics YOLOE docs — https://docs.ultralytics.com/models/yoloe ✔
- S10 AILab-CVC/YOLO-World — https://github.com/AILab-CVC/YOLO-World ✔
- S11 HF google/owlv2-base-patch16-ensemble — https://huggingface.co/google/owlv2-base-patch16-ensemble ✔
- S12 OWLv2 paper arXiv 2306.09683 — https://arxiv.org/abs/2306.09683 ✔
- S13 HF microsoft/Florence-2-large — https://huggingface.co/microsoft/Florence-2-large ✔
- S14 QwenLM/Qwen3-VL — https://github.com/QwenLM/Qwen3-VL ✔
- S15 IDEA-Research/Rex-Omni — https://github.com/IDEA-Research/Rex-Omni ✔
- S16 Rex-Omni paper arXiv 2510.12798 — https://arxiv.org/abs/2510.12798 (сниппет поиска)
- S17 Roboflow100-VL arXiv 2505.20612 — https://arxiv.org/abs/2505.20612 ✔
- S18 OpenCV 5 DNN Benchmarks (wiki, 05.06.2026) — https://github.com/opencv/opencv/wiki/OpenCV-5-DNN-Benchmarks ✔
- S19 OVD robustness arXiv 2405.14874 — https://arxiv.org/abs/2405.14874 ✔ (только аннотация)
- S20 MDPI Sensors 26(17):5646 (шахты, zero-shot vs fine-tuned) — https://www.mdpi.com/1424-8220/26/17/5646 (403, сниппет поиска)
- S21 IDEA-CVR (X) о GD 1.6 Pro/Edge, июль 2024 — https://x.com/IDEACVR/status/1859793408744882536 (сниппет)
- S22 Разбор SAM License (сторонний) — https://sam3ai.com/license/ (сниппет; первоисточник лицензии не открыт → условия частично UNVERIFIED)
- S23 DINO-X paper arXiv 2411.14347 — https://arxiv.org/abs/2411.14347 (сниппет)
- S24 Ultralytics YOLO26 docs — https://docs.ultralytics.com/models/yolo26/ ✔
- S25 Ultralytics License — https://www.ultralytics.com/license ✔
- S26 roboflow/rf-detr — https://github.com/roboflow/rf-detr ✔
- S27 Ultralytics models / roadmap (поиск: YOLO27 «coming soon») — https://docs.ultralytics.com/models ; https://www.ultralytics.com/roadmap (сниппет)
