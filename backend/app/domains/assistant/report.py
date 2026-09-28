"""Чистая функция построения отчёта для ассистента из данных assessment."""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.domains.assessment.schemas import DeviationRead, SiteSummaryRead, StageStatusRead
from app.domains.observation.models import Observation
from app.domains.schedule.models import ScheduleStage

SITE_LABEL: str = "p1"
MAX_STAGES: int = 300
MAX_TEXT: int = 300


def clean_text(value: str | None, limit: int = MAX_TEXT) -> str | None:
    """Очистить текст: удалить переносы, табы, управляющие символы и обрезать по лимиту.

    Args:
        value: Исходный текст или None.
        limit: Максимальная длина результата.

    Returns:
        Очищенный текст или None если на входе None.
    """
    if value is None:
        return None

    # Удаляем управляющие символы (кроме пробела)
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)

    # Заменяем табы на пробелы
    cleaned = cleaned.replace("\t", " ")

    # Сворачиваем множественные пробелы в один
    cleaned = re.sub(r" +", " ", cleaned)

    # Обрезаем по началу и концу
    cleaned = cleaned.strip()

    # Если текст длиннее лимита, обрезаем и добавляем многоточие
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"

    return cleaned


@dataclass(frozen=True)
class ReportInput:
    """Входные данные для построения отчёта."""

    stages: Sequence[ScheduleStage]
    statuses: Sequence[StageStatusRead]
    deviations: Sequence[DeviationRead]
    summary: SiteSummaryRead
    observations: Sequence[Observation]


@dataclass(frozen=True)
class BuiltReport:
    """Собранный отчёт с информацией о соответствии этапов."""

    report: dict
    stage_ids: dict[int, uuid.UUID]


def build_report(data: ReportInput) -> BuiltReport:
    """Построить отчёт для ассистента из данных assessment.

    Args:
        data: Входные данные (этапы, статусы, отклонения, сводка, наблюдения).

    Returns:
        BuiltReport с полным отчётом и маппингом stage_no -> stage_id.
    """
    # Сортируем этапы по position
    sorted_stages = sorted(data.stages, key=lambda s: s.position)

    # Усекаем если больше MAX_STAGES
    stages_truncated = len(sorted_stages) > MAX_STAGES
    truncated_stages = sorted_stages[:MAX_STAGES]

    # Строим маппинг stage_id -> StageStatusRead для быстрого поиска
    statuses_by_stage_id = {s.stage_id: s for s in data.statuses}

    # Строим маппинг stage_id -> stage_no (1-based)
    stage_id_to_no = {stage.id: i + 1 for i, stage in enumerate(truncated_stages)}

    # Строим stage_ids маппинг (stage_no -> stage_id)
    stage_ids = {i + 1: stage.id for i, stage in enumerate(truncated_stages)}

    # Строим отчёты по этапам
    stages_list = []
    for stage_no, stage in enumerate(truncated_stages, start=1):
        status = statuses_by_stage_id.get(stage.id)

        stage_report = {
            "stage_ref": f"этап {stage_no}",
            "stage_no": stage_no,
            "stage_name": clean_text(stage.name),
            "planned_start": stage.planned_start.isoformat() if stage.planned_start else None,
            "planned_end": stage.planned_end.isoformat() if stage.planned_end else None,
            "status": status.status if status else "not_started",
            "delay_days": status.delay_days if status else None,
            "confidence": status.confidence if status else None,
            "confidence_reason": clean_text(status.confidence_reason) if status else None,
        }
        stages_list.append(stage_report)

    # Строим отчёты по отклонениям (alerts)
    alerts_list = []
    for deviation in data.deviations:
        # Определяем stage_ref если этап есть в списке
        stage_ref = None
        if deviation.stage_id is not None and deviation.stage_id in stage_id_to_no:
            stage_no = stage_id_to_no[deviation.stage_id]
            stage_ref = f"этап {stage_no}"

        alert = {
            "type": deviation.type,
            "severity": deviation.severity,
            "is_hypothesis": deviation.is_hypothesis,
            "confidence": deviation.confidence,
            "stage_ref": stage_ref,
            "period_start": deviation.period_start.isoformat(),
            "period_end": deviation.period_end.isoformat(),
            "expected": clean_text(deviation.expected),
            "observed": clean_text(deviation.observed),
            "limits": clean_text(deviation.limits_text),
        }
        alerts_list.append(alert)

    # Определяем as_of (дата последнего вычисленного статуса)
    as_of = None
    if data.statuses:
        computed_dates = [s.computed_at.date() for s in data.statuses if s.computed_at is not None]
        if computed_dates:
            as_of = max(computed_dates).isoformat()

    # Определяем last_observation (максимальная дата наблюдения)
    last_observation = None
    if data.observations:
        observed_dates = [o.observed_on for o in data.observations]
        if observed_dates:
            last_observation = max(observed_dates).isoformat()

    # Собираем отчёт по сайту
    site_report = {
        "site_id": SITE_LABEL,
        "as_of": as_of,
        "observations": len(data.observations),
        "last_observation": last_observation,
        "summary": {
            "verdict": data.summary.verdict,
            "delay_days_min": data.summary.delay_days_min,
            "delay_days_max": data.summary.delay_days_max,
            "critical_count": data.summary.critical_count,
            "attention_count": data.summary.attention_count,
        },
        "stages": stages_list,
        "alerts": alerts_list,
    }

    # Собираем полный отчёт
    report = {
        "meta": {
            "sites": 1,
            "stages": len(truncated_stages),
            "stages_truncated": stages_truncated,
            "source": "assessment",
        },
        "sites": [site_report],
    }

    return BuiltReport(report=report, stage_ids=stage_ids)
