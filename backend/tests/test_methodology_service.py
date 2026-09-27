"""MethodologyService: test methodology domain service functionality."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.models import (
    EquipmentRequirement,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.repository import MethodologyRepository
from app.domains.methodology.schemas import RequirementIn, RuleUpdate, SetWrite
from app.domains.methodology.seed import EQUIPMENT_SEED
from app.domains.methodology.service import MethodologyService
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.guard import SiteAccessGuard
from app.domains.site.models import Site
from app.domains.site.repository import SiteRepository
from app.domains.user.models import User
from app.plugins.exceptions import AppError


class RecordingRecalculator:
    """Fake StatusRecalculator that records calls for testing."""

    def __init__(self):
        self.calls: list[uuid.UUID] = []

    async def recalculate(self, site_id: uuid.UUID) -> None:
        """Record the call."""
        self.calls.append(site_id)


@pytest.fixture
async def db_setup(container):
    """Set up database with EQUIPMENT_SEED."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        from app.domains.methodology.models import EquipmentType

        for item in EQUIPMENT_SEED:
            equipment = EquipmentType(
                code=item["code"],
                title=item["title"],
                synonyms=item["synonyms"],
                is_coarse=item.get("is_coarse", False),
            )
            session.add(equipment)
        await session.commit()


@pytest.fixture
async def site_and_schedule(container, db_setup):
    """Create a site with owner and a schedule with stages."""
    owner_id = uuid.uuid4()
    site_id = uuid.uuid4()
    schedule_id = uuid.uuid4()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        owner = User(id=owner_id, full_name="Test Owner")
        session.add(owner)

        site = Site(id=site_id, name="Test Site", owner_id=owner_id)
        session.add(site)

        schedule = Schedule(id=schedule_id, site_id=site_id, source_filename="test.csv")
        session.add(schedule)

        # Create stages
        stages = [
            ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule_id,
                name="Устройство свай",
                position=1,
            ),
            ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule_id,
                name="Разработка котлована",
                position=2,
            ),
            ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule_id,
                name="Отделка фасада",
                position=3,
            ),
        ]
        for stage in stages:
            session.add(stage)

        await session.commit()

    return {
        "owner_id": owner_id,
        "site_id": site_id,
        "schedule_id": schedule_id,
        "stage_ids": [s.id for s in stages],
        "stage_names": [s.name for s in stages],
    }


@pytest.fixture
async def methodology_service(engine, container, site_and_schedule):
    """Create MethodologyService with fresh session for each test."""
    # Build sessionmaker from engine (APP-scope resource)
    sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)

    # Get a fresh request container with AsyncSession
    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        catalog = EquipmentCatalog(sessionmaker_inst)
        # Warm catalog before using service to prevent StaticPool rollback.
        # In tests, EquipmentCatalog opens its own session; closing it issues
        # ROLLBACK on the shared connection, wiping flushed-but-uncommitted changes
        # from list_rules. In prod (Postgres) each session has its own connection.
        await catalog.all()

        defaults = DefaultRuleSet()
        recalculator = RecordingRecalculator()

        methodology_repo = MethodologyRepository(session)
        schedule_repo = ScheduleRepository(session)
        site_repo = SiteRepository(session)

        guard = SiteAccessGuard(
            site_repo, type("CurrentUser", (), {"id": site_and_schedule["owner_id"]})()
        )

        service = MethodologyService(
            repository=methodology_repo,
            session=session,
            guard=guard,
            schedule_repository=schedule_repo,
            catalog=catalog,
            defaults=defaults,
            recalculator=recalculator,
        )

        yield session, service, recalculator


class TestMethodologyServiceEquipmentTypes:
    """Tests for list_equipment_types."""

    @pytest.mark.asyncio
    async def test_list_equipment_types_returns_all(self, engine, db_setup):
        """list_equipment_types returns all 20 equipment types."""
        sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)

        async with sessionmaker_inst() as session:
            catalog = EquipmentCatalog(sessionmaker_inst)
            repo = MethodologyRepository(session)

            service = MethodologyService(
                repository=repo,
                session=session,
                guard=None,
                schedule_repository=None,
                catalog=catalog,
                defaults=None,
                recalculator=None,
            )

            types = await service.list_equipment_types()

        assert len(types) == 25
        assert types[0].code == "backhoe_loader"
        assert all(hasattr(t, "id") for t in types)
        assert all(hasattr(t, "code") for t in types)
        assert all(hasattr(t, "title") for t in types)


