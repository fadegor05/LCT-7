# PART J — Открытые датасеты и модели для недостающих классов
_статус: done (2026-09-15); источников: 38 (датасетов 35, моделей 3); подтверждено [OK]: 28; [PARTIAL]: 10_

Условные обозначения: `[OK]` — подтверждено со страницы/API; `[PARTIAL]` — только сниппет поиска / страница не отрендерилась (Roboflow Universe: WebFetch и curl → 403, Browser pane → «Policy check temporarily unavailable»); `[UNVERIFIED]` — не подтверждено.

Ограничения проверки: страницы Roboflow Universe не открылись ни одним способом — все данные по Roboflow-проектам взяты из сниппетов поиска. Papers-with-Code (paperswithcode.com) с машины не отвечает (curl http=000) — не проверен.

## 1. Матрица покрытия классов

Легенда: **ДА** — отдельный класс; **~** — частично / в составе более общего класса; **—** — нет. «Можно на хакатоне» = можно ли обучить модель и выложить веса в открытый репозиторий.

| Датасет | Лицензия | Можно на хакатоне | Изобр. | Буровая | Башенный кран | Экск.-погрузчик | Гусен. кран | Автобетононасос | Копёр | Самосвал | Экскаватор | Автокран | Похожесть на наши снимки |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Kaggle xyzyxzzxy/construction-equipment (§2) | CC0 | **ДА** | 19 982 | — | — | — | — | — | — | ДА | ДА | ДА (Autocran; + Crane manipulator) | низкая/средняя (CCTV, ~20 камер, МСК) |
| J02 MOCS | CC BY-NC 4.0 | СЕРО | 41 668 | ~ (pile driver) | **ДА** | — | — | **ДА** (pump truck) | **ДА** (pile driver) | ~ (truck) | ДА | ДА (vehicle crane) | **высокая** (174 площадки, разные устройства) |
| J14 HF AmiyaChan/mocs_yolo (зеркало MOCS) | тег MIT, фактически CC BY-NC 4.0 | СЕРО | ≈MOCS [UNVERIFIED] | ~ | ДА | — | — | ДА | ДА | ~ | ДА | ДА | высокая |
| J16 APOCE (RF100-VL) | CC BY 4.0 (RF100-VL) | **ДА** | 928–931 [PARTIAL] | ~ (piling machine) | **ДА** | — | ~ (lifting equipment) [UNVERIFIED] | — | **ДА** (piling machine) | ДА | ДА | ~ (lifting equipment) | средняя/высокая для дрон-кадров |
| J17 Roboflow KlinterAI Construction | CC BY 4.0 [PARTIAL] | ДА [PARTIAL] | 700–922 [PARTIAL] | **ДА** (drilling rig, folded piling rig, CFA drill) | — | ~ (Backhoe/Backactor) | — | — | ~ | ДА | ДА | ~ (crane, load carrying crane) | высокая (свайные площадки, цифровые камеры) |
| J19 Roboflow Tower Crane Component | CC BY 4.0 [PARTIAL] | ДА [PARTIAL] | 954 [PARTIAL] | — | **ДА** (+ Jib Mast …) | — | — | — | — | — | — | — | средняя [UNVERIFIED] |
| J19 Roboflow KMUTT Tower Crane | CC BY 4.0 [PARTIAL] | ДА | 113 | — | **ДА** (+ Counterweights, Hook Block, Operator Cab) | — | — | — | — | — | — | — | средняя |
| J18 Roboflow dikong drone inspection | CC BY 4.0 [PARTIAL] | ДА [PARTIAL] | 2 599 [PARTIAL] | — [UNVERIFIED] | **ДА** | — [UNVERIFIED] | ~ (crane) | — [UNVERIFIED] | — [UNVERIFIED] | [UNVERIFIED] | ДА | ~ (crane) | средняя/высокая для дрон-кадров |
| J03 ACID | CC BY 4.0 + «No commercial usage», запрет распространения | НЕТ/СЕРО | 10 000 | — | **ДА** | **ДА** | — | — | — | ДА | ДА | ДА (mobile crane) | средняя (часть кадров из YouTube) |
| J08 AIDCON | CC BY-NC 4.0, research only | СЕРО/НЕТ | 2 155 | — | — | **ДА** | — | ~ (в «other») [PARTIAL] | — | ДА | ДА | ~ (в «other») [PARTIAL] | высокая для дрон-кадров |
| J05 CIS | [UNVERIFIED] | СЕРО | 50 000 | — | — | — | — | — | — | ДА | ДА | — | высокая (74 площадки) |
| J01 SODA | CC BY 4.0 (статья) [данные UNVERIFIED] | СЕРО→ДА | 19 846 | — | — (только hook) | — | — | — | — | — | — | — | средняя (классы не те) |
| J09 Kaggle kartaviychert/arh-df | GPL 2 | СЕРО | 318 | — | ~ (crane) | — | ~ (crane) | — | — | ~ (truck) | ДА | ~ (crane) | средняя (≈11.8 объектов/кадр) |
| J15 RF100 Excavators (keremberke/LibreYOLO) | CC BY 4.0 | **ДА** | 2 655 | — | — | — | — | — | — | ДА | ДА | — | средняя |
| J20 Kaggle pablogarcher24 PPE+Heavy (balanced) | CC0 | **ДА** | [UNVERIFIED] | — | — | — | — | — | — | ДА | ДА | — | [UNVERIFIED] |
| J10 HF keremberke/construction-safety | CC BY 4.0 | ДА | 398 | — | — | — | — | — | — | ДА | ДА | — | средняя |
| J21 Kaggle dataclusterlabs/jcb-image-dataset | CC0 (Kaggle), вендор-sample на HF — запрет коммерции | СЕРО | 3 000+ | — | — | ~ (JCB) [UNVERIFIED] | — | — | — | — | ~ | — | низкая (крупный план, без bbox) |
| J07 GitHub Tower-crane-dataset | нет лицензии | НЕТ | 2 911 | — | ~ (только крюк, вид с крана) | — | — | — | — | — | — | — | низкая |
| J11 HF LouisChen15/ConstructionSite | CC BY-NC 4.0, gated | СЕРО | ~10 013 [PARTIAL] | — | — | — | — | — | — | — | ~ (grounding) | — | средняя (VQA, не детекция) |
| J23 Roboflow Crane Construction | CC BY 4.0 [PARTIAL] | ДА | 484 | — | — | — | — | — | — | — | — | — (construction-vehicle) | низкая |
| J24 CIVAD | [UNVERIFIED] | [UNVERIFIED] | 86 905 [PARTIAL] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | не опубликован (по найденному) |
| J12/J13/J22/J25 (Transzvuk, Datacluster HF, Kaggle Unknown, miniexcav) | нет / Unknown / NC | НЕТ | — | — | — | — | — | — | — | — | ~ | ~ | низкая |

