import fastapi
import pydantic

from src.auth import user_auth
from src.common import state
from src.dao.local_storage_repo import LocalStorageRepo, LocalStorageEntry

router = fastapi.APIRouter()


class LocalStorageEntryDto(pydantic.BaseModel):
    id: str
    key: str
    value: str
    created_at: int
    updated_at: int


class UpsertEntryBody(pydantic.BaseModel):
    key: str
    value: str


def _to_dto(entry: LocalStorageEntry) -> LocalStorageEntryDto:
    return LocalStorageEntryDto(
        id=entry.id,
        key=entry.key,
        value=entry.value,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("", response_model=list[LocalStorageEntryDto])
@router.get("/", response_model=list[LocalStorageEntryDto])
async def list_entries(
    repo: LocalStorageRepo = state.injected(LocalStorageRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> list[LocalStorageEntryDto]:
    entries = repo.list_entries(u.id)
    return [_to_dto(e) for e in entries]


@router.post("", response_model=LocalStorageEntryDto)
@router.post("/", response_model=LocalStorageEntryDto)
async def upsert_entry(
    body: UpsertEntryBody,
    repo: LocalStorageRepo = state.injected(LocalStorageRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> LocalStorageEntryDto:
    entry = repo.upsert_entry(u.id, body.key, body.value)
    return _to_dto(entry)


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: str,
    repo: LocalStorageRepo = state.injected(LocalStorageRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> None:
    repo.delete_entry_by_id(u.id, entry_id)
    return None
