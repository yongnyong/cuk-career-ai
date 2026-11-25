from datetime import date as CalendarDate
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel
from .startup_plan import StartupPlan

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
FieldValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
FactKind = Literal[
    "personal", "department", "grade", "status", "education", "training", "certification",
    "job", "internship", "project", "activity", "award", "skill", "interest", "goal", "study_time",
]
MemoryKind = Literal[
    "interest", "goal", "education", "training", "certification", "job", "internship",
    "project", "activity", "award", "skill", "department", "grade", "study_time",
]
Source = Literal["system", "official", "conversation", "user_claim"]
Progress = Literal["preparing", "completed", "not_held", "beginner", "intermediate"]
EXPERIENCE_KINDS = frozenset({"project", "job", "internship", "activity", "award"})
FieldKind = Literal[
    "personal", "department", "grade", "status", "education", "training", "certification",
    "job", "internship", "career", "project", "activity", "award", "skill", "interest",
    "goal", "narrative", "unknown",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)


class Fact(Contract):
    id: Identifier
    kind: FactKind
    value: ShortText
    source: Source
    detail: Message | None = None
    date: CalendarDate | None = None
    reference: ShortText | None = None
    field_key: Identifier | None = None
    progress: Progress | None = None


class Profile(Contract):
    mock: bool = False
    facts: list[Fact] = Field(default_factory=list)


class Condition(Contract):
    kind: Literal["department", "grade", "status", "skill", "certification", "other"]
    label: ShortText
    values: list[ShortText] = Field(default_factory=list, max_length=20)
    minimum: int | None = Field(default=None, ge=1, le=10)


class Opportunity(Contract):
    id: Identifier
    type: Literal["employment", "startup"]
    title: ShortText
    organization: ShortText
    description: Message
    deadline: AwareDatetime
    conditions: list[Condition] = Field(default_factory=list, max_length=30)
    documents: list[ShortText] = Field(default_factory=list, max_length=30)
    mock: bool = False
    source_url: Annotated[str, StringConstraints(pattern=r"^https?://[^\s]+$", max_length=2000)] | None = None
    version: int | None = Field(default=None, ge=1)


class SkillNode(Contract):
    job_id: Identifier
    job_name: ShortText
    skill_id: Identifier
    skill_name: ShortText
    description: Message
    prerequisites: list[ShortText] = Field(default_factory=list, max_length=20)
    learning_topics: list[ShortText] = Field(default_factory=list, max_length=20)
    importance: ShortText | None = None
    required: bool | None = None
    difficulty: ShortText | None = None
    mock: bool = False


class CareerRole(Contract):
    id: Identifier
    name: ShortText
    description: Message
    interests: list[ShortText] = Field(default_factory=list, max_length=20)
    mock: bool = False


class Screen(Contract):
    startup_node_id: Identifier | None = None
    page: Identifier = "home"
    job_id: Identifier | None = None
    skill_id: Identifier | None = None
    opportunity_id: Identifier | None = None
    document_id: Identifier | None = None


class RetrievalSelection(Contract):
    query: str = Field(max_length=600)
    posting_ids: list[Identifier] = Field(default_factory=list, max_length=2000)


class ChatRequest(Contract):
    retrieval: RetrievalSelection | None = None
    mode: Literal["startup_intake"] | None = None
    message: Message
    context: Screen = Field(default_factory=Screen)
    conversation_id: Identifier = "default"
    request_id: Identifier | None = None


class MemoryEdit(Contract):
    kind: MemoryKind
    value: ShortText
    detail: Message | None = None
    date: CalendarDate | None = None
    progress: Progress | None = None

    @model_validator(mode="after")
    def valid_progress(self):
        if self.progress and (
            self.kind not in ("certification", "skill", "training")
            and not (self.kind in EXPERIENCE_KINDS and self.progress == "not_held")
            or self.kind == "certification" and self.progress in ("beginner", "intermediate")
            or self.date and self.progress in ("preparing", "not_held")
        ):
            raise ValueError("기억 종류와 진행 상태를 확인해 주세요.")
        return self


