"""Бизнес-логика графика выполнения работ."""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.assistant import AssistantError
from app.adapters.ml.schedule_llm import LlmScheduleResult, ScheduleLlmClient
from app.domains.methodology.materializer import NO_KIT_REASON
from app.domains.methodology.models import MethodologyRule
from app.domains.methodology.recalculator import StatusRecalculator
from app.domains.schedule.grouping import group_works
from app.domains.schedule.models import (
    DatesSource,
    ParseMethod,
    ParseMode,
    Schedule,
    ScheduleImportIssue,
    ScheduleStage,
)
from app.domains.schedule.parser import (
    ParsedIssue,
    ParsedRow,
    ParseResult,
    ScheduleFormatError,
    ScheduleParser,
    clean_stage_name,
)
from app.domains.schedule.repository import ScheduleRepository
from app.domains.schedule.schemas import IssueRead, ScheduleReport, StageDatesUpdate, StageRead
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


def _from_llm(result: LlmScheduleResult) -> ParseResult:
    """Ответ LLM → ParseResult, с той же проверкой порядка дат, что у встроенного парсера."""
    rows: list[ParsedRow] = []
    issues = [ParsedIssue(row_number=i.row, raw_row=i.raw, reason=i.reason) for i in result.issues]
    for item in result.rows:
        if item.start and item.end and item.end < item.start:
            issues.append(
                ParsedIssue(
                    row_number=item.row,
                    raw_row=item.name,
                    reason="Дата окончания раньше даты начала",
                )
            )
            continue
        name = clean_stage_name(item.name)
        rows.append(ParsedRow(name=name, start=item.start, end=item.end))
    issues.sort(key=lambda i: i.row_number)
    return ParseResult(rows=rows, issues=issues, rows_total=len(rows) + len(issues))