class TestMethodologyServiceListRules:
    """Tests for list_rules."""

    @pytest.mark.asyncio
    async def test_list_rules_materializes_defaults(self, methodology_service, site_and_schedule):
        """list_rules creates rules from defaults on first call."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])

        assert len(rules) == 3
        assert rules[0].stage_name == "Устройство свай"
        assert rules[1].stage_name == "Разработка котлована"
        assert rules[2].stage_name == "Отделка фасада"

        assert rules[0].rule.is_verifiable is True
        assert rules[0].rule.unverifiable_reason is None
        assert len(rules[0].sets) == 2

        assert rules[1].rule.is_verifiable is True
        assert rules[1].rule.unverifiable_reason is None
        assert len(rules[1].sets) == 1

        assert rules[2].rule.is_verifiable is False
        assert (
            rules[2].rule.unverifiable_reason == "Нет правила в базовом наборе — задайте комплект"
        )
        assert len(rules[2].sets) == 0

        assert len(recalculator.calls) == 0

    @pytest.mark.asyncio
    async def test_list_rules_second_call_idempotent(self, methodology_service, site_and_schedule):
        """Second list_rules call creates nothing new."""
        session, service, recalculator = methodology_service

        rules1 = await service.list_rules(site_and_schedule["site_id"])
        rules2 = await service.list_rules(site_and_schedule["site_id"])

        assert len(rules1) == len(rules2)
        assert [r.rule.id for r in rules1] == [r.rule.id for r in rules2]

    @pytest.mark.asyncio
    async def test_list_rules_ordered_by_stage_position(
        self, methodology_service, site_and_schedule
    ):
        """Rules are ordered by stage position, not by creation/id order."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])

        # Verify order matches stage positions: piles (1), excavation (2), facade (3)
        assert len(rules) == 3
        assert rules[0].stage_name == "Устройство свай"  # position 1
        assert rules[1].stage_name == "Разработка котлована"  # position 2
        assert rules[2].stage_name == "Отделка фасада"  # position 3

    @pytest.mark.asyncio
    async def test_list_rules_no_schedule_404(self, container, db_setup):
        """list_rules without schedule raises 404."""
        owner_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Test Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)
            await session.commit()

        async with container() as request_container:
            # Get engine from APP scope to build sessionmaker
            engine = await request_container.get(AsyncEngine)
            sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)
            session = await request_container.get(AsyncSession)
            catalog = EquipmentCatalog(sessionmaker_inst)

            methodology_repo = MethodologyRepository(session)
            schedule_repo = ScheduleRepository(session)
            site_repo = SiteRepository(session)

            guard = SiteAccessGuard(site_repo, type("CurrentUser", (), {"id": owner_id})())

            service = MethodologyService(
                repository=methodology_repo,
                session=session,
                guard=guard,
                schedule_repository=schedule_repo,
                catalog=catalog,
                defaults=DefaultRuleSet(),
                recalculator=RecordingRecalculator(),
            )

            with pytest.raises(AppError) as exc_info:
                await service.list_rules(site_id)

            assert exc_info.value.status_code == 404
            assert exc_info.value.message == "График не загружен"


