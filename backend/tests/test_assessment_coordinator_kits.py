"""Tests for kit confirmation functionality in RecomputeCoordinator."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.coordinator import RecomputeCoordinator
from app.domains.assessment.engine import EngineConfig, RuleEngine, RuleInput
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.materializer import RuleMaterializer
from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    EquipmentType,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.repository import MethodologyRepository
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.models import Site
from app.domains.user.models import User


async def seed_user(container) -> User:
    """Create and return a test user."""
    user_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        user = User(id=user_id, full_name="Test User")
        session.add(user)
        await session.commit()
    return user


async def create_coordinator(
    container: object, engine_config: EngineConfig
) -> RecomputeCoordinator:
    """Create RecomputeCoordinator from container."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        stage_status_repo = StageStatusRepository(session)
        deviation_repo = DeviationRepository(session)
        deviation_evidence_repo = DeviationEvidenceRepository(session)
        status_basis_repo = StatusBasisRepository(session)
        schedule_repo = ScheduleRepository(session)
        methodology_repo = MethodologyRepository(session)
        observation_repo = ObservationRepository(session)
        observed_equipment_repo = ObservedEquipmentRepository(session)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)
        equipment_catalog = await request_container.get(EquipmentCatalog)

        engine = RuleEngine(engine_config)
        coordinator = RecomputeCoordinator(
            engine=engine,
            stage_status_repo=stage_status_repo,
            deviation_repo=deviation_repo,
            deviation_evidence_repo=deviation_evidence_repo,
            status_basis_repo=status_basis_repo,
            schedule_repo=schedule_repo,
            methodology_repo=methodology_repo,
            observation_repo=observation_repo,
            observed_equipment_repo=observed_equipment_repo,
            photo_repo=photo_repo,
            detection_repo=detection_repo,
            equipment_catalog=equipment_catalog,
            materializer=await request_container.get(RuleMaterializer),
            session=session,
        )
        return coordinator


class TestKitConfirmation:
    """Tests for kit confirmation (LCT-xxx)."""

    @pytest.mark.asyncio
    async def test_rule_with_two_equipment_sets_creates_kits(self, container) -> None:
        """A rule with two EquipmentSets -> RuleInput has 2 kits.

        Drilling rig (specific) in kit 2, excavator (not specific) in kit 1.
        Flat requirements still has both. Kits are in position order.
        """
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()

        # Equipment types
        excavator_id = uuid.uuid4()  # not specific
        drilling_rig_id = uuid.uuid4()  # specific

        today = date.today()
        obs_date = today - timedelta(days=5)

        # Create site with rule having two EquipmentSets
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # User and site
            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            # Schedule
            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            # Stage
            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=obs_date - timedelta(days=3),
                planned_end=obs_date + timedelta(days=3),
            )
            session.add(stage)

            # Equipment types
            excavator_type = EquipmentType(
                id=excavator_id, code="excavator", title="Excavator", synonyms=[]
            )
            drilling_rig_type = EquipmentType(
                id=drilling_rig_id,
                code="drilling_rig",
                title="Drilling Rig",
                synonyms=[],
            )
            session.add(excavator_type)
            session.add(drilling_rig_type)
            await session.flush()

            # Rule
            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            # Equipment Set 1 (position 1): excavator (not specific)
            set_1_id = uuid.uuid4()
            equipment_set_1 = EquipmentSet(id=set_1_id, rule_id=rule_id, position=1)
            session.add(equipment_set_1)
            await session.flush()

            requirement_1 = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=set_1_id,
                equipment_type_id=excavator_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement_1)

            # Equipment Set 2 (position 2): drilling_rig (specific)
            set_2_id = uuid.uuid4()
            equipment_set_2 = EquipmentSet(id=set_2_id, rule_id=rule_id, position=2)
            session.add(equipment_set_2)
            await session.flush()

            requirement_2 = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=set_2_id,
                equipment_type_id=drilling_rig_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.002",
            )
            session.add(requirement_2)

            await session.commit()

        # Create coordinator and spy on engine.compute_site
        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )

        captured_rules_by_stage: dict = {}

        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)

            # Spy on engine.compute_site to capture what gets passed
            original_compute_site = coordinator._engine.compute_site

            def spy_compute_site(
                stages, rules_by_stage, observations, reference_date, equipment_names, coarse
            ):
                # Capture the rules_by_stage
                captured_rules_by_stage.update(rules_by_stage)
                # Call original with same arguments
                return original_compute_site(
                    stages, rules_by_stage, observations, reference_date, equipment_names, coarse
                )

            coordinator._engine.compute_site = spy_compute_site

            # Run recompute
            await coordinator.recompute_site(site_id)

        # Verify that RuleInput was passed correctly
        assert stage_id in captured_rules_by_stage, f"No RuleInput for stage {stage_id}"
        rule_input: RuleInput = captured_rules_by_stage[stage_id]

        # Verify kits
        assert len(rule_input.kits) == 2, f"Expected 2 kits, got {len(rule_input.kits)}"

        # Verify kits are in position order
        kit_1 = rule_input.kits[0]
        kit_2 = rule_input.kits[1]
        assert kit_1.position == 1, f"Kit 1 position: expected 1, got {kit_1.position}"
        assert kit_2.position == 2, f"Kit 2 position: expected 2, got {kit_2.position}"

        # Verify kit 1 has excavator (not specific)
        assert len(kit_1.requirements) == 1
        assert kit_1.requirements[0].equipment_type_id == excavator_id
        assert kit_1.requirements[0].is_specific is False, "Excavator should not be specific"

        # Verify kit 2 has drilling_rig (specific)
        assert len(kit_2.requirements) == 1
        assert kit_2.requirements[0].equipment_type_id == drilling_rig_id
        assert kit_2.requirements[0].is_specific is True, "Drilling rig should be specific"

        # Verify flat requirements still has both
        assert len(rule_input.requirements) == 2, (
            f"Expected 2 flat requirements, got {len(rule_input.requirements)}"
        )
        flat_ids = {req.equipment_type_id for req in rule_input.requirements}
        assert excavator_id in flat_ids, "Flat requirements should include excavator"
        assert drilling_rig_id in flat_ids, "Flat requirements should include drilling_rig"

        # Verify specificity in flat requirements
        excavator_req = next(
            r for r in rule_input.requirements if r.equipment_type_id == excavator_id
        )
        drilling_rig_req = next(
            r for r in rule_input.requirements if r.equipment_type_id == drilling_rig_id
        )
        assert excavator_req.is_specific is False, (
            "Excavator in flat requirements should not be specific"
        )
        assert drilling_rig_req.is_specific is True, (
            "Drilling rig in flat requirements should be specific"
        )