**Итог по матрице:** гусеничный кран отдельным классом — **нигде**; автобетононасос — **только MOCS (NC)**; буровая установка — **только KlinterAI (мало)**, плюс «piling machine» в APOCE (дрон) и «pile driver» в MOCS (NC); башенный кран — несколько чистых по лицензии источников (APOCE, Tower Crane Component, dikong, KMUTT) + MOCS/ACID с NC; экскаватор-погрузчик — **только NC-источники** (ACID, AIDCON), в KlinterAI неоднозначно.

## 2. Kaggle xyzyxzzxy/construction-equipment — структура, формат, число изображений

Источник: публичный Kaggle API без авторизации (curl, 2026-09-15):
- `GET https://www.kaggle.com/api/v1/datasets/view/xyzyxzzxy/construction-equipment` → JSON `[OK]`
- `GET https://www.kaggle.com/api/v1/datasets/metadata/xyzyxzzxy/construction-equipment` → JSON `[OK]`
- `GET https://www.kaggle.com/api/v1/datasets/list/files/xyzyxzzxy/...` → **возвращает HTML-страницу, не JSON** (не работает).
- `GET https://www.kaggle.com/api/v1/datasets/list/xyzyxzzxy/construction-equipment?pageSize=1000&pageToken=...` → **рабочий** постраничный листинг файлов (JSON `datasetFiles`, `nextPageToken`). Фактически отдаёт по 200 файлов на страницу; 200 страниц пройдено скриптом.

Факты `[OK]`:
- Лицензия: `"licenseName":"CC0: Public Domain"`, в metadata `"licenses":[{"name":"CC0-1.0"}]` → **ДА**.
- `totalBytes` = 17 494 075 225 (≈17.5 ГБ); версия 1, `lastUpdated` 2024-12-20; downloadCount 40 587; usabilityRating 0.5; `userSpecifiedSources` пусто; описание = только список классов 0..16.
- Файлов всего: **39 964** = **19 982 .jpg + 19 982 .txt** (сумма байт по листингу совпадает с totalBytes — листинг полный).
- Структура:
  ```
  train/images  16 754 jpg
  train/labels  16 754 txt
  valid/images   3 228 jpg
  valid/labels   3 228 txt
  ```
  Тестового сплита нет. Других файлов (data.yaml, README, json) **нет** — порядок классов берётся из description (0: Dump truck … 16: Autocran).
- Формат разметки: **YOLO txt** (парные images/labels, по имени файла; структура Ultralytics). Размер .txt: среднее 68 байт, максимум 270 байт → в среднем ~1–2 объекта на кадр, максимум порядка 7–10 строк (оценка по байтам, строка YOLO bbox ≈ 30–40 байт; bbox vs полигоны содержимым не проверено — анонимная загрузка отдельного файла `api/v1/datasets/download/.../train/labels/*.txt` → HTTP 404, нужен токен) `[PARTIAL]`.
- **2 699 файлов разметки нулевого размера** (пустые = фоновые кадры без объектов) `[OK]`.
- Изображения: средний размер 0.88 МБ, медиана 0.92 МБ.
- Происхождение: имена файлов — **таймстемпы стационарных камер видеонаблюдения**, не фото: `camera_6.201_2024-01-05T16_42_20_236+03_00.jpg` (10 879 шт., часовой пояс **+03:00 = Москва**), `238_12_24_27_053979-2023-09-22.jpg` (4 384), `2501_…` (1 573), `1325_…` (859), `1422_…` (584) и т.д.; всего 19 префиксов камер/объектов. Даты съёмки: 2023-09 (3 808), 2023-10 (3 595), 2023-11 (1 700), 2023-12 (3 347), 2024-01 (7 532) — т.е. осень–зима, нет лета.
- Вывод: это кадры с небольшого числа (~20+) фиксированных CCTV-камер (российские, МСК+03:00), сильно коррелированные серии. Похожесть на наши фоторепортажи — **низкая/средняя** (другая точка съёмки, мало ракурсов, риск переобучения на фон). Буровых, башенных кранов, экскаваторов-погрузчиков, гусеничных кранов, бетононасосов, копров **нет в классах**.
- Скачивание: `kaggle datasets download -d xyzyxzzxy/construction-equipment` (нужен kaggle.json токен) или через UI; 17.5 ГБ.

## 3. Карточки датасетов (J01…)

### J01. SODA — Site Object Detection dAtaset `[OK]`
- URL: https://arxiv.org/abs/2202.09554 ; журнал: Automation in Construction 142 (2022) 104499 (https://www.sciencedirect.com/science/article/abs/pii/S0926580522003727). Roboflow-копия: https://universe.roboflow.com/deul-saha-la3uh/soda-mwh0v `[PARTIAL]`
- Лицензия: arXiv-страница — «Creative Commons Attribution 4.0 (CC BY 4.0)» (это лицензия **статьи на arXiv**; лицензия самих данных на отдельной странице не найдена) → **СЕРО→ДА** (при CC BY 4.0 — можно с атрибуцией; уточнить лицензию данных).
- Классы (15): helmet, vest, wood, board, person, fence, rebar, hook, brick, cutter, ebox, handcart, hopper, scaffold, slogan.
- Целевые классы: **нет ни одного** (нет техники вообще; есть hook, hopper, scaffold).
- Объём: 19 846 изображений, 286 201 объект `[OK]`.
- Формат: VOC/YOLO `[UNVERIFIED]`.
- Тип съёмки: «multiple construction sites in different site conditions, weather conditions, and construction phases, covering different angles» — фото/видео с земли, Китай.
- Похожесть: средняя по сцене, но классы не нужны. Официальная ссылка на скачивание со страницы SCUT (www2.scut.edu.cn/bim/...) не открылась (ошибка сайта).
- Вывод для нас: **не нужен** (разве что как negative/контекст).