class TestMethodologyServiceUpdateRule:
    """Tests for update_rule."""

    @pytest.mark.asyncio
    async def test_update_rule_to_unverifiable(self, methodology_service, site_and_schedule):
        """update_rule sets is_verifiable and calls recalculator."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        rule_update = RuleUpdate(
            is_verifiable=False,
            unverifiable_reason="Комплект не установлен",
        )

        updated_rule = await service.update_rule(
            site_and_schedule["site_id"], piles_rule.rule.id, rule_update
        )

        assert updated_rule.rule.is_verifiable is False
        assert updated_rule.rule.unverifiable_reason == "Комплект не установлен"
        assert len(recalculator.calls) == 1
        assert recalculator.calls[0] == site_and_schedule["site_id"]

    @pytest.mark.asyncio
    async def test_create_set_appends_position(self, methodology_service, site_and_schedule):
        """create_set appends at position max+1."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        max_position = max(s.equipment_set.position for s in piles_rule.sets)
        equipment_types = await service.list_equipment_types()
        excavator = next(e for e in equipment_types if e.code == "excavator_crawler")

        new_set_data = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=excavator.id,
                    obligation=Obligation.NORMATIVE,
                    source_note="Test requirement",
                ),
            ]
        )

        new_set = await service.create_set(
            site_and_schedule["site_id"], piles_rule.rule.id, new_set_data
        )

        assert new_set.equipment_set.position == max_position + 1
        assert len(recalculator.calls) == 1

    @pytest.mark.asyncio
    async def test_create_set_logical_only_422(self, methodology_service, site_and_schedule):
        """create_set with only logical requirement raises 422."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        equipment_types = await service.list_equipment_types()
        concrete_mixer = next(e for e in equipment_types if e.code == "concrete_mixer")

        new_set_data = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=concrete_mixer.id,
                    obligation=Obligation.LOGICAL,
                    source_note="Only logical",
                ),
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_set(site_and_schedule["site_id"], piles_rule.rule.id, new_set_data)

        assert exc_info.value.status_code == 422
        assert len(recalculator.calls) == 0

    @pytest.mark.asyncio
    async def test_delete_set_removes(self, methodology_service, site_and_schedule):
        """delete_set removes the set."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]
        set_id = piles_rule.sets[0].equipment_set.id

        await service.delete_set(site_and_schedule["site_id"], set_id)

        rules_after = await service.list_rules(site_and_schedule["site_id"])
        piles_rule_after = rules_after[0]
        remaining_set_ids = [s.equipment_set.id for s in piles_rule_after.sets]
        assert set_id not in remaining_set_ids


class TestMethodologyServiceForeignOwner:
    """Tests for access control: foreign owner cannot access another's site."""

    @pytest.mark.asyncio
    async def test_foreign_owner_list_rules_404(self, engine, container, db_setup):
        """Foreign owner cannot list_rules on another's site."""
        owner1_id = uuid.uuid4()
        owner2_id = uuid.uuid4()
        site_id = uuid.uuid4()
        schedule_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner1 = User(id=owner1_id, full_name="Owner 1")
            owner2 = User(id=owner2_id, full_name="Owner 2")
            session.add(owner1)
            session.add(owner2)

            site = Site(id=site_id, name="Test Site", owner_id=owner1_id)
            session.add(site)

            schedule = Schedule(id=schedule_id, site_id=site_id, source_filename="test.csv")
            session.add(schedule)

            stage = ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule_id,
                name="Stage 1",
                position=1,
            )
            session.add(stage)

            await session.commit()

        sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            catalog = EquipmentCatalog(sessionmaker_inst)
            await catalog.all()

            methodology_repo = MethodologyRepository(session)
            schedule_repo = ScheduleRepository(session)
            site_repo = SiteRepository(session)

            guard = SiteAccessGuard(site_repo, type("CurrentUser", (), {"id": owner2_id})())

            service = MethodologyService(
                repository=methodology_repo,
                session=session,
                guard=guard,
                schedule_repository=schedule_repo,
                catalog=catalog,
                defaults=DefaultRuleSet(),
                recalculator=RecordingRecalculator(),
            )

            with pytest.raises(AppError) as exc_info:
                await service.list_rules(site_id)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_foreign_owner_update_rule_404(
        self, engine, container, db_setup, site_and_schedule
    ):
        """Foreign owner cannot update_rule on another's site."""
        owner2_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner2 = User(id=owner2_id, full_name="Owner 2")
            session.add(owner2)
            await session.commit()

        sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            catalog = EquipmentCatalog(sessionmaker_inst)
            await catalog.all()

            methodology_repo = MethodologyRepository(session)
            schedule_repo = ScheduleRepository(session)
            site_repo = SiteRepository(session)

            guard = SiteAccessGuard(site_repo, type("CurrentUser", (), {"id": owner2_id})())

            service = MethodologyService(
                repository=methodology_repo,
                session=session,
                guard=guard,
                schedule_repository=schedule_repo,
                catalog=catalog,
                defaults=DefaultRuleSet(),
                recalculator=RecordingRecalculator(),
            )

            with pytest.raises(AppError) as exc_info:
                await service.update_rule(
                    site_and_schedule["site_id"],
                    uuid.uuid4(),
                    RuleUpdate(is_verifiable=False, unverifiable_reason="Test"),
                )

            assert exc_info.value.status_code == 404


