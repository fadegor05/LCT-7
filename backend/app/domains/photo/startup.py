"""Стартовые проверки для photo домена."""

import asyncio
import logging

from app.adapters.ml.base import DetectorClient
from app.domains.methodology.catalog import EquipmentCatalog

logger = logging.getLogger(__name__)


async def check_detector_classes(detector: DetectorClient, catalog: EquipmentCatalog) -> None:
    """Проверить соответствие классов модели детектора каталогу оборудования.

    Никогда не выбрасывает исключение. Защита от таймаутов на 5 секунд.

    Если info вернёт None, логирует info-сообщение и заканчивает.

    Иначе сравнивает set(info.class_names) с кодами каталога:
    - Выписывает unknown-to-catalog классы
    - Выписывает non-coarse каталога коды, отсутствующие в модели
    - Логирует одно warning, если есть какие-либо различия

    Args:
        detector: DetectorClient для получения информации о модели
        catalog: EquipmentCatalog для сравнения кодов
    """
    try:
        # Защита от таймаутов: max 5 секунд
        info = await asyncio.wait_for(detector.info(), timeout=5)
    except TimeoutError:
        logger.warning("Детектор не ответил в течение 5 секунд при проверке классов")
        return
    except Exception as e:
        logger.warning("Ошибка при получении информации о детекторе: %s", e)
        return

    if info is None:
        logger.info("ML недоступен или отключен, пропускаем проверку классов")
        return

    # Получаем классы из модели
    model_classes = set(info.class_names)

    # Получаем коды каталога (все коды, включая coarse)
    catalog_items = await catalog.all()
    all_catalog_codes = {item.code for item in catalog_items}
    non_coarse_codes = {item.code for item in catalog_items if not item.is_coarse}

    # Находим различия
    # unknown = классы в модели, которых нет в каталоге (вообще)
    unknown_classes = model_classes - all_catalog_codes
    # missing = non-coarse коды каталога, которых нет в модели
    missing_codes = non_coarse_codes - model_classes

    # Логируем warning если есть различия
    if unknown_classes or missing_codes:
        message_parts = []
        if unknown_classes:
            message_parts.append(f"неизвестные классы в модели: {sorted(unknown_classes)}")
        if missing_codes:
            message_parts.append(f"коды каталога отсутствуют в модели: {sorted(missing_codes)}")

        logger.warning("Несоответствие классов детектора: %s", "; ".join(message_parts))
