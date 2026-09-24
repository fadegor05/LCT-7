"""Бизнес-логика графика выполнения работ."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedule.models import DatesSource, Schedule, ScheduleImportIssue, ScheduleStage
from app.domains.schedule.parser import ScheduleFormatError, ScheduleParser
from app.domains.schedule.repository import ScheduleRepository
from app.domains.schedule.schemas import IssueRead, ScheduleReport, StageDatesUpdate, StageRead
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


class ScheduleService:
    """Бизнес-логика графика выполнения работ."""

    def __init__(
        self,
        repository: ScheduleRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        parser: ScheduleParser,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._parser = parser

    async def _build_report(self, schedule: Schedule) -> ScheduleReport:
        """Построить ScheduleReport из Schedule с загрузкой связанных данных.

        Helper для import_schedule и get_schedule.
        """
        loaded_stages = await self._repository.list_stages(schedule.id)
        loaded_issues = await self._repository.list_issues(schedule.id)

        stages_with_dates = sum(
            1
            for stage in loaded_stages
            if stage.planned_start is not None and stage.planned_end is not None
        )
        stages_without_dates = len(loaded_stages) - stages_with_dates

        return ScheduleReport(
            id=schedule.id,
            site_id=schedule.site_id,
            source_filename=schedule.source_filename or "",
            imported_at=schedule.imported_at,
            rows_total=schedule.rows_total or 0,
            rows_parsed=schedule.rows_parsed or 0,
            stages_with_dates=stages_with_dates,
            stages_without_dates=stages_without_dates,
            stages=[StageRead.model_validate(stage) for stage in loaded_stages],
            issues=[IssueRead.model_validate(issue) for issue in loaded_issues],
        )

    async def import_schedule(
        self, site_id: uuid.UUID, filename: str, content: bytes
    ) -> ScheduleReport:
        """Импортировать график из файла.

        Парсит файл, удаляет старый график (если был), создаёт новый с этапами и ошибками.
        Одна транзакция: delete_by_site, create Schedule, add stages, add issues, commit.

        Args:
            site_id: ID сайта
            filename: имя файла
            content: содержимое файла

        Returns:
            ScheduleReport с информацией об импорте

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(422) если ошибка формата файла
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Парсим файл
        try:
            parse_result = self._parser.parse(filename, content)
        except ScheduleFormatError as e:
            raise AppError(str(e), status_code=422) from e

        # Одна транзакция: удаляем старый график полностью, создаём новый
        await self._repository.delete_by_site(site_id)

        # Создаём новый график с fresh id и imported_at
        schedule = Schedule(
            site_id=site_id,
            source_filename=filename,
            rows_total=parse_result.rows_total,
            rows_parsed=len(parse_result.rows),
        )
        await self._repository.add(schedule)

        # Добавляем этапы (с positions 1..N, dates_source='file')
        stages = [
            ScheduleStage(
                schedule_id=schedule.id,
                name=row.name,
                position=idx + 1,
                planned_start=row.start,
                planned_end=row.end,
                dates_source=DatesSource.FILE.value,
            )
            for idx, row in enumerate(parse_result.rows)
        ]
        if stages:
            await self._repository.add_stages(stages)

        # Добавляем ошибки
        issues = [
            ScheduleImportIssue(
                schedule_id=schedule.id,
                row_number=issue.row_number,
                raw_row=issue.raw_row,
                reason=issue.reason,
            )
            for issue in parse_result.issues
        ]
        if issues:
            await self._repository.add_issues(issues)

        # Коммитим
        await self._session.commit()

        # Строим отчёт
        return await self._build_report(schedule)

    async def get_schedule(self, site_id: uuid.UUID) -> ScheduleReport:
        """Получить отчёт о графике.

        Args:
            site_id: ID сайта

        Returns:
            ScheduleReport

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(404) если график не загружен
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Получаем график
        schedule = await self._repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)

        # Строим отчёт
        return await self._build_report(schedule)

    async def update_stage_dates(
        self, site_id: uuid.UUID, stage_id: uuid.UUID, data: StageDatesUpdate
    ) -> ScheduleStage:
        """Обновить даты этапа.

        Применяет только поля, переданные в data.model_fields_set.
        Проверяет, что если оба поля установлены, то end >= start.
        Если ошибка - не коммитит.
        Устанавливает dates_source='manual'.

        Args:
            site_id: ID сайта
            stage_id: ID этапа
            data: StageDatesUpdate с новыми датами

        Returns:
            Обновлённый ScheduleStage

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(404) если график не загружен или этап не найден
            AppError(422) если end < start
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Получаем график
        schedule = await self._repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("Этап не найден", status_code=404)

        # Получаем этап
        stage = await self._repository.get_stage(schedule.id, stage_id)
        if stage is None:
            raise AppError("Этап не найден", status_code=404)

        # Получаем установленные поля
        update_dict = data.model_dump(exclude_unset=True)

        # Подготавливаем новые значения (результирующие значения после merge)
        new_start = update_dict.get("planned_start", stage.planned_start)
        new_end = update_dict.get("planned_end", stage.planned_end)

        # Проверяем, что РЕЗУЛЬТИРУЮЩИЕ значения валидны (end >= start)
        # Проверяем даже если обновлено только одно поле
        if new_start is not None and new_end is not None and new_end < new_start:
            raise AppError("Дата окончания не может быть раньше даты начала", status_code=422)

        # Применяем только установленные поля
        if "planned_start" in update_dict:
            stage.planned_start = new_start
        if "planned_end" in update_dict:
            stage.planned_end = new_end

        # Устанавливаем dates_source='manual'
        stage.dates_source = DatesSource.MANUAL.value

        # Коммитим
        await self._session.commit()

        return stage

    async def get_stage_window(self, stage_id: uuid.UUID) -> tuple[date | None, date | None]:
        """Получить окно дат этапа (start, end).

        Контракт для других доменов, без гварда.

        Args:
            stage_id: ID этапа

        Returns:
            (planned_start, planned_end)

        Raises:
            AppError(404) если этап не найден
        """
        stage = await self._session.get(ScheduleStage, stage_id)
        if stage is None:
            raise AppError("Этап не найден", status_code=404)

        return (stage.planned_start, stage.planned_end)