class TestMethodologyServiceCrossSiteIsolation:
    """Tests for cross-site isolation: resources from site B shouldn't be accessible via site A."""

    @pytest.mark.asyncio
    async def test_cross_site_update_rule_404(self, engine, container, db_setup, site_and_schedule):
        """Using rule_id from site B with site A should return 404."""
        owner_id = site_and_schedule["owner_id"]
        site_a_id = site_and_schedule["site_id"]

        # Create site B with its own schedule and rules
        site_b_id = uuid.uuid4()
        schedule_b_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site_b = Site(id=site_b_id, name="Site B", owner_id=owner_id)
            session.add(site_b)

            schedule_b = Schedule(id=schedule_b_id, site_id=site_b_id, source_filename="test_b.csv")
            session.add(schedule_b)

            stage_b = ScheduleStage(
                id=uuid.uuid4(),
                schedule_id=schedule_b_id,
                name="Stage B",
                position=1,
            )
            session.add(stage_b)

            await session.commit()

        # Materialize rules for both sites
        sessionmaker_inst = async_sessionmaker(engine, expire_on_commit=False)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            catalog = EquipmentCatalog(sessionmaker_inst)
            await catalog.all()

            methodology_repo = MethodologyRepository(session)
            schedule_repo = ScheduleRepository(session)
            site_repo = SiteRepository(session)

            guard = SiteAccessGuard(site_repo, type("CurrentUser", (), {"id": owner_id})())

            service = MethodologyService(
                repository=methodology_repo,
                session=session,
                guard=guard,
                schedule_repository=schedule_repo,
                catalog=catalog,
                defaults=DefaultRuleSet(),
                recalculator=RecordingRecalculator(),
            )

            rules_b = await service.list_rules(site_b_id)
            rule_b_id = rules_b[0].rule.id

            # Try to use rule from site B with site A
            with pytest.raises(AppError) as exc_info:
                await service.update_rule(
                    site_a_id,
                    rule_b_id,
                    RuleUpdate(is_verifiable=False, unverifiable_reason="Test"),
                )

            assert exc_info.value.status_code == 404


