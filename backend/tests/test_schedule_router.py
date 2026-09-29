"""HTTP-контракт графика выполнения работ."""

import io
import uuid
from datetime import date

import openpyxl
import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.schedule.models import Schedule, ScheduleImportIssue, ScheduleStage
from app.domains.user.service import UserService


async def seed_stand_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def make_csv_bytes(content: str) -> bytes:
    """Создать CSV как bytes с корректной кодировкой."""
    return content.encode("utf-8")


async def test_post_import_csv_with_201(client: AsyncClient, container: AsyncContainer) -> None:
    """POST /sites/{site_id}/schedule/import с CSV возвращает 201 и ScheduleReport."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Создаём CSV с двумя этапами
    csv_content = make_csv_bytes(
        "name,start,end\nФундамент,2024-01-01,2024-01-10\nСтены,2024-01-11,2024-01-20\n"
    )

    # Импортируем график
    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["site_id"] == site_id
    assert data["source_filename"] == "schedule.csv"
    assert data["rows_total"] == 2
    assert data["rows_parsed"] == 2
    assert data["stages_with_dates"] == 2
    assert data["stages_without_dates"] == 0
    assert len(data["stages"]) == 2
    assert len(data["issues"]) == 0


async def test_post_import_xlsx_with_201(client: AsyncClient, container: AsyncContainer) -> None:
    """POST /sites/{site_id}/schedule/import с XLSX возвращает 201 и ScheduleReport."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Создаём XLSX в памяти
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "name"
    ws["B1"] = "start"
    ws["C1"] = "end"
    ws["A2"] = "Фундамент"
    ws["B2"] = date(2024, 1, 1)
    ws["C2"] = date(2024, 1, 10)
    ws["A3"] = "Стены"
    ws["B3"] = date(2024, 1, 11)
    ws["C3"] = date(2024, 1, 20)

    # Сохраняем в bytes
    bytes_io = io.BytesIO()
    wb.save(bytes_io)
    xlsx_content = bytes_io.getvalue()

    # Импортируем график
    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={
            "file": (
                "schedule.xlsx",
                xlsx_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["rows_parsed"] == 2
    assert len(data["stages"]) == 2


async def test_get_schedule_returns_report(client: AsyncClient, container: AsyncContainer) -> None:
    """GET /sites/{site_id}/schedule возвращает ScheduleReport."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes(
        "name,start,end\nФундамент,2024-01-01,2024-01-10\nСтены,2024-01-11,2024-01-20\n"
    )
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    schedule_id = import_resp.json()["id"]

    # Получаем график
    response = await client.get(f"/sites/{site_id}/schedule")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == schedule_id
    assert len(data["stages"]) == 2


async def test_get_schedule_before_import_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET /sites/{site_id}/schedule до импорта возвращает 404."""
    await seed_stand_user(container)

    # Создаём сайт без графика
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Получаем график
    response = await client.get(f"/sites/{site_id}/schedule")

    assert response.status_code == 404
    assert "График не загружен" in response.json()["detail"]


async def test_reimport_replaces_schedule(client: AsyncClient, container: AsyncContainer) -> None:
    """Повторный импорт заменяет график без дубликатов."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content1 = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp1 = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content1, "text/csv")},
    )
    schedule_id1 = import_resp1.json()["id"]
    assert import_resp1.json()["rows_parsed"] == 1

    # Переимпортируем с другим содержимым
    csv_content2 = make_csv_bytes(
        "name,start,end\n"
        "Фундамент,2024-01-01,2024-01-10\n"
        "Стены,2024-01-11,2024-01-20\n"
        "Кровля,2024-01-21,2024-01-30\n"
    )
    import_resp2 = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content2, "text/csv")},
    )
    schedule_id2 = import_resp2.json()["id"]
    assert import_resp2.json()["rows_parsed"] == 3

    # Новый график должен иметь новый ID
    assert schedule_id2 != schedule_id1

    # Получаем график
    get_resp = await client.get(f"/sites/{site_id}/schedule")
    assert len(get_resp.json()["stages"]) == 3


async def test_patch_stage_dates_happy_path(client: AsyncClient, container: AsyncContainer) -> None:
    """PATCH /sites/{site_id}/schedule/stages/{stage_id} обновляет даты."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    stage_id = import_resp.json()["stages"][0]["id"]

    # Обновляем даты
    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/{stage_id}",
        json={"planned_start": "2024-01-02", "planned_end": "2024-01-11"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["planned_start"] == "2024-01-02"
    assert data["planned_end"] == "2024-01-11"
    assert data["dates_source"] == "manual"


async def test_patch_stage_dates_end_before_start_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH со start > end возвращает 422."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    stage_id = import_resp.json()["stages"][0]["id"]

    # Пытаемся установить end < start
    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/{stage_id}",
        json={"planned_start": "2024-01-10", "planned_end": "2024-01-05"},
    )

    assert response.status_code == 422


async def test_patch_stage_only_planned_end_violating_existing_start_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH только end, если конфликт с existing start, возвращает 422."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    stage_id = import_resp.json()["stages"][0]["id"]

    # Пытаемся установить end раньше existing start
    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/{stage_id}",
        json={"planned_end": "2023-12-31"},
    )

    assert response.status_code == 422


async def test_patch_stage_explicit_null_clears_date(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH с explicit null очищает дату."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    stage_id = import_resp.json()["stages"][0]["id"]

    # Очищаем start, оставляем end
    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/{stage_id}",
        json={"planned_start": None},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["planned_start"] is None
    assert data["planned_end"] == "2024-01-10"


async def test_patch_unknown_stage_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH на неизвестный этап возвращает 404."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    # Пытаемся обновить несуществующий этап
    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/{uuid.uuid4()}",
        json={"planned_start": "2024-01-02"},
    )

    assert response.status_code == 404
    assert "Этап не найден" in response.json()["detail"]


async def test_post_import_malformed_csv_no_name_column_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт CSV без колонки 'name' возвращает 422."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # CSV без колонки 'name'
    csv_content = make_csv_bytes("start,end\n2024-01-01,2024-01-10\n")

    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 422


async def test_post_import_unknown_extension_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт с неизвестным расширением возвращает 422."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.txt", b"some content", "text/plain")},
    )

    assert response.status_code == 422


