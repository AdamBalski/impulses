import fastapi
import pydantic

from src.auth import user_auth
from src.common import state
from src.dao.llm_model_repo import LlmHeader, LlmModel, LlmModelRepo, LlmModelSettings

router = fastapi.APIRouter()


class LlmHeaderDto(pydantic.BaseModel):
    name: str
    value: str


class LlmModelSettingsDto(pydantic.BaseModel):
    base_url: str
    headers: list[LlmHeaderDto] = pydantic.Field(default_factory=list)
    is_localhost: bool = False


class LlmModelDto(pydantic.BaseModel):
    id: str
    model: str
    settings: LlmModelSettingsDto
    created_at: int
    updated_at: int


class UpsertLlmModelBody(pydantic.BaseModel):
    model: str
    settings: LlmModelSettingsDto


def _to_settings(dto: LlmModelSettingsDto) -> LlmModelSettings:
    return LlmModelSettings(
        base_url=dto.base_url,
        headers=[LlmHeader(name=header.name, value=header.value) for header in dto.headers],
        is_localhost=dto.is_localhost,
    )


def _to_dto(model: LlmModel) -> LlmModelDto:
    return LlmModelDto(
        id=model.id,
        model=model.model_name,
        settings=LlmModelSettingsDto(
            base_url=model.settings.base_url,
            headers=[LlmHeaderDto(name=header.name, value=header.value) for header in model.settings.headers],
            is_localhost=model.settings.is_localhost,
        ),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.get("", response_model=list[LlmModelDto])
@router.get("/", response_model=list[LlmModelDto])
async def list_models(
    repo: LlmModelRepo = state.injected(LlmModelRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> list[LlmModelDto]:
    return [_to_dto(model) for model in repo.list_models(u.id)]


@router.get("/{model_id}", response_model=LlmModelDto)
async def get_model(
    model_id: str,
    repo: LlmModelRepo = state.injected(LlmModelRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> LlmModelDto:
    model = repo.get_model_by_id(u.id, model_id)
    if not model:
        raise fastapi.HTTPException(status_code=404, detail="Model not found")
    return _to_dto(model)


@router.post("", response_model=LlmModelDto)
@router.post("/", response_model=LlmModelDto)
async def create_model(
    body: UpsertLlmModelBody,
    repo: LlmModelRepo = state.injected(LlmModelRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> LlmModelDto:
    model_name = body.model.strip()
    if not model_name:
        raise fastapi.HTTPException(status_code=422, detail="Model name is required")
    model = repo.create_model(u.id, model_name, _to_settings(body.settings))
    return _to_dto(model)


@router.put("/{model_id}", response_model=LlmModelDto)
async def update_model(
    model_id: str,
    body: UpsertLlmModelBody,
    repo: LlmModelRepo = state.injected(LlmModelRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> LlmModelDto:
    model_name = body.model.strip()
    if not model_name:
        raise fastapi.HTTPException(status_code=422, detail="Model name is required")
    model = repo.update_model(u.id, model_id, model_name, _to_settings(body.settings))
    if not model:
        raise fastapi.HTTPException(status_code=404, detail="Model not found")
    return _to_dto(model)


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    repo: LlmModelRepo = state.injected(LlmModelRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> None:
    existing = repo.get_model_by_id(u.id, model_id)
    if not existing:
        raise fastapi.HTTPException(status_code=404, detail="Model not found")
    repo.delete_model(u.id, model_id)
    return None
