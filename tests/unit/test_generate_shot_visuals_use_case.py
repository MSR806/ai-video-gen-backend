from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_video_gen_backend.application.shot.generate_shot_visuals import (
    GenerateShotVisualsRequest,
    GenerateShotVisualsUseCase,
)
from ai_video_gen_backend.domain.collection import Collection
from ai_video_gen_backend.domain.generation import (
    GenerationRun,
    GenerationRunRequest,
    GenerationRunSubmission,
)
from ai_video_gen_backend.domain.project import Project
from ai_video_gen_backend.domain.screenplay import Screenplay, ScreenplayScene
from ai_video_gen_backend.domain.shot import Shot, ShotCreateInput, ShotImagePromptCraftResult


class FakeProjectRepository:
    def __init__(self, project: Project | None) -> None:
        self._project = project

    def get_all_projects(self) -> list[Project]:
        return []

    def get_project_by_id(self, project_id: UUID) -> Project | None:
        if self._project is None or self._project.id != project_id:
            return None
        return self._project

    def create_project(self, payload: object) -> Project:
        del payload
        raise NotImplementedError

    def update_project(self, project_id: UUID, payload: object) -> Project | None:
        del project_id, payload
        raise NotImplementedError


class FakeScreenplayRepository:
    def __init__(self, screenplay: Screenplay | None) -> None:
        self._screenplay = screenplay

    def get_screenplay_by_project_id(self, project_id: UUID) -> Screenplay | None:
        if self._screenplay is None or self._screenplay.project_id != project_id:
            return None
        return self._screenplay

    def create_screenplay(self, project_id: UUID, payload: object) -> Screenplay:
        del project_id, payload
        raise NotImplementedError

    def update_screenplay_title(self, screenplay_id: UUID, title: str) -> Screenplay | None:
        del screenplay_id, title
        raise NotImplementedError

    def create_screenplay_scene(self, screenplay_id: UUID, payload: object) -> Screenplay | None:
        del screenplay_id, payload
        raise NotImplementedError

    def update_screenplay_scene(
        self, screenplay_id: UUID, scene_id: UUID, payload: object
    ) -> ScreenplayScene | None:
        del screenplay_id, scene_id, payload
        raise NotImplementedError

    def delete_screenplay_scene(self, screenplay_id: UUID, scene_id: UUID) -> Screenplay | None:
        del screenplay_id, scene_id
        raise NotImplementedError

    def reorder_screenplay_scenes(
        self, screenplay_id: UUID, scene_ids: list[UUID]
    ) -> Screenplay | None:
        del screenplay_id, scene_ids
        raise NotImplementedError


class FakeShotRepository:
    def __init__(self, shots: dict[UUID, Shot]) -> None:
        self._shots = shots

    def get_shot(self, scene_id: UUID, shot_id: UUID) -> Shot | None:
        shot = self._shots.get(shot_id)
        if shot is None or shot.scene_id != scene_id:
            return None
        return shot

    def list_shots(self, scene_id: UUID) -> list[Shot]:
        del scene_id
        return []

    def get_shot_by_collection_id(self, collection_id: UUID) -> Shot | None:
        del collection_id
        return None

    def create_shot(self, scene_id: UUID, payload: object) -> Shot | None:
        del scene_id, payload
        raise NotImplementedError

    def update_shot(self, scene_id: UUID, shot_id: UUID, payload: object) -> Shot | None:
        del scene_id, shot_id, payload
        raise NotImplementedError

    def set_shot_collection(
        self, scene_id: UUID, shot_id: UUID, collection_id: UUID
    ) -> Shot | None:
        del scene_id, shot_id, collection_id
        raise NotImplementedError

    def delete_shot(self, scene_id: UUID, shot_id: UUID) -> bool:
        del scene_id, shot_id
        raise NotImplementedError

    def reorder_shots(self, scene_id: UUID, shot_ids: list[UUID]) -> list[Shot] | None:
        del scene_id, shot_ids
        raise NotImplementedError

    def replace_shots(self, scene_id: UUID, payloads: list[ShotCreateInput]) -> list[Shot] | None:
        del scene_id, payloads
        raise NotImplementedError


@dataclass
class FakeEnsureShotVisualCollectionUseCase:
    collection_by_shot_id: dict[UUID, Collection | None]

    def execute(self, *, project_id: UUID, scene_id: UUID, shot_id: UUID) -> Collection | None:
        del project_id, scene_id
        return self.collection_by_shot_id.get(shot_id)


class FakeCraftShotImagePromptUseCase:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    def execute(self, *, project_id: UUID, collection_id: UUID) -> ShotImagePromptCraftResult:
        del project_id
        self.calls.append(collection_id)
        return ShotImagePromptCraftResult(prompt='crafted prompt')