async def test_post_import_file_too_large_returns_413(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт файла, превышающего MAX_UPLOAD_BYTES, возвращает 413."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Создаём файл размером 5 МБ + 1 байт
    oversized_content = b"x" * (5 * 1024 * 1024 + 1)

    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", oversized_content, "text/csv")},
    )

    assert response.status_code == 413
    assert "слишком большой" in response.json()["detail"].lower()


async def test_post_import_file_exactly_max_size_returns_201(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт файла размером ровно MAX_UPLOAD_BYTES возвращает 201."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    # Создаём CSV размером ровно 5 МБ (заполняем нулями до размера)
    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    # Дополняем до ровно 5 МБ комментариями/пробелами
    padding_size = 5 * 1024 * 1024 - len(csv_content)
    if padding_size > 0:
        # Добавляем пустые строки
        csv_content = csv_content + b"\n" * (padding_size // 2)

    response = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201


async def test_post_import_nonexistent_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт на несуществующий сайт возвращает 404."""
    await seed_stand_user(container)

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")

    response = await client.post(
        f"/sites/{uuid.uuid4()}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_get_schedule_foreign_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """GET графика чужого сайта возвращает 404."""
    await seed_stand_user(container)

    # Создаём чужой сайт
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    # Пытаемся получить график чужого сайта
    response = await client.get(f"/sites/{foreign_site_id}/schedule")

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_post_import_foreign_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт на чужой сайт возвращает 404."""
    await seed_stand_user(container)

    # Создаём чужой сайт
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")

    # Пытаемся импортировать график на чужой сайт
    response = await client.post(
        f"/sites/{foreign_site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_patch_stage_foreign_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """PATCH этапа на чужом сайте возвращает 404."""
    await seed_stand_user(container)

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    csv_content = make_csv_bytes("name,start,end\nФундамент,2024-01-01,2024-01-10\n")
    import_resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )
    stage_id = import_resp.json()["stages"][0]["id"]

    # Создаём чужой сайт
    async with container() as rc:
        session = await rc.get(AsyncSession)
        from app.domains.site.models import Site
        from app.domains.user.models import User

        foreign_user = User(id=uuid.uuid4(), full_name="Foreign User")
        await session.merge(foreign_user)

        foreign_site = Site(
            id=uuid.uuid4(),
            name="Foreign Site",
            owner_id=foreign_user.id,
        )
        await session.merge(foreign_site)
        await session.commit()

        foreign_site_id = foreign_site.id

    # Пытаемся обновить этап на чужом сайте
    response = await client.patch(
        f"/sites/{foreign_site_id}/schedule/stages/{stage_id}",
        json={"planned_start": "2024-01-02"},
    )

    assert response.status_code == 404
    assert "Стройка не найдена" in response.json()["detail"]


async def test_invalid_uuid_in_site_id_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Невалидный UUID в site_id возвращает 422."""
    await seed_stand_user(container)

    response = await client.get("/sites/invalid-uuid/schedule")

    assert response.status_code == 422


async def test_invalid_uuid_in_stage_id_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Невалидный UUID в stage_id возвращает 422."""
    await seed_stand_user(container)

    # Создаём сайт
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id = site_resp.json()["id"]

    response = await client.patch(
        f"/sites/{site_id}/schedule/stages/invalid-uuid",
        json={"planned_start": "2024-01-02"},
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("default_kits")
async def test_site_deletion_removes_schedule(
    client: AsyncClient, container: AsyncContainer, engine
) -> None:
    """Удаление сайта удаляет связанный график с каскадным удалением."""
    await seed_stand_user(container)

    # Включаем FK pragma для SQLite
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        # Проверяем, что FK включены
        result = await conn.exec_driver_sql("PRAGMA foreign_keys")
        row = result.fetchone()
        assert row[0] == 1, "FK pragma не включена"

    # Создаём сайт и импортируем график
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    site_id_str = site_resp.json()["id"]
    site_id = uuid.UUID(site_id_str)

    csv_content = make_csv_bytes(
        "name,start,end\nФундамент,2024-01-01,2024-01-10\nСтены,2024-01-11,2024-01-20\n"
    )
    await client.post(
        f"/sites/{site_id_str}/schedule/import",
        files={"file": ("schedule.csv", csv_content, "text/csv")},
    )

    # Удаляем сайт
    delete_resp = await client.delete(f"/sites/{site_id_str}")
    assert delete_resp.status_code == 204

    # Проверяем каскадное удаление: все таблицы должны быть пусты
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        from sqlalchemy import select

        # Проверяем что schedules пусто
        schedules = await session.execute(select(Schedule).where(Schedule.site_id == site_id))
        assert len(schedules.scalars().all()) == 0

        # Проверяем что stages пусто
        schedule_stages = await session.execute(select(ScheduleStage))
        assert len(schedule_stages.scalars().all()) == 0

        # Проверяем что issues пусто
        schedule_issues = await session.execute(select(ScheduleImportIssue))
        assert len(schedule_issues.scalars().all()) == 0


@pytest.mark.usefixtures("default_kits")
async def test_import_computes_stage_statuses_without_observations(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Импорт графика сразу пересчитывает статусы (bug-reports/002).

    Наблюдений нет: этап с наступившим окном — «не наблюдалось», а не «не начат»;
    у этапа, окно которого ещё впереди, статуса нет (null). Правила методики
    создаются из базового набора, даже если «Методику» ещё не открывали.
    """
    from datetime import timedelta

    from tests.test_methodology_router import seed_equipment_types

    await seed_stand_user(container)
    await seed_equipment_types(container)
    site_id = (await client.post("/sites", json={"name": "Шмякострой"})).json()["id"]

    today = date.today()
    past_start, past_end = today - timedelta(days=90), today - timedelta(days=60)
    future_start, future_end = today + timedelta(days=60), today + timedelta(days=90)
    csv = make_csv_bytes(
        "name,start,end\n"
        f"Устройство свай,{past_start},{past_end}\n"
        f"Разработка котлована,{future_start},{future_end}\n"
    )
    resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", csv, "text/csv")},
    )
    assert resp.status_code == 201

    stages = (await client.get(f"/sites/{site_id}/assessment/stages")).json()
    by_name = {s["stage_name"]: s for s in stages}
    assert by_name["Устройство свай"]["status"] == "not_observed"
    assert by_name["Устройство свай"]["computed_at"] is not None
    assert by_name["Разработка котлована"]["status"] is None

    summary = (await client.get(f"/sites/{site_id}/assessment/summary")).json()
    assert summary["verdict"] == "insufficient_data"
