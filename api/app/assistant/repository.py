"""Contracts for backend-owned data and the development-only JSON store."""
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from filelock import FileLock, Timeout
from pydantic import ValidationError

from .contracts import CareerRole, DocumentRecord, Draft, Opportunity, Profile, SkillNode, UserState
from .errors import Conflict, NotFound, StorageUnavailable
from .skill_context import CatalogSkillData, SkillTree

MAX_DOCUMENTS = 20


class CareerData(Protocol):
    def get_profile(self, user_id: str) -> Profile: ...
    def get_opportunity(self, opportunity_id: str) -> Opportunity | None: ...
    def list_opportunities(self) -> Sequence[Opportunity]: ...
    def get_skill_node(self, job_id: str, skill_id: str) -> SkillNode | None: ...


class CatalogCareerData(CareerData, Protocol):
    def get_skill_tree(self, job_id: str) -> SkillTree | None: ...
    def list_career_roles(self) -> Sequence[CareerRole]: ...


class AssistantStore(Protocol):
    def get_state(self, user_id: str) -> UserState: ...
    def save_state(self, user_id: str, state: UserState) -> None:
        """Compare the revision. Save memory, turns and any changed drafts atomically."""
        ...

    def create_document(self, user_id: str, record: DocumentRecord, original: bytes) -> None: ...
    def get_document(self, user_id: str, document_id: str) -> DocumentRecord: ...
    def get_original(self, user_id: str, document_id: str) -> bytes: ...
    def save_draft(self, user_id: str, document_id: str, draft: Draft) -> None:
        """Save only if the latest revision is exactly draft.revision - 1."""
        ...


class MockCareerData:
    """Development fixtures. A login is mapped to a mock student explicitly."""

    def __init__(self, users: dict[str, str], path: Path | None = None, *, skill_catalog: CatalogSkillData | None = None):
        fixture = Path(__file__).with_name("mock_data.json") if path is None else path
        data = json.loads(fixture.read_text(encoding="utf-8"))
        self.users = dict(users)
        self.profiles = {key: Profile(mock=True, facts=items) for key, items in data["users"].items()}
        self.opportunities = {
            item["id"]: Opportunity.model_validate({**item, "mock": True})
            for item in data["opportunities"]
        }
        self.nodes = {}
        by_job: dict[str, list[SkillNode]] = {}
        parents: dict[str, dict[str, list[str]]] = {}
        for item in data["skill_tree"]:
            fields = {key: value for key, value in item.items() if key != "prerequisiteIds"}
            node = SkillNode.model_validate({**fields, "mock": True})
            self.nodes[(node.job_id, node.skill_id)] = node
            by_job.setdefault(node.job_id, []).append(node)
            if "prerequisiteIds" in item:
                parents.setdefault(node.job_id, {})[node.skill_id] = item["prerequisiteIds"]
        self.trees = {job: SkillTree(nodes, parents.get(job, {})) for job, nodes in by_job.items()}
        self.roles = [CareerRole.model_validate({**item, "mock": True}) for item in data.get("career_roles", [])]
        if skill_catalog is not None:
            self.roles = skill_catalog.list_career_roles()
            self.trees = dict(skill_catalog.trees)
            self.nodes = {(node.job_id, node.skill_id): node for tree in self.trees.values()
                          for node in tree.nodes.values()}

    def get_profile(self, user_id: str) -> Profile:
        profile = self.profiles.get(self.users.get(user_id))
        return profile.model_copy(deep=True) if profile else Profile(mock=True)

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        item = self.opportunities.get(opportunity_id)
        return item.model_copy(deep=True) if item else None

    def list_opportunities(self) -> list[Opportunity]:
        return [item.model_copy(deep=True) for item in self.opportunities.values()]

    def get_skill_node(self, job_id: str, skill_id: str) -> SkillNode | None:
        node = self.nodes.get((job_id, skill_id))
        return node.model_copy(deep=True) if node else None

    def get_skill_tree(self, job_id: str) -> SkillTree | None:
        return self.trees.get(job_id)

    def list_career_roles(self) -> list[CareerRole]:
        return [role.model_copy(deep=True) for role in self.roles]


def _digest(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, contents: bytes) -> None:
    temp_path = None
    try:
        with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as output:
            temp_path = Path(output.name)
            output.write(contents)
            output.flush()
        temp_path.replace(path)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


class JsonAssistantStore:
    """Use a dedicated, writable development directory outside the source tree."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _state(self, user_id: str) -> Path:
        return self.root / _digest(user_id) / "state.json"

    def _original(self, user_id: str, document_id: str) -> Path:
        return self._state(user_id).parent / (_digest(document_id) + ".original")

    def get_state(self, user_id: str) -> UserState:
        try:
            return UserState.model_validate_json(self._state(user_id).read_bytes())
        except FileNotFoundError:
            return UserState()
        except (OSError, ValidationError):
            raise StorageUnavailable("저장된 데이터를 읽을 수 없어요.") from None

    def _publish(self, user_id: str, state: UserState) -> None:
        updated = state.model_copy(update={"revision": state.revision + 1})
        _atomic_write(self._state(user_id), updated.model_dump_json().encode("utf-8"))

    def save_state(self, user_id: str, state: UserState) -> None:
        path = self._state(user_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(path) + ".lock", timeout=3):
                if self.get_state(user_id).revision != state.revision:
                    raise Conflict("다른 요청이 정보를 변경했어요. 최신 상태에서 다시 시도해 주세요.")
                self._publish(user_id, state)
        except (OSError, Timeout):
            raise StorageUnavailable("대화 상태를 저장할 수 없어요.") from None

    def create_document(self, user_id: str, record: DocumentRecord, original: bytes) -> None:
        path = self._state(user_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(path) + ".lock", timeout=3):
                state = self.get_state(user_id)
                if record.id in state.documents or len(state.documents) >= MAX_DOCUMENTS:
                    raise Conflict("이미 존재하는 문서이거나 최대 보관 문서 수에 도달했어요.")
                original_path = self._original(user_id, record.id)
                _atomic_write(original_path, original)
                state.documents[record.id] = record
                try:
                    self._publish(user_id, state)
                except OSError:
                    original_path.unlink(missing_ok=True)
                    raise
        except (OSError, Timeout):
            raise StorageUnavailable("문서를 저장할 수 없어요.") from None

    def get_document(self, user_id: str, document_id: str) -> DocumentRecord:
        record = self.get_state(user_id).documents.get(document_id)
        if not record:
            raise NotFound("문서를 찾을 수 없어요.")
        return record

    def get_original(self, user_id: str, document_id: str) -> bytes:
        self.get_document(user_id, document_id)
        try:
            return self._original(user_id, document_id).read_bytes()
        except OSError:
            raise StorageUnavailable("문서 원본을 읽을 수 없어요.") from None

    def save_draft(self, user_id: str, document_id: str, draft: Draft) -> None:
        state = self.get_state(user_id)
        document = state.documents.get(document_id)
        if not document:
            raise NotFound("문서를 찾을 수 없어요.")
        if (document.draft.revision if document.draft else 0) + 1 != draft.revision:
            raise Conflict("문서 초안이 변경됐어요. 새로 조회한 뒤 다시 시도해 주세요.")
        document.draft = draft
        self.save_state(user_id, state)