class FakeSubmitGenerationRunUseCase:
    def __init__(self, failing_shot_collection_ids: set[UUID] | None = None) -> None:
        self.calls: list[GenerationRunRequest] = []
        self._failing_shot_collection_ids = failing_shot_collection_ids or set()

    def execute(self, request: GenerationRunRequest) -> GenerationRunSubmission:
        self.calls.append(request)
        if request.collection_id in self._failing_shot_collection_ids:
            raise RuntimeError('submit failed')
        now = datetime.now(UTC)
        run = GenerationRun(
            id=uuid4(),
            project_id=request.project_id,
            operation_key=request.operation_key,
            provider='fal',
            model_key=request.model_key,
            endpoint_id='endpoint',
            status='IN_PROGRESS',
            requested_output_count=request.output_count,
            inputs_json=request.inputs,
            provider_request_id='provider-id',
            provider_response_json=None,
            idempotency_key=request.idempotency_key,
            error_code=None,
            error_message=None,
            submitted_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        return GenerationRunSubmission(run=run, outputs=[])


def test_generate_shot_visuals_batch_isolates_failures_and_uses_project_aspect_ratio() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    shot_ok = uuid4()
    shot_missing_collection = uuid4()
    shot_not_found = uuid4()
    now = datetime.now(UTC)
    project = Project(
        id=project_id,
        name='Project',
        description='Desc',
        style='Style',
        aspect_ratio='2:3',
        status='draft',
        created_at=now,
        updated_at=now,
    )
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project_id,
        title='Title',
        scenes=[
            ScreenplayScene(id=scene_id, screenplay_id=uuid4(), order_index=1, content='scene')
        ],
    )
    shots = {
        shot_ok: Shot(
            id=shot_ok,
            scene_id=scene_id,
            collection_id=None,
            order_index=1,
            title='Shot 1',
            description='Desc',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Calm',
        ),
        shot_missing_collection: Shot(
            id=shot_missing_collection,
            scene_id=scene_id,
            collection_id=None,
            order_index=2,
            title='Shot 2',
            description='Desc',
            camera_framing='Wide',
            camera_movement='Static',
            mood='Calm',
        ),
    }
    collection = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=None,
        name='Shot collection',
        tag='shot',
        description='desc',
        created_at=now,
        updated_at=now,
    )
    submit = FakeSubmitGenerationRunUseCase()
    use_case = GenerateShotVisualsUseCase(
        project_repository=FakeProjectRepository(project),
        screenplay_repository=FakeScreenplayRepository(screenplay),
        shot_repository=FakeShotRepository(shots),
        ensure_shot_visual_collection=FakeEnsureShotVisualCollectionUseCase(
            {shot_ok: collection, shot_missing_collection: None}
        ),
        craft_shot_image_prompt=FakeCraftShotImagePromptUseCase(),
        submit_generation_run=submit,
    )

    results = use_case.execute(
        GenerateShotVisualsRequest(
            project_id=project_id,
            scene_id=scene_id,
            shot_ids=[shot_ok, shot_missing_collection, shot_not_found],
            model_key='model',
            operation_key='op',
        )
    )

    assert len(results) == 3
    assert results[0].shot_id == shot_ok
    assert results[0].run_id is not None
    assert results[0].collection_id == collection.id
    assert results[1].error == 'Shot visual collection not found'
    assert results[2].error == 'Shot not found'
    assert submit.calls[0].inputs['aspect_ratio'] == '2:3'


def test_generate_shot_visuals_uses_default_aspect_ratio_and_given_prompt() -> None:
    project_id = uuid4()
    scene_id = uuid4()
    shot_id = uuid4()
    now = datetime.now(UTC)
    project = Project(
        id=project_id,
        name='Project',
        description='Desc',
        style='Style',
        aspect_ratio='',
        status='draft',
        created_at=now,
        updated_at=now,
    )
    screenplay = Screenplay(
        id=uuid4(),
        project_id=project_id,
        title='Title',
        scenes=[
            ScreenplayScene(id=scene_id, screenplay_id=uuid4(), order_index=1, content='scene')
        ],
    )
    shot = Shot(
        id=shot_id,
        scene_id=scene_id,
        collection_id=None,
        order_index=1,
        title='Shot',
        description='Desc',
        camera_framing='Wide',
        camera_movement='Static',
        mood='Calm',
    )
    collection = Collection(
        id=uuid4(),
        project_id=project_id,
        parent_collection_id=None,
        name='Shot collection',
        tag='shot',
        description='desc',
        created_at=now,
        updated_at=now,
    )
    prompt_use_case = FakeCraftShotImagePromptUseCase()
    submit = FakeSubmitGenerationRunUseCase()
    use_case = GenerateShotVisualsUseCase(
        project_repository=FakeProjectRepository(project),
        screenplay_repository=FakeScreenplayRepository(screenplay),
        shot_repository=FakeShotRepository({shot_id: shot}),
        ensure_shot_visual_collection=FakeEnsureShotVisualCollectionUseCase({shot_id: collection}),
        craft_shot_image_prompt=prompt_use_case,
        submit_generation_run=submit,
    )

    use_case.execute(
        GenerateShotVisualsRequest(
            project_id=project_id,
            scene_id=scene_id,
            shot_ids=[shot_id],
            model_key='model',
            operation_key='op',
            prompt='manual prompt',
        )
    )

    assert len(prompt_use_case.calls) == 0
    assert submit.calls[0].inputs['prompt'] == 'manual prompt'
    assert submit.calls[0].inputs['aspect_ratio'] == '16:9'