class ConditionResult(Contract):
    label: str
    verdict: Literal["pass", "fail", "check"]
    reason: str


class AssessedOpportunity(Contract):
    id: Identifier
    type: Literal["employment", "startup"]
    title: str
    organization: str
    description: str
    deadline: datetime
    open: bool
    conditions: list[ConditionResult]
    documents: list[str]
    mock: bool
    source_url: str | None
    version: int | None


class DocumentReference(Contract):
    id: Identifier
    revision: int
    filled: list[str] = Field(default_factory=list)
    needs_confirmation: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)


class ChatResult(Contract):
    startup_plan_updated: bool = False
    answer: str
    conversation_id: Identifier
    mock_data: bool = False
    memory_updated: bool = False
    needs_confirmation: list[str] = Field(default_factory=list)
    context_issues: list[str] = Field(default_factory=list)
    opportunities: list[AssessedOpportunity] = Field(default_factory=list)
    document: DocumentReference | None = None


class NarrativeOptions(Contract):
    target_role: ShortText | None = None
    min_characters: int | None = Field(default=None, ge=1, le=3900)
    max_characters: int | None = Field(default=None, ge=1, le=3900)

    @model_validator(mode="after")
    def valid_length(self):
        if self.min_characters and self.max_characters and self.min_characters > self.max_characters:
            raise ValueError("최소 글자 수는 최대 글자 수 이하여야 합니다.")
        return self


class NarrativeContext(NarrativeOptions):
    question: Literal["motivation", "introduction", "strengths", "experience"]


class Turn(Contract):
    timestamp: datetime
    message: str
    result: ChatResult
    context: Screen
    topic_opportunity_id: Identifier | None = None
    topic_document_id: Identifier | None = None
    request_id: Identifier | None = None
    request_fingerprint: str | None = None
    memory_evidence: bool = False
    narrative_prompt: Message | None = None
    narrative_context: NarrativeContext | None = None
    narrative_field_ids: list[Identifier] = Field(default_factory=list)
    narrative_source_ids: list[Identifier] = Field(default_factory=list)
    awaiting_narrative_evidence: bool = False


class Conversation(Contract):
    turns: list[Turn] = Field(default_factory=list)
    summary: str = ""
    example_names: list[ShortText] = Field(default_factory=list)


class TemplateField(Contract):
    id: Identifier
    label: ShortText
    kind: FieldKind = "unknown"


class TemplateInput(Contract):
    fields: list[TemplateField] = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def unique_fields(self):
        if len({field.id for field in self.fields}) != len(self.fields):
            raise ValueError("문서 필드 ID는 서로 달라야 합니다.")
        return self


class DraftField(Contract):
    field: TemplateField
    status: Literal["filled", "confirmation", "missing", "draft", "edited", "unsupported"]
    value: str | None = None
    sources: list[Fact] = Field(default_factory=list)
    suggestions: list[Fact] = Field(default_factory=list)
    note: str | None = None


class Draft(Contract):
    revision: int
    fields: list[DraftField]
    mock_data: bool = False


class DraftRequest(NarrativeOptions):
    field_ids: list[Identifier] | None = Field(default=None, min_length=1, max_length=80)
    narrative_prompt: Message | None = None


class NarrativeRequest(NarrativeOptions):
    topic: Message


class NarrativeResult(Contract):
    draft: DraftField
    mock_data: bool = False


class DraftEdit(Contract):
    revision: int = Field(ge=1)
    values: dict[Identifier, FieldValue] = Field(min_length=1, max_length=80)


class DocumentRecord(Contract):
    id: Identifier
    filename: str
    format: Literal["docx", "pdf", "json"]
    fields: list[TemplateField]
    warnings: list[str] = Field(default_factory=list)
    draft: Draft | None = None


class UserState(Contract):
    startup_plan: StartupPlan | None = None
    revision: int = 0
    memory: list[Fact] = Field(default_factory=list)
    conversations: dict[Identifier, Conversation] = Field(default_factory=dict)
    documents: dict[Identifier, DocumentRecord] = Field(default_factory=dict)