### J02. MOCS — Moving Objects in Construction Sites `[OK]`
- URL: http://www.anlab340.com/Archives/IndexArctype/index/t_id/17.html (Tsinghua, лаб. An); статья: Automation in Construction, https://www.sciencedirect.com/science/article/abs/pii/S0926580520310621
- Страница: «All the images in MOCS dataset are collected from real construction sites. There are 41,668 images in dataset and 13 categories of objects are annotated.»
- Скачивание: только через **Request form** (https://www.wjx.cn/vm/wWGwSOc.aspx — анкета на китайском сервисе wjx) → ссылка присылается. Прямой ссылки нет.
- Лицензия: на странице явного текста лицензии не найдено в извлечённых строках `[UNVERIFIED]`; доступ по заявке → **СЕРО** (обычно academic-only; публикация весов не оговорена).
- Классы (13): worker, tower crane, hanging hook, vehicle crane, roller, bulldozer, excavator, truck, loader, pump truck, concrete transport mixer, pile driver, other vehicles.
- Целевые: **башенный кран — ДА**, **автобетононасос (pump truck) — ДА**, **копёр (pile driver) — ДА** (скорее всего включает буровые/сваебойные установки — определение класса в статье не проверено `[UNVERIFIED]`), автокран (vehicle crane) — ДА, экскаватор — ДА, погрузчик (loader) — ДА, самосвал/truck — ДА. Экскаватор-погрузчик и гусеничный кран отдельно — НЕТ.
- Объём: 41 668 изображений, 222 861 экземпляр; 174 стройплощадки; bbox + маски.
- Формат: COCO-подобный (bbox + mask) `[UNVERIFIED]`.
- Тип съёмки: 5 разных устройств, разные ракурсы/освещение/погода, реальные площадки Китая → **высокая** похожесть на наши кадры (широкий план, много мелких объектов, башенные краны).
- Размер: `[UNVERIFIED]`.
- Вывод: **лучший кандидат по покрытию нужных классов, но лицензионно серый** — нужна заявка и проверка условий в ответе.

### J03. ACID — Alberta / Advanced Construction Image Dataset `[OK]`
- URL: https://www.acidb.net/ ; https://www.acidb.net/dataset ; https://www.acidb.net/term-of-use ; Roboflow-копия (сторонняя): https://universe.roboflow.com/test-blhxw/acid-dataset `[PARTIAL]`
- Лицензия дословно (dataset page): «Creative Commons Attribution 4.0 International License. No commercial usage is allowed.»; изображения с YouTube — «must comply with YouTube's copyright policy». Terms of use: «Only use the ACID dataset suite for academic and research purposes. No commercial usage is allowed.» и «You may not redistribute, share, or publish the ACID datasets or other intellectual contents, in whole or in part, without express written permission from ACID group.» Страница: доступ «currently only sharing for research purposes». → **НЕТ/СЕРО** (государственный хакатон с перспективой внедрения = некоммерческий? спорно; публикация весов в ToU явно не запрещена, но «intellectual contents» трактуется широко). Сторонние Roboflow-копии — нарушение ToU.
- Классы (10): Excavator, Compactor, Dozer, Grader, Dump Truck, Concrete Mixer Truck, Wheel Loader, **Backhoe Loader**, **Tower Crane**, Mobile Crane.
- Целевые: **экскаватор-погрузчик — ДА**, **башенный кран — ДА**, автокран (mobile crane) — ДА, самосвал — ДА, экскаватор — ДА. Буровая/копёр/бетононасос/гусеничный кран — НЕТ.
- Объём: 10 000 изображений, 15 767 объектов (всего по сайту) `[OK]`.
- Формат: detection + instance segmentation + captioning; формат файлов `[UNVERIFIED]`.
- Тип съёмки: частично кадры из YouTube (web-scraped), частично собственные → средняя похожесть (часто крупный план машины).
- Скачивание: Google-форма, ссылка приходит «in one week»; или email dr.boxiao@gmail.com.

### J04. AIDCON — Aerial Image Dataset for Construction `[PARTIAL]`
- URL: https://www.ai2lab.org/aidcon/ ; статья Remote Sensing 16(17):3295, https://www.mdpi.com/2072-4292/16/17/3295
- Лицензия (по сниппету поиска): «only sharing for research purposes», «no commercial usage» `[PARTIAL]` → **СЕРО/НЕТ**.
- Объём: 2 155 аэрофото, 9 563 машины, пиксельная разметка, 9 категорий (полный список — проверяется).
- Тип съёмки: дрон (надир/наклон) → похоже на наши дрон-кадры.

### J05. CIS — Construction Instance Segmentation dataset `[PARTIAL]`
- URL: https://www.sciencedirect.com/science/article/abs/pii/S0926580523003436 (Automation in Construction, 2023)
- Классы (10): worker with helmet, worker without helmet, PC delivery truck, dump truck, concrete mixer truck, excavator, roller, dozer, wheel loader, PC (precast components).
- Целевые: **нет** (ни буровых, ни кранов, ни бетононасосов).
- Объём: 50 000 изображений, 104 021 экземпляр; 74 стройплощадки; смартфоны, БПЛА, цифровые камеры, PoE-камеры.
- Лицензия / скачивание: `[UNVERIFIED]` (проверяется).

### J06. Roboflow Universe — KlinterAI «Construction Dataset» `[PARTIAL]`
- URL: https://universe.roboflow.com/klinterai/construction-dataset-6xih3 (WebFetch → 403)
- Из сниппета поиска: классы включают «folded piling rig», «contiguous pile», «sectional flight auger», hydraulic grabs, testing equipment. → **буровая (piling rig) — ДА** `[PARTIAL]`.
- Лицензия, число изображений: `[UNVERIFIED]`.

### J02-upd. MOCS — лицензия подтверждена `[OK]`
- На странице http://www.anlab340.com/Archives/IndexArctype/index/t_id/17.html (HTML, curl) найдено: «licensed under a … Creative Commons Attribution-NonCommercial 4.0 International License» со ссылкой http://creativecommons.org/licenses/by-nc/4.0/ → **СЕРО** (CC BY-NC 4.0: обучение и публикация весов в открытом репозитории для некоммерческого хакатона допустимы при атрибуции, но внедрение/коммерческое использование модели — риск; для гос. заказчика нужна юр. оценка).

### J07. Tower-crane-dataset (GitHub, к статье FLE-YOLO) `[OK]`
- URL: https://github.com/sugar-fifty-doge/Tower-crane-dataset (статья FLE-YOLO: https://doi.org/10.3390/app15105364 ; код https://github.com/sugar-fifty-doge/FLE-YOLO)
- Лицензия: GitHub API `"license": null` — **лицензии нет** → **НЕТ/СЕРО** (по умолчанию «все права защищены»).
- README: «This dataset contains 2911 image files of tower crane hooks and their corresponding XML tag files»; снимки от Gansu Construction Investment Group Machinery Company.
- Классы: **крюк башенного крана** (hook), не сам кран. Точный список классов в XML не проверен `[UNVERIFIED]`.
- Формат: Pascal VOC XML (Annotations.zip 1.17 МБ) + images1..10.zip (≈201 МБ суммарно по API).
- Тип съёмки: камера на кране, взгляд на крюк сверху → **не похоже** на наши снимки.
- Вывод: **не подходит** для детекции башенного крана целиком.

### J08. AIDCON — полные данные `[OK]`
- URL: https://www.ai2lab.org/aidcon/
- Лицензия дословно: «Creative Commons Attribution-NonCommercial 4.0 International License»; «AIDCON is currently only sharing for research purposes and no commercial usage is allowed.» → **СЕРО/НЕТ**.
- Классы (9): Dump truck, excavator, **backhoe loader**, wheel loader, compactor, dozer, grader, car, other.
- Целевые: **экскаватор-погрузчик — ДА**; самосвал, экскаватор — ДА; остальные — НЕТ.
- Объём: 2 155 изображений UAV, 9 563 машины, пиксельная (instance) разметка.
- Съёмка: БПЛА, 30 стройплощадок, 47 стоянок техники, 3 карьера, 2015–2023, высота ~10–150 м → похоже на наши **дрон**-кадры.
- Скачивание: форма-запрос на сайте.

### J09. Kaggle kartaviychert/arh-df «Сonstruction equipment» (+ Dataset Ninja) `[OK]`
- URL: https://www.kaggle.com/datasets/kartaviychert/arh-df ; https://datasetninja.com/construction-equipment
- Лицензия: Kaggle API `"licenseName":"GPL 2"`; Dataset Ninja: «GNU GPL 2.0» → **СЕРО** (GPL для данных — copyleft; веса как производная работа — неоднозначно).
- Классы (5): crane, excavator, truck, tractor, other. Кран не разделён на башенный/автокран `[UNVERIFIED]`.
- Объём: 318 изображений, 3 752 объекта (≈11.8 объектов/кадр — плотные сцены), bbox. Kaggle totalBytes 426 475 795 (≈0.43 ГБ); Supervisely-экспорт 406 МБ.
- Автор: Ilya Kalinin (русскоязычный). Обновлён 2023-06-24. Съёмка: `[UNVERIFIED]` (много объектов на кадр — вероятно обзорные кадры/видеонаблюдение).

### J10. HF keremberke/construction-safety-object-detection `[OK]`
- URL: https://huggingface.co/datasets/keremberke/construction-safety-object-detection (копия Roboflow `roboflow-universe-projects/construction-site-safety` v1)
- Лицензия: «CC BY 4.0» → **ДА**.
- Классы (17): barricade, dumpster, excavators, gloves, hardhat, mask, no-hardhat, no-mask, no-safety vest, person, safety net, safety shoes, safety vest, dump truck, mini-van, truck, wheel loader.
- Объём: train 307 / valid 57 / test 34 = 398 изображений. Формат: zip (COCO, по HF-скрипту).
- Целевые: нет. Экскаватор, самосвал — ДА. Вывод: мало и не про наши классы.

### J11. HF LouisChen15/ConstructionSite `[OK]` (карточка закрыта, gated)
- URL: https://huggingface.co/datasets/LouisChen15/ConstructionSite
- Лицензия (теги API): `license:cc-by-nc-4.0` → **СЕРО**. Доступ gated (нужен логин и согласие).
- Задачи: image-to-text / visual grounding; 10K<n<100K; parquet. По сниппету: 10 013 изображений, grounding «excavators, rebar, workers with white hard hats» `[PARTIAL]`.
- Целевые классы: не заявлены. Для детекции малополезен.

### J12. HF Transzvuk/piling-equipment `[OK]`
- URL: https://huggingface.co/datasets/Transzvuk/piling-equipment — gated, без лицензии в тегах, n<1K, imagefolder; файлы — ~15 рекламных фото сваевдавливающих машин (Piling-Machine-CO450, RSM80, Sheet-Piling-Machine, «Vdavlivanie-Svay»). **Без разметки** → только как примеры для визуального ознакомления. Лицензия не указана → **НЕТ**.

### J13. HF Dataclusterlabspvtltd/Construction_Vehicle_Images_Trucks_Tractor `[OK]`
- Лицензия: `license_name: datacluster-commercial-sample`; «Commercial use ❌ Not permitted», «Redistribution ❌ Not permitted» → **НЕТ**. Классы: tractor, truck; VOC XML; Индия, смартфоны. Не подходит.

### J14. HF AmiyaChan/mocs_yolo — неофициальное зеркало MOCS в YOLO `[OK]`
- URL: https://huggingface.co/datasets/AmiyaChan/mocs_yolo ; не gated.
- Файлы (HF tree API): `images.rar` 9 675 931 636 байт (≈9.7 ГБ), `labels.rar` 6 981 249 байт (≈7 МБ), README = только `license: mit`.
- Лицензия: тег **MIT — неправомерная перелицензия**: оригинал MOCS под CC BY-NC 4.0 (J02). Правильно считать **CC BY-NC 4.0 → СЕРО**. Удобно как готовый YOLO-формат MOCS без заявки, но ссылаться на оригинал и соблюдать NC.
- Содержимое rar (сплиты, порядок классов) не проверено `[UNVERIFIED]`.

### J15. Roboflow «Excavators» (mohamed-sabek) = RF100 excavators-czvg9 `[OK]`
- URL: https://huggingface.co/datasets/keremberke/excavator-detector ; https://huggingface.co/datasets/LibreYOLO/excavators-czvg9 ; оригинал https://universe.roboflow.com/mohamed-sabek-6zmr6/excavators-cwlh0
- Лицензия: «CC BY 4.0» / `license:cc-by-4.0` → **ДА**.
- Классы (3): excavators, dump truck, wheel loader.
- Объём: 2 655–2 656 изображений (train 2 244–2 245 / valid 267 / test 144); COCO (keremberke) или YOLO+data.yaml (LibreYOLO), 640×640 stretch.
- Съёмка: имена `construction--1-_mp4-103_jpg` — кадры из видео. Похожесть средняя. Целевых классов нет.

### J16. APOCE — Aerial Photographs for Object Detection of Construction Equipment (в составе RF100-VL) `[СКАЧАНО И ПРОВЕРЕНО 2026-09-16]`

**Проверено на скачанном архиве** (`data/external/apoce.tar`, 1 418 557 440 байт, совпало с листингом HF):
- **928 изображений** (train 649 / valid 185 / test 94), **2 246 рамок**. Разметка — **COCO json** (`_annotations.coco.json` в каждом сплите), не YOLO: для Ultralytics нужна конвертация.
- **Классы и число рамок:** excavator 962, dump-truck 564, tower-crane **290**, concrete-mixer 205, bulldozer 95, piling-machine **78**, lifting-equipment 52.
- **Лицензия:** в `README.dataset.txt` самого экспорта написано «License: MIT» (в статье RF100-VL указано CC BY 4.0 — расхождение; обе лицензии разрешают использование, в документации сослаться на обе).
- **Разрешения кадров смешанные:** 960×540 (486 кадров), 5472×3648 (202), 4864×3648 (131), 6000×4000 (84), 3840×2160 (25).
- **Масштаб объектов:** >96 px — 1 742 рамки, 32–96 px — 475, <32 px — 29. То есть мелких объектов мало, но кадры разного размера: считать нужно после ресайза под обучение.
- **Вывод:** башенные краны берём отсюда (290 рамок — рабочий объём). Буровых всего 78 и они слиты в «piling-machine» вместе с копрами → своя разметка всё равно обязательна.

---

- URL: https://universe.roboflow.com/roboflow100vl-full/apoce-aerial-photographs-for-object-detection-of-construction-equipment-6raie-ryqq ; HF-зеркало: https://huggingface.co/datasets/LibreYOLO/rf100-vl → файл `apoce-aerial-photographs-for-object-detection-of-construction-equipment.tar` **1 418 557 440 байт (≈1.42 ГБ)** `[OK]`.
- Классы (по сниппету поиска, RF100-VL): excavator, bulldozer, concrete-mixer, dump-truck, lifting-equipment, **piling-machine**, **tower-crane** `[PARTIAL]` — проверяется.
- Объём: 928 / 931 изображение (разные сниппеты) `[PARTIAL]`. Съёмка: аэрофото (дрон).
- Лицензия: LibreYOLO/rf100-vl тег `license:mit` (для агрегатора); лицензия исходного проекта Roboflow `[UNVERIFIED]` — проверяется.

### J17. Roboflow KlinterAI «Construction Dataset» — дополнение `[PARTIAL]`
- По сниппету: 922 open source images; классы включают Backhoe/Backactor, drilling rig, load carrying crane, folded piling rig, contiguous pile, sectional flight auger, bore pile. → **буровая — ДА**, **экскаватор-погрузчик — ДА(?)** (Backhoe/Backactor в британской терминологии = экскаватор с обратной лопатой, не обязательно погрузчик) `[PARTIAL]`. Лицензия `[UNVERIFIED]`. Страница: WebFetch 403, curl 403, Browser pane — «Policy check temporarily unavailable».

### J18. Roboflow dikong «drone inspection of construction» `[PARTIAL]`
- URL: https://universe.roboflow.com/dikong-alvun/drone-inspection-of-construction-21xro
- По сниппетам: 2 599 изображений, 18 классов, среди них crane, excavator, **tower crane**. Лицензия, полный список классов `[UNVERIFIED]`. Съёмка — дрон.

### J19. Roboflow — башенные краны (мелкие проекты) `[PARTIAL]`
- KMUTT «Tower Crane»: https://universe.roboflow.com/king-mongkuts-university-of-technology-thonburi-zdkyg/tower-crane-zxwqv — сниппет: 113 изображений, 4 класса (Counterweights, Hook Block, Operator Cab, Tower Crane), **CC BY 4.0** → ДА, но очень мало.
- «Tower Crane Component» (workspace excavator-detection-dataset): https://universe.roboflow.com/excavator-detection-dataset/tower-crane-component-pbv83 — сниппет: 954 изображения + pre-trained model; классы/лицензия `[UNVERIFIED]`.
- Мелкие: «Heavy Equipment» (excavator-sampling) 472 изобр.; «Construction Equipment» (boat-j9swf) 184 изобр. — классы `[UNVERIFIED]`.

### J17-upd. KlinterAI — дополнительные сниппеты `[PARTIAL]`
- Сниппет поиска: «licensed under CC BY 4.0»; «about 700+ images with 77 identified classes»; «custom built for Construction Foundations Sites … collected from the year 2000 onwards using Digital Cameras». Классы (часть): car, crane, excavator, floor, person, stone, truck, wall, water, concrete loader, aerial view of construction site, bore pile, building structure, cables, concrete mixer truck, contiguous pile, continuous flight auger drill, dump truck, exposed piles, drilling rig, folded piling rig, sectional flight auger, Backhoe/Backactor, load carrying crane.
- Разночтение числа изображений: 700+ (описание) / 922 (карточка). → **единственный найденный открытый источник с классами буровой/сваебойной техники на фото с земли; лицензия (по сниппету) CC BY 4.0 → ДА, но 77 классов на ~900 кадров = единицы примеров на класс**.

### J20. Kaggle pablogarcher24/ppe-and-heavy-machinery-detection(-balanced) `[OK]`
- URL: https://www.kaggle.com/datasets/pablogarcher24/ppe-and-heavy-machinery-detection-balanced (CC0: Public Domain, 2 057 527 984 байт, 2025-05-29) и …/ppe-and-heavy-machinery-detection (ODbL «Database: Open Database, Contents: Database Contents», 1 190 137 289 байт) → **ДА** (balanced, CC0) / **СЕРО→ДА** (ODbL).
- Классы с числом объектов (balanced): mask 3788, boots 3099, gloves 3099, human 3099, helmet 3099, vest 3099, glasses 3099, ear_protection 2965, road_roller 4023, excavator 4000, dump_truck 6000, bulldozer 2989, wheel_loader 3718, background 3039.
- Структура: папка `FinalDataset/` (jpg; формат разметки по первой странице листинга не виден) `[PARTIAL]`. Целевых классов нет.

### J21. Kaggle dataclusterlabs/jcb-image-dataset «Excavator Image Dataset | Construction Vehicle» `[OK]`
- Лицензия в Kaggle: «CC0: Public Domain»; 798 127 380 байт; описание: «over 3,000+ images of excavator vehicles», краудсорс, 200+ локаций (Индия), «To download full dataset … sales@datacluster.ai». В Индии «JCB» — нарицательное название **экскаватора-погрузчика**; фактически ли это backhoe loader — по превью не проверено `[UNVERIFIED]`. Файлы в корне (jpg), разметки в первой странице листинга не видно → вероятно **без bbox** `[PARTIAL]`. Лицензионно: Kaggle-метка CC0, но на HF у того же вендора sample запрещает коммерческое использование (J13) → **СЕРО**.

### J22. Прочие Kaggle-кандидаты (проверены API, не рекомендуются) `[OK]`
| ref | лицензия | размер | что внутри |
|---|---|---|---|
| mennamahmoudd/construction-sites-equipments | Unknown → НЕТ | 4.98 ГБ | `Construct.AI.v2.BB.yolov8/` (Roboflow-экспорт YOLOv8, png, data.yaml); классы не видны |
| lilonglilong/cranepicture | Unknown → НЕТ | 2.86 ГБ | «Crane Defect Dataset (Wire Rope and Human Ladder)» — дефекты, не детекция кранов |
| whitetigerpx/truck-crane | Unknown → НЕТ | 4.8 МБ | 82 valid images+labels (YOLO) — автокран |
| pranavpr03/crane-dataset | Unknown → НЕТ | 50 МБ | jpg без разметки в 1-й странице |
| propro32/construction-vehicles-additional | Unknown → НЕТ | 691 МБ | Forklift/… YOLO |
| ashrafminhaj/excavator | «Data files © Original Authors» → НЕТ | 5 МБ | «collected from google search» |
| dataclusterlabs/construction-vehicle-images | CC BY-NC-ND 4.0 → НЕТ | 1.14 ГБ | Trucks/Tractor |
- Kaggle API `datasets/list?search=` по «drilling rig», «heavy equipment» — релевантных датасетов **нет**.

### J23. Roboflow «Crane Construction» (Amer El Saad) `[PARTIAL]`
- URL: https://universe.roboflow.com/amer-el-saad-s-workspace/crane-construction-ivhdf — сниппет: 484 изображения; классы worker, Fence, washer, Black_Screw, construction-vehicle; CC BY 4.0. Несмотря на название — **кранов как класса нет**. Не подходит.

### J24. CIVAD — Construction Industry Vision Alberta Dataset `[PARTIAL]`
- URL: https://www.iaarc.org/publications/2025_proceedings_of_the_42nd_isarc_montreal_canada/construction_industry_vision_alberta_dataset_civad_developing_a_comprehensive_object_detection_dataset_for_diverse_construction_applications.html (ISARC 2025)
- Сниппет: «over 50 classes with more than 86,905 images»; web scraping + open-source датасеты + собственные съёмки; полуавторазметка Grounded SAM / Grounding DINO. Лицензия и скачивание **не найдены** → `[UNVERIFIED]`, публично не выложен (по найденному).

### J25. GitHub miniexcav/Construction-Machines-Images-Dataset `[OK]`
- URL: https://github.com/miniexcav/Construction-Machines-Images-Dataset ; лицензия репо в API не указана → **НЕТ/СЕРО**.
- README: «223 image and their related label files in a YOLO format», только excavators, «downloaded from google images». План классов (tower cranes, backhoe loaders…) не реализован. Не подходит.

### J26. GitHub YUZ128pitt/OpenConstruction `[OK]`
- URL: https://github.com/YUZ128pitt/OpenConstruction — не датасет, а конфиги MMDetection2 для lifelong-обучения на ACID+SODA+MOCS («Please download the datasets from their official website under licensed permissions»). Весов в репо нет (size 32 КБ). Полезен как подтверждение списков классов ACID/SODA/MOCS.

### Уточнения к карточкам после дополнительной проверки
- **J01 SODA — скачивание** `[OK]`: на странице https://linjiarui.net/en/portfolio/2022-02-22-SODA-site-object-detection-dataset-for-deep-learning-in-construction есть ссылки SharePoint (hkustconnect-my.sharepoint.com, аккаунт ycdeng) и Baidu (pan.baidu.com/s/1vuWIOdBnb-U5F_JOxcZoBw, pwd 9cnh). Лицензия данных на странице **не указана**; итог прежний — СЕРО.
- **J16 APOCE — классы и лицензия** (почти подтверждено): два независимых сниппета (исходный проект https://universe.roboflow.com/wbcs-j9gyh/apoce-aerial-photographs-for-object-detection-of-construction-equipment-v3or7 и копия RF100-VL) дают **7 классов**: Bulldozer, Concrete Mixer, Dump Truck, Excavator, Lifting Equipment, Piling Machine, Tower Crane. Есть и правила разметки: «Piling machines have large vertical frameworks…» (размечать всю вертикальную конструкцию и базу), для башенного крана — «tower, jib, and counterweights». Лицензия RF100-VL в статье arXiv 2505.20612: «License: CC BY 4.0» `[OK]`. Проект есть в `rf100vl/assets/dataset_name_to_category.json` (домен «Aerial») `[OK]`. Итог: **ДА**.
- **J18 dikong** `[PARTIAL]`: сниппет — «licensed under CC BY 4.0», классы excavator и crane (плюс tower crane по более раннему сниппету). Полный список из 18 классов не получен.
- **J19 Tower Crane Component** `[PARTIAL]`: сниппет — 954 изображения, **4 класса** (среди них «Jib Mast» и «Tower Crane»), **CC BY 4.0**.
- **MOCS pile driver**: определение класса в доступных источниках (статья-абстракт, GSO-YOLO, страница лаборатории) **не найдено**. Входят ли туда роторные буровые установки — `[UNVERIFIED]`, до решения проверить по картинкам после скачивания.
- **Papers-with-Code**: `paperswithcode.com/datasets?q=construction` и `/dataset/mocs` с этой машины не отвечают (curl http=000) — не проверено.

## 4. Предобученные модели

### M03. yihong1120/Construction-Hazard-Detection (HF + GitHub) `[OK]`
- URL: https://huggingface.co/yihong1120/Construction-Hazard-Detection ; https://github.com/yihong1120/Construction-Hazard-Detection (348★, обновлён 2026-09-13)
- Лицензия: **AGPL-3.0** (HF tag и GitHub) → **СЕРО** (можно публиковать в открытом репо, но copyleft распространяется на сервис; для гос. внедрения нежелательно). Плюс Ultralytics YOLO сама AGPL-3.0.
- Классы (11): Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, **machinery**, utility pole, vehicle — техника одним классом.
- Метрики (box mAP50-95, 6 664 val-изобр., 61 458 инстансов): YOLO26n 0.4765, s 0.5996, m 0.5891, l 0.6482, x 0.6673. Веса: YOLO26 n–x (.pt/.onnx/TensorRT), YOLO11 n–x.
- Для нас: как «class-agnostic» детектор машин/людей для предразметки — да; для типов техники — нет.

### M01. uisikdag/yolo-v5-construction-machine-detection (HF) `[OK]`
- URL: https://huggingface.co/uisikdag/yolo-v5-construction-machine-detection ; файлы: best.pt, config.json, tfevents.
- Лицензия: тегов лицензии **нет** → **СЕРО**.
- Датасет: https://universe.roboflow.com/kfu-ye4kz/construction-management (классы `[UNVERIFIED]`); yolov5 7.0.7.
- Метрика в карточке: «mAP@0.5 = 0.884» (поле type: precision).

### M02. uisikdag/autotrain-detr-resnet-50-excavator-detection (HF) `[OK]`
- URL: https://huggingface.co/uisikdag/autotrain-detr-resnet-50-excavator-detection ; base facebook/detr-resnet-50; датасет uisikdag/excavators.
- Лицензия: не указана → **СЕРО**. Метрики: map 0.4249, map_50 0.5213, map_75 0.4799, map_medium 0.0574, map_large 0.4568. Только «excavator». Слабая модель, для нас бесполезна.

### Поиск HF API (2026-09-15) — отрицательный результат `[OK]`
- `api/models?search=` excavator / construction-machine / heavy-equipment / crane / construction-vehicle / construction-site: детекторов с башенными кранами, буровыми, бетононасосами **не найдено** (только M01, M02, VLM-файнтюны hnv2520/excavator_* для image-text, классификатор Bazaar/cv_construction_vehicle_identification, пустые репо).
- `api/datasets?search=` construction-equipment / heavy-equipment / backhoe → пусто; drilling-rig → только ImageNet offshore rig; construction-machine → PabloWang/constructionmachines (только README, данных нет).

### M04. Модели, привязанные к Roboflow-проектам `[PARTIAL]`
- В сниппетах у Tower Crane Component (J19), KlinterAI (J17), dikong (J18), Crane Construction (J23) есть «pre-trained model and API». Это модели, размещённые у Roboflow (инференс через Roboflow API/Inference SDK). Можно ли скачать веса и под какой лицензией — `[UNVERIFIED]` (страницы не открылись). Метрики не получены.

### M05. Модели из статей — весов нет `[OK]`
- GSO-YOLO (обучен на MOCS, https://arxiv.org/html/2407.00906v1): в тексте статьи **нет** ссылок на код и веса, по классам AP не приведены (есть только общие mAP50 / mAP50-95).
- FLE-YOLO (https://github.com/sugar-fifty-doge/FLE-YOLO): модель детекции крюка башенного крана, датасет J07. Классы «крюк», не кран.
- OpenConstruction (J26): только конфиги MMDetection2, весов в репозитории нет.

### Итог по моделям
**Нет ни одной открытой предобученной модели**, которая детектирует буровую установку, башенный кран, экскаватор-погрузчик, гусеничный кран, автобетононасос или копёр отдельными классами, со скачиваемыми весами и понятной лицензией (проверены HF API, GitHub, сниппеты Roboflow). Что реально есть:
- M03 (AGPL-3.0): один общий класс `machinery`/`vehicle`. Годится для поиска кандидатов при предразметке.
- M01 (без лицензии), M02 (слабый, только экскаватор): не использовать.
- Практический путь: самим дообучить детектор на наборе из §5. Для предразметки новых классов можно взять открытые open-vocabulary детекторы (Grounding DINO / OWLv2 / YOLO-World). В этой части их лицензии и качество на наших классах **не проверялись** `[UNVERIFIED]`.

## 5. Рекомендация: минимальный набор внешних данных под наши классы

Принцип: делаем **две сборки обучающих данных**. Веса модели «clean» можно публиковать в открытом репозитории. Модель «research» (с NC-данными) используем только для сравнения и предразметки; если публикуем, то с пометкой NC или после согласования с организаторами.

### 5.1. Качать первым, лицензионно чисто (сборка «clean»)
| # | Источник | Что даёт | Объём | Как скачать | Лицензионный риск |
|---|---|---|---|---|---|
| 1 | Kaggle xyzyxzzxy/construction-equipment (§2) | самосвал, экскаватор, автокран, миксер, погрузчики, каток, бульдозер и др., 17 классов | 17.5 ГБ, 19 982 изобр., YOLO txt | `kaggle datasets download -d xyzyxzzxy/construction-equipment` (нужен токен) | низкий (CC0). Учесть: только CCTV-кадры, мало ракурсов; для нас лучше прореживать серии (дубли кадров с одной камеры) |
| 2 | **APOCE** из RF100-VL | **башенный кран**, **piling machine** (буровая/копёр вместе), lifting equipment, самосвал, экскаватор, бульдозер, миксер. Съёмка с воздуха | 1.42 ГБ tar, ~930 изобр. | HF без авторизации: `huggingface-cli download LibreYOLO/rf100-vl apoce-aerial-photographs-for-object-detection-of-construction-equipment.tar --repo-type dataset` | низкий (в статье RF100-VL: «License: CC BY 4.0»), нужна атрибуция. Список классов подтверждён двумя сниппетами; после скачивания сверить с data.yaml |
| 3 | **Roboflow Tower Crane Component** | **башенный кран** (4 класса, в т.ч. Tower Crane, Jib Mast) | 954 изобр. | Roboflow Universe → Download (нужен бесплатный аккаунт / API key) | низкий по сниппету (CC BY 4.0). Перед использованием проверить лицензию на странице |
| 4 | **Roboflow KlinterAI Construction Dataset** | **буровая** (drilling rig, folded piling rig, CFA drill), backhoe/backactor, краны, самосвал, экскаватор | 700–922 изобр., 77 классов | Roboflow Universe (аккаунт) | низкий по сниппету (CC BY 4.0). 77 классов нужно свести к нашим (remap), примеров на класс мало |
| 5 | Roboflow dikong «drone inspection of construction» | башенный кран, кран, экскаватор (дрон) | 2 599 изобр. | Roboflow Universe (аккаунт) | низкий по сниппету (CC BY 4.0). Полный список классов не проверен |
| 6 | (опц.) RF100 Excavators | экскаватор, самосвал, фронтальный погрузчик | 2 655 изобр. | HF `LibreYOLO/excavators-czvg9` (YOLO) | низкий (CC BY 4.0). Добавлять только если Kaggle-данных по этим классам не хватит |

Объём сборки «clean» без Kaggle: около 1.5 ГБ плюс три небольших Roboflow-экспорта (размер `[UNVERIFIED]`). Башенные краны покрыты неплохо. Буровые и копры покрыты слабо: сотни кадров в сумме, вид с земли только у KlinterAI.

### 5.2. Вторая очередь, СЕРО (сборка «research», CC BY-NC)
| # | Источник | Зачем | Объём | Как скачать | Риск |
|---|---|---|---|---|---|
| 7 | **MOCS** | единственный крупный источник **автобетононасосов** (pump truck) и **pile driver**, много башенных кранов и автокранов, ракурсы похожи на наши | 41 668 изобр.; HF-зеркало images.rar 9.7 ГБ + labels.rar 7 МБ | официально: анкета https://www.wjx.cn/vm/wWGwSOc.aspx; или зеркало `AmiyaChan/mocs_yolo` | **средний**: CC BY-NC 4.0. Тег MIT у зеркала юридически ничего не меняет |
| 8 | AIDCON | экскаватор-погрузчик на дрон-кадрах | 2 155 изобр. | форма-запрос ai2lab.org | средний/высокий: CC BY-NC 4.0, «research purposes only» |
| 9 | ACID | экскаватор-погрузчик, башенный кран, автокран | 10 000 изобр. | Google-форма, ссылку присылают в течение недели | **высокий**: ToU запрещает распространять и публиковать «intellectual contents». Не рекомендуется |

### 5.3. Не использовать
Tower-crane-dataset (J07: нет лицензии, это крюки), arh-df (J09: GPL 2), Datacluster (J13, J21: вендорские ограничения), Kaggle-наборы с лицензией Unknown (J22), Transzvuk (J12), miniexcav (J25), неофициальные Roboflow-копии ACID и SODA (нарушают исходные условия).

### 5.4. Порядок действий
1. Скачать APOCE (без авторизации, 1.42 ГБ) и сверить классы в data.yaml.
2. Завести Roboflow-аккаунт, открыть J19/J17/J18 в браузере вручную, подтвердить лицензию и классы, экспортировать в YOLOv8.
3. Свести классы к таксономии проекта: `tower_crane`, `drilling_rig`, `pile_driver`, `crawler_crane`, `mobile_crane`, `backhoe_loader`, `concrete_pump`, `dump_truck`, `excavator`, …
4. Параллельно отправить заявку на MOCS: ответ приходит не сразу, а зеркало весит 9.7 ГБ.
5. Всё внешнее — только для обучения. **Валидацию делать только на наших снимках Москвы.**

## 6. Классы, для которых открытых данных нет → нужна своя разметка

| Класс | Что нашлось | Вывод |
|---|---|---|
| **Гусеничный кран** | Ни в одном датасете нет отдельного класса. Есть только общие `crane` (arh-df, KlinterAI, dikong) и `lifting equipment` (APOCE); что в них входят гусеничные краны — `[UNVERIFIED]` | **Полностью своя разметка** |
| **Буровая установка** (Bauer/Liebherr/Soilmec-подобные, с высокой мачтой; буронабивные сваи, стена в грунте) | KlinterAI: drilling rig / piling rig / CFA, сотни кадров на 77 классов. APOCE: `piling machine`, вид с воздуха, вместе с копрами. MOCS: `pile driver`, NC, что именно входит — не проверено. Отдельного крупного датасета нет | **Своя разметка обязательна**. Внешние данные — только для дообучения |
| **Копёр / вибропогружатель шпунта** | В открытых данных нигде не отделён от буровой (`pile driver`, `piling machine`) | **Своя разметка**, или объединить с буровой в класс `piling_rig`, если по регламенту этапов работ различать их не нужно |
| **Грейфер для «стены в грунте»** | Не найдено нигде | Своя разметка, если нужен для этапов работ |
| **Автобетононасос** | Только MOCS `pump truck` (NC). В AIDCON — внутри класса «other» (NC, по сниппету). С чистой лицензией — нет | **Своя разметка** для «clean»-модели; MOCS — только в сборке «research» |
| **Экскаватор-погрузчик** | ACID и AIDCON — NC/ToU. KlinterAI `Backhoe/Backactor` неоднозначен. Kaggle `jcb-image-dataset` без bbox | **Своя разметка** для «clean»-модели |
| **Башенный кран** | Есть с чистой лицензией: APOCE, Tower Crane Component, dikong, KMUTT | Внешних данных достаточно для старта. Дообучить на наших кадрах: зима, дальний план, мелкие краны |
| Самосвал, экскаватор, автокран, миксер, бульдозер, каток, погрузчик | Kaggle CC0 и RF100 (CC BY 4.0) | Своя разметка нужна только для валидации |

Практически: 100 выданных снимков — это валидационный набор. Для перечисленных выше «пустых» классов нужно размечать дополнительные собственные фото или кадры из открытых источников с подходящей лицензией, с предразметкой через M03 / open-vocabulary детектор и ручной проверкой. Сколько экземпляров на класс нужно, в этой части не исследовалось.