class TestMethodologyServiceUpdatedAt:
    """Tests for updated_at timestamp updates on mutations."""

    @pytest.mark.asyncio
    async def test_update_rule_bumps_updated_at(self, methodology_service, site_and_schedule):
        """update_rule bumps the rule's updated_at timestamp."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        # Set updated_at to old time
        old_time = datetime(2000, 1, 1, tzinfo=UTC)
        rule = await session.get(MethodologyRule, piles_rule.rule.id)
        rule.updated_at = old_time
        await session.flush()

        # Update rule
        updated_rule = await service.update_rule(
            site_and_schedule["site_id"],
            piles_rule.rule.id,
            RuleUpdate(is_verifiable=False, unverifiable_reason="Test"),
        )

        # Verify updated_at was bumped
        assert updated_rule.rule.updated_at > old_time
        assert len(recalculator.calls) == 1

    @pytest.mark.asyncio
    async def test_create_set_bumps_rule_updated_at(self, methodology_service, site_and_schedule):
        """create_set bumps the rule's updated_at timestamp."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        # Set updated_at to old time
        old_time = datetime(2000, 1, 1, tzinfo=UTC)
        rule = await session.get(MethodologyRule, piles_rule.rule.id)
        rule.updated_at = old_time
        await session.flush()

        # Create set
        equipment_types = await service.list_equipment_types()
        excavator = next(e for e in equipment_types if e.code == "excavator_crawler")

        await service.create_set(
            site_and_schedule["site_id"],
            piles_rule.rule.id,
            SetWrite(
                requirements=[
                    RequirementIn(
                        equipment_type_id=excavator.id,
                        obligation=Obligation.NORMATIVE,
                        source_note="Test",
                    ),
                ]
            ),
        )

        # Verify updated_at was bumped
        rule_after = await session.get(MethodologyRule, piles_rule.rule.id)
        assert rule_after.updated_at > old_time
        assert len(recalculator.calls) == 1

    @pytest.mark.asyncio
    async def test_delete_set_bumps_rule_updated_at(self, methodology_service, site_and_schedule):
        """delete_set bumps the rule's updated_at timestamp."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]
        set_id = piles_rule.sets[0].equipment_set.id

        # Set updated_at to old time
        old_time = datetime(2000, 1, 1, tzinfo=UTC)
        rule = await session.get(MethodologyRule, piles_rule.rule.id)
        rule.updated_at = old_time
        await session.flush()

        # Delete set
        await service.delete_set(site_and_schedule["site_id"], set_id)

        # Verify updated_at was bumped
        rule_after = await session.get(MethodologyRule, piles_rule.rule.id)
        assert rule_after.updated_at > old_time
        assert len(recalculator.calls) == 1


class TestMethodologyServiceUnknownEquipmentType:
    """Tests for unknown equipment type handling."""

    @pytest.mark.asyncio
    async def test_create_set_unknown_equipment_type_422(
        self, methodology_service, site_and_schedule
    ):
        """create_set with unknown equipment_type_id raises 422."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        unknown_id = uuid.uuid4()

        with pytest.raises(AppError) as exc_info:
            await service.create_set(
                site_and_schedule["site_id"],
                piles_rule.rule.id,
                SetWrite(
                    requirements=[
                        RequirementIn(
                            equipment_type_id=unknown_id,
                            obligation=Obligation.NORMATIVE,
                            source_note="Test",
                        ),
                    ]
                ),
            )

        assert exc_info.value.status_code == 422
        assert len(recalculator.calls) == 0

    @pytest.mark.asyncio
    async def test_replace_set_unknown_equipment_type_422(
        self, methodology_service, site_and_schedule
    ):
        """replace_set with unknown equipment_type_id raises 422 and doesn't change DB."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]
        set_id = piles_rule.sets[0].equipment_set.id

        # Get old requirements count
        old_reqs = await session.execute(
            select(EquipmentRequirement).where(EquipmentRequirement.set_id == set_id)
        )
        old_req_count = len(old_reqs.scalars().all())

        unknown_id = uuid.uuid4()

        with pytest.raises(AppError) as exc_info:
            await service.replace_set(
                site_and_schedule["site_id"],
                set_id,
                SetWrite(
                    requirements=[
                        RequirementIn(
                            equipment_type_id=unknown_id,
                            obligation=Obligation.NORMATIVE,
                            source_note="Test",
                        ),
                    ]
                ),
            )

        assert exc_info.value.status_code == 422

        # Verify DB unchanged
        reqs_after = await session.execute(
            select(EquipmentRequirement).where(EquipmentRequirement.set_id == set_id)
        )
        assert len(reqs_after.scalars().all()) == old_req_count
        assert len(recalculator.calls) == 0


class TestMethodologyServiceAuxiliaryOnlySet:
    """Tests for auxiliary-only set rejection."""

    @pytest.mark.asyncio
    async def test_create_set_auxiliary_only_422(self, methodology_service, site_and_schedule):
        """create_set with only auxiliary requirement raises 422."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        equipment_types = await service.list_equipment_types()
        excavator = next(e for e in equipment_types if e.code == "excavator_crawler")

        with pytest.raises(AppError) as exc_info:
            await service.create_set(
                site_and_schedule["site_id"],
                piles_rule.rule.id,
                SetWrite(
                    requirements=[
                        RequirementIn(
                            equipment_type_id=excavator.id,
                            obligation=Obligation.AUXILIARY,
                            source_note="Only auxiliary",
                        ),
                    ]
                ),
            )

        assert exc_info.value.status_code == 422
        assert len(recalculator.calls) == 0

    @pytest.mark.asyncio
    async def test_create_set_normative_plus_logical_succeeds(
        self, methodology_service, site_and_schedule
    ):
        """create_set with normative + logical requirements succeeds."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        equipment_types = await service.list_equipment_types()
        excavator = next(e for e in equipment_types if e.code == "excavator_crawler")
        concrete_mixer = next(e for e in equipment_types if e.code == "concrete_mixer")

        new_set = await service.create_set(
            site_and_schedule["site_id"],
            piles_rule.rule.id,
            SetWrite(
                requirements=[
                    RequirementIn(
                        equipment_type_id=excavator.id,
                        obligation=Obligation.NORMATIVE,
                        source_note="Normative",
                    ),
                    RequirementIn(
                        equipment_type_id=concrete_mixer.id,
                        obligation=Obligation.LOGICAL,
                        source_note="Logical",
                    ),
                ]
            ),
        )

        assert len(new_set.requirements) == 2
        obligations = [r.requirement.obligation for r in new_set.requirements]
        assert Obligation.NORMATIVE in obligations
        assert Obligation.LOGICAL in obligations
        assert len(recalculator.calls) == 1


class TestMethodologyServiceReplaceSet:
    """Tests for replace_set behavior."""

    @pytest.mark.asyncio
    async def test_replace_set_old_reqs_gone_new_present(
        self, methodology_service, site_and_schedule
    ):
        """replace_set removes old requirements and adds new ones."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]
        set_id = piles_rule.sets[0].equipment_set.id

        equipment_types = await service.list_equipment_types()
        new_equipment = next(e for e in equipment_types if e.code == "excavator_crawler")

        updated_set = await service.replace_set(
            site_and_schedule["site_id"],
            set_id,
            SetWrite(
                requirements=[
                    RequirementIn(
                        equipment_type_id=new_equipment.id,
                        obligation=Obligation.NORMATIVE,
                        source_note="New requirement",
                    ),
                ]
            ),
        )

        # Verify old requirements are gone
        old_reqs = await session.execute(
            select(EquipmentRequirement)
            .where(EquipmentRequirement.set_id == set_id)
            .where(EquipmentRequirement.equipment_type_id != new_equipment.id)
        )
        assert len(old_reqs.scalars().all()) == 0

        # Verify new requirement is present
        assert len(updated_set.requirements) == 1
        assert updated_set.requirements[0].equipment_type.code == "excavator_crawler"
        assert len(recalculator.calls) == 1

    @pytest.mark.asyncio
    async def test_replace_set_logical_only_422_old_intact(
        self, methodology_service, site_and_schedule
    ):
        """replace_set with logical-only raises 422 and old requirements stay intact."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]
        set_id = piles_rule.sets[0].equipment_set.id

        # Get old requirements
        old_reqs = await session.execute(
            select(EquipmentRequirement).where(EquipmentRequirement.set_id == set_id)
        )
        old_req_ids = {r.id for r in old_reqs.scalars().all()}
        old_req_count = len(old_req_ids)

        equipment_types = await service.list_equipment_types()
        concrete_mixer = next(e for e in equipment_types if e.code == "concrete_mixer")

        with pytest.raises(AppError) as exc_info:
            await service.replace_set(
                site_and_schedule["site_id"],
                set_id,
                SetWrite(
                    requirements=[
                        RequirementIn(
                            equipment_type_id=concrete_mixer.id,
                            obligation=Obligation.LOGICAL,
                            source_note="Only logical",
                        ),
                    ]
                ),
            )

        assert exc_info.value.status_code == 422

        # Verify old requirements are still there
        reqs_after = await session.execute(
            select(EquipmentRequirement).where(EquipmentRequirement.set_id == set_id)
        )
        after_ids = {r.id for r in reqs_after.scalars().all()}
        assert after_ids == old_req_ids
        assert len(after_ids) == old_req_count
        assert len(recalculator.calls) == 0


class TestMethodologyServiceListRulesStructure:
    """Tests for list_rules structure and details."""

    @pytest.mark.asyncio
    async def test_list_rules_piles_rule_structure(self, methodology_service, site_and_schedule):
        """Piles rule has correct structure with gesn_code and logical concrete_mixer."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        piles_rule = rules[0]

        assert piles_rule.stage_name == "Устройство свай"
        assert piles_rule.rule.is_verifiable is True
        assert len(piles_rule.sets) == 2

        # Check first set has 4 requirements
        first_set = piles_rule.sets[0]
        assert len(first_set.requirements) == 4

        # Check for gesn_code
        reqs_with_gesn = [r for r in first_set.requirements if r.requirement.gesn_code]
        assert len(reqs_with_gesn) > 0
        assert any(r.requirement.gesn_code == "05-01-079-01" for r in first_set.requirements)

        # Check for logical concrete_mixer
        logical_reqs = [
            r for r in first_set.requirements if r.requirement.obligation == Obligation.LOGICAL
        ]
        assert len(logical_reqs) > 0
        concrete_mixer_logical = [
            r for r in logical_reqs if r.equipment_type.code == "concrete_mixer"
        ]
        assert len(concrete_mixer_logical) > 0

    @pytest.mark.asyncio
    async def test_list_rules_facade_unverifiable(self, methodology_service, site_and_schedule):
        """Facade rule is unverifiable with reason and has no sets."""
        session, service, recalculator = methodology_service

        rules = await service.list_rules(site_and_schedule["site_id"])
        facade_rule = rules[2]

        assert facade_rule.stage_name == "Отделка фасада"
        assert facade_rule.rule.is_verifiable is False
        assert facade_rule.rule.unverifiable_reason is not None
        assert len(facade_rule.rule.unverifiable_reason) > 0
        assert len(facade_rule.sets) == 0

    @pytest.mark.asyncio
    async def test_list_rules_never_calls_recalculator(
        self, methodology_service, site_and_schedule
    ):
        """list_rules never calls recalculator, even on materialization."""
        session, service, recalculator = methodology_service

        # Clear any prior calls
        recalculator.calls.clear()

        # First call materializes defaults
        rules = await service.list_rules(site_and_schedule["site_id"])
        assert len(rules) == 3
        assert len(recalculator.calls) == 0

        # Second call should also not call recalculator
        rules2 = await service.list_rules(site_and_schedule["site_id"])
        assert len(rules2) == 3
        assert len(recalculator.calls) == 0

    @pytest.mark.asyncio
    async def test_list_rules_race_condition_retry(
        self, methodology_service, site_and_schedule
    ) -> None:
        """Параллельная материализация: конфликт unique -> rollback, повтор, без 500 и дублей."""
        session, service, recalculator = methodology_service
        site_id = site_and_schedule["site_id"]

        # Другой запрос уже успел создать все правила и закоммитить
        await service.list_rules(site_id)

        # Наш запрос «не увидел» их: первое чтение возвращает пустой список
        real_list = service._repository.list_rules_by_site
        calls = {"n": 0}

        async def stale_first_read(sid):
            calls["n"] += 1
            if calls["n"] == 1:
                return []
            return await real_list(sid)

        service._repository.list_rules_by_site = stale_first_read

        rules = await service.list_rules(site_id)

        assert calls["n"] >= 2  # был повтор после IntegrityError
        assert [r.stage_name for r in rules] == [
            "Устройство свай",
            "Разработка котлована",
            "Отделка фасада",
        ]
        result = await session.execute(
            select(MethodologyRule).where(MethodologyRule.site_id == site_id)
        )
        assert len(result.scalars().all()) == 3
        assert len(recalculator.calls) == 0