class ScheduleService:
    """Бизнес-логика графика выполнения работ."""

    def __init__(
        self,
        repository: ScheduleRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        parser: ScheduleParser,
        recalculator: StatusRecalculator,
        llm: ScheduleLlmClient,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._parser = parser
        self._recalculator = recalculator
        self._llm = llm

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
            parse_method=schedule.parse_method,
            stages_with_dates=stages_with_dates,
            stages_without_dates=stages_without_dates,
            stages=[StageRead.model_validate(stage) for stage in loaded_stages],
            issues=[IssueRead.model_validate(issue) for issue in loaded_issues],
        )

    async def _parse_with_llm(self, filename: str, content: bytes) -> ParseResult:
        """Разобрать файл моделью: таблица «как есть» → LLM → проверенные строки.

        Raises:
            ScheduleFormatError: файл нечитаем или пуст
            AssistantError: LLM недоступна, не ответила или отвергла запрос
        """
        grid = self._parser.read_grid(filename, content)
        return _from_llm(await self._llm.parse(grid))

    async def _parse(
        self, filename: str, content: bytes, mode: ParseMode
    ) -> tuple[ParseResult, ParseMethod]:
        """Разобрать файл в выбранном режиме.

        builtin — только встроенный парсер; llm — только модель; auto — встроенный,
        а если он не нашёл в файле ни одной работы, то модель. Если в auto не вышло
        и у модели, пользователь видит причину отказа встроенного парсера (она
        точнее говорит, что не так с файлом), плюс причину отказа модели.
        """
        try:
            if mode is ParseMode.BUILTIN:
                return self._parser.parse(filename, content), ParseMethod.BUILTIN

            if mode is ParseMode.LLM:
                result = await self._parse_with_llm(filename, content)
                if not result.rows and not result.issues:
                    raise AppError("Модель не нашла в файле ни одной работы", status_code=422)
                return result, ParseMethod.LLM

            builtin: ParseResult | None = None
            reason: str
            try:
                builtin = self._parser.parse(filename, content)
                reason = "во встроенном разборе не нашлось ни одной работы"
            except ScheduleFormatError as e:
                reason = str(e)
            if builtin is not None and builtin.rows:
                return builtin, ParseMethod.BUILTIN

            try:
                result = await self._parse_with_llm(filename, content)
            except ScheduleFormatError:
                # Файл нечитаем даже как «сырая» таблица — LLM тут не поможет
                if builtin is None:
                    raise
                return builtin, ParseMethod.BUILTIN
            except AssistantError as e:
                if builtin is not None:
                    return builtin, ParseMethod.BUILTIN
                raise AppError(
                    f"{reason}. Разбор моделью тоже не удался: {e.message}", status_code=422
                ) from e
            if not result.rows:
                if builtin is not None:
                    return builtin, ParseMethod.BUILTIN
                raise AppError(
                    f"{reason}. Модель тоже не нашла в файле ни одной работы", status_code=422
                )
            return result, ParseMethod.LLM
        except ScheduleFormatError as e:
            raise AppError(str(e), status_code=422) from e
        except AssistantError as e:
            raise AppError(e.message, e.status_code, code=e.code) from e

    async def import_schedule(
        self,
        site_id: uuid.UUID,
        filename: str,
        content: bytes,
        mode: ParseMode = ParseMode.AUTO,
    ) -> ScheduleReport:
        """Импортировать график из файла.

        Парсит файл, удаляет старый график (если был), создаёт новый с этапами и ошибками.
        Одна транзакция: delete_by_site, create Schedule, add stages, add issues, commit.

        Args:
            site_id: ID сайта
            filename: имя файла
            content: содержимое файла
            mode: режим разбора (auto — встроенный, при неудаче LLM; llm; builtin)

        Returns:
            ScheduleReport с информацией об импорте

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(422) если ошибка формата файла
            AppError(503/504) если выбран LLM-разбор, а модель недоступна
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Парсим файл (LLM-вызов — до транзакции: старый график не трогаем, пока не разобрали новый)
        parse_result, method = await self._parse(filename, content, mode)

        # Одна транзакция: удаляем старый график полностью, создаём новый
        await self._repository.delete_by_site(site_id)

        # Создаём новый график с fresh id и imported_at
        schedule = Schedule(
            site_id=site_id,
            source_filename=filename,
            rows_total=parse_result.rows_total,
            rows_parsed=len(parse_result.rows),
            parse_method=method.value,
        )
        await self._repository.add(schedule)

        # Добавляем этапы (с positions 1..N, dates_source='file'): работы одного пункта
        # графика («2.1», «2.2») — один этап с окном от первой до последней работы
        stages = [
            ScheduleStage(
                schedule_id=schedule.id,
                name=group.name,
                position=idx + 1,
                planned_start=group.start,
                planned_end=group.end,
                work_names=[w.name for w in group.works],
                dates_source=DatesSource.FILE.value,
            )
            for idx, group in enumerate(group_works(parse_result.rows))
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

        # Коммитим (может поднять IntegrityError при гонке)
        try:
            await self._session.commit()
        except IntegrityError as e:
            await self._session.rollback()
            raise AppError(
                "График этой стройки уже импортируется, повторите запрос",
                status_code=409,
            ) from e

        # Строим отчёт до пересчёта: при ошибке он откатывает сессию, и ORM-объекты протухают
        report = await self._build_report(schedule)

        # Этапы с наступившим окном сразу получают статус («не наблюдалось», пока нет
        # кадров). Без пересчёта обзор показывал бы их «не начатыми» до первого наблюдения.
        await self._recalculator.recalculate(site_id)

        return report

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
        Если нет изменений - не коммитит и не меняет dates_source.
        Если есть изменения - устанавливает dates_source='manual'.

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

        # Если нет установленных полей - no-op, просто вернуть stage
        if not update_dict:
            return stage

        # Подготавливаем новые значения (результирующие значения после merge)
        new_start = update_dict.get("planned_start", stage.planned_start)
        new_end = update_dict.get("planned_end", stage.planned_end)

        # Проверяем, что РЕЗУЛЬТИРУЮЩИЕ значения валидны (end >= start)
        # Проверяем даже если обновлено только одно поле
        if new_start is not None and new_end is not None and new_end < new_start:
            raise AppError("Дата окончания не может быть раньше даты начала", status_code=422)

        # Проверяем, есть ли реальные изменения
        has_actual_changes = False

        if "planned_start" in update_dict:
            if new_start != stage.planned_start:
                has_actual_changes = True
            stage.planned_start = new_start

        if "planned_end" in update_dict:
            if new_end != stage.planned_end:
                has_actual_changes = True
            stage.planned_end = new_end

        # Устанавливаем dates_source='manual' только если есть реальные изменения
        if has_actual_changes:
            stage.dates_source = DatesSource.MANUAL.value
            # Коммитим только если есть изменения
            await self._session.commit()
            # Триггер пересчёта статусов этапов и отклонений
            await self._recalculator.recalculate(site_id)
            # Сбой пересчёта глушится с rollback, и этап протухает — перечитываем его
            await self._session.refresh(stage)

        return stage

    async def merge_stages(
        self, site_id: uuid.UUID, stage_ids: Sequence[uuid.UUID]
    ) -> ScheduleReport:
        """Объединить соседние этапы графика в первый из них.

        Название и id остаются у первого этапа, окно — объединение дат всех. Правило
        методики первого этапа получает наборы техники остальных (одинаковые наборы
        не дублируются); проверяемым становится, если проверяемым был любой из них.
        Правила и этапы остальных удаляются, порядок этапов перенумеровывается.

        Args:
            site_id: ID сайта
            stage_ids: ID объединяемых этапов (соседних, не меньше двух разных)

        Returns:
            ScheduleReport после объединения и пересчёта статусов

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю, нет графика
                или этап не найден
            AppError(422) если этапы не разные или не соседние
        """
        await self._guard.require(site_id)

        schedule = await self._repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)
        schedule_id = schedule.id

        distinct = set(stage_ids)
        if len(distinct) < 2:
            raise AppError("Выберите хотя бы два разных этапа", status_code=422)

        stages = await self._repository.list_stages(schedule_id)
        chosen = sorted((s for s in stages if s.id in distinct), key=lambda s: s.position)
        if len(chosen) != len(distinct):
            raise AppError("Этап не найден", status_code=404)
        positions = [s.position for s in chosen]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            raise AppError("Объединять можно только соседние этапы", status_code=422)

        target, rest = chosen[0], chosen[1:]
        rest_ids = [s.id for s in rest]

        # Методика: правило первого этапа (создаём, если его ещё не материализовали)
        target_rules = await self._repository.list_rules_of_stages([target.id])
        if target_rules:
            target_rule = target_rules[0]
        else:
            target_rule = await self._repository.add_rule(
                MethodologyRule(
                    site_id=site_id,
                    stage_id=target.id,
                    is_verifiable=False,
                    unverifiable_reason=NO_KIT_REASON,
                )
            )
        rest_rules = await self._repository.list_rules_of_stages(rest_ids)
        stage_position = {s.id: s.position for s in chosen}
        rest_rules = [
            r
            for _, r in sorted(
                ((stage_position[r.stage_id], r) for r in rest_rules if r.stage_id is not None),
                key=lambda pair: pair[0],
            )
        ]
        rule_order = {r.id: i for i, r in enumerate(rest_rules)}

        target_sets = await self._repository.list_sets_of_rules([target_rule.id])
        rest_sets = sorted(
            await self._repository.list_sets_of_rules([r.id for r in rest_rules]),
            key=lambda s: (rule_order[s.rule_id], s.position),
        )
        requirements = await self._repository.list_requirements_of_sets(
            [s.id for s in [*target_sets, *rest_sets]]
        )
        signature_of: dict[uuid.UUID, set[tuple]] = {}
        for req in requirements:
            signature_of.setdefault(req.set_id, set()).add(
                (
                    req.equipment_type_id,
                    req.obligation,
                    req.min_count,
                    req.gesn_code,
                    req.source_note,
                )
            )

        seen = {frozenset(signature_of.get(s.id, set())) for s in target_sets}
        next_position = max((s.position for s in target_sets), default=-1) + 1
        for equipment_set in rest_sets:
            key = frozenset(signature_of.get(equipment_set.id, set()))
            if key in seen:
                continue
            seen.add(key)
            equipment_set.rule_id = target_rule.id
            equipment_set.position = next_position
            next_position += 1
        await self._session.flush()
        await self._repository.delete_rules([r.id for r in rest_rules])

        rest_verifiable = any(r.is_verifiable for r in rest_rules)
        if not target_rule.is_verifiable and rest_verifiable:
            target_rule.is_verifiable = True
            target_rule.unverifiable_reason = None

        # Этап: окно — объединение дат, «вручную», если хоть один правили вручную
        target.planned_start = min(
            (s.planned_start for s in chosen if s.planned_start), default=None
        )
        target.planned_end = max((s.planned_end for s in chosen if s.planned_end), default=None)
        if any(s.dates_source == DatesSource.MANUAL.value for s in chosen):
            target.dates_source = DatesSource.MANUAL.value
        target.work_names = [name for s in chosen for name in (s.work_names or [s.name])]
        for stage in rest:
            await self._session.delete(stage)
        for number, stage in enumerate((s for s in stages if s.id not in rest_ids), start=1):
            stage.position = number

        await self._session.commit()
        # Пересчёт статусов — тот же триггер, что после правки дат этапа
        await self._recalculator.recalculate(site_id)
        # Отчёт строим заново: сбой пересчёта откатывает сессию и протухает ORM-объекты
        fresh = await self._repository.get_by_site(site_id)
        if fresh is None:
            raise AppError("График не загружен", status_code=404)
        return await self._build_report(fresh)

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