class TestMethodologyServiceCoarseEquipment:
    """Тесты для отклонения грубых классов оборудования."""

    @pytest.mark.asyncio
    async def test_create_set_rejects_coarse_equipment(
        self, methodology_service, site_and_schedule
    ):
        """Создание набора отклоняет грубые классы оборудования."""
        session, service, recalculator = methodology_service
        site_id = site_and_schedule["site_id"]

        # Материализируем правило для первого этапа
        rules = await service.list_rules(site_id)
        rule_id = rules[0].rule.id

        # Получить ID coarse equipment (excavator_unknown)
        all_equipment = await service.list_equipment_types()
        coarse_equipment = next(eq for eq in all_equipment if eq.code == "excavator_unknown")

        # Попытаться создать набор с coarse equipment
        set_data = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=coarse_equipment.id,
                    min_count=1,
                    obligation=Obligation.NORMATIVE,
                    gesn_code="test-code",
                )
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.create_set(site_id, rule_id, set_data)

        assert exc_info.value.status_code == 422
        assert "excavator_unknown" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_replace_set_rejects_coarse_equipment(
        self, methodology_service, site_and_schedule
    ):
        """Замена набора отклоняет грубые классы оборудования."""
        session, service, recalculator = methodology_service
        site_id = site_and_schedule["site_id"]

        # Материализируем правило и создаём набор
        rules = await service.list_rules(site_id)
        rule_id = rules[0].rule.id

        # Создаём набор с обычным оборудованием
        normal_equipment = await service.list_equipment_types()
        drilling_rig = next(eq for eq in normal_equipment if eq.code == "drilling_rig")

        set_data = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=drilling_rig.id,
                    min_count=1,
                    obligation=Obligation.NORMATIVE,
                    gesn_code="test-code",
                )
            ]
        )

        created_set = await service.create_set(site_id, rule_id, set_data)

        # Попытаться заменить требования на coarse equipment
        coarse_equipment = next(eq for eq in normal_equipment if eq.code == "excavator_unknown")

        replace_data = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=coarse_equipment.id,
                    min_count=1,
                    obligation=Obligation.NORMATIVE,
                    gesn_code="test-code",
                )
            ]
        )

        with pytest.raises(AppError) as exc_info:
            await service.replace_set(site_id, created_set.equipment_set.id, replace_data)

        assert exc_info.value.status_code == 422
        assert "excavator_unknown" in exc_info.value.message
