"""Grounded, editable drafts for one verified Catholic University application."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TEMPLATE_URL = "https://www.catholic.ac.kr/ko/campuslife/notice.do?articleNo=277684&attachNo=227459&mode=download"
LABELS = {"name": "아이템명", "overview": "아이템 개요", "problem": "문제 인식(Problem)"}
FieldId = Literal["name", "overview", "problem"]


class ApplicationField(BaseModel):
    value: str = ""
    status: Literal["draft", "edited", "missing"] = "missing"
    sources: list[str] = Field(default_factory=list)
    input_snapshot: dict[str, str] = Field(default_factory=dict)


class StartupApplication(BaseModel):
    template_id: Literal["cuk-global-2026"] = "cuk-global-2026"
    source_url: str = TEMPLATE_URL
    project_id: str
    goal_id: str
    feedback: str = ""
    fields: dict[FieldId, ApplicationField] = Field(default_factory=dict)


class ApplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    action: Literal["generate", "save"]
    field_ids: list[FieldId] | None = Field(default=None, min_length=1, max_length=3)
    values: dict[FieldId, str] = Field(default_factory=dict, max_length=3)
    feedback: str | None = Field(default=None, max_length=3000)


def inputs(plan, application, field_id):
    """Capture only facts that the particular field uses, for staleness checks."""
    if field_id == "name":
        return {"아이디어": plan.idea}
    if field_id == "overview":
        return {"아이디어": plan.idea, "대상 고객": plan.customer, "보유 결과물": plan.artifacts}
    return {"학생이 기록한 고객 피드백": application.feedback}


def apply_request(plan, request):
    from .privacy import redact

    application = plan.application or StartupApplication(project_id=plan.project_id, goal_id=plan.goal_id)
    if request.feedback is not None:
        application.feedback = redact(request.feedback).strip()
    for key, value in request.values.items():
        if len(value) > 6000:
            raise ValueError("문항별 초안은 6,000자까지 저장할 수 있어요.")
        application.fields[key] = ApplicationField(
            value=redact(value).strip(), status="edited", sources=["사용자 직접 수정"],
            input_snapshot=inputs(plan, application, key))
    if request.action == "generate":
        for key in request.field_ids or list(LABELS):
            previous = application.fields.get(key)
            if previous and previous.status == "edited":
                continue
            facts = inputs(plan, application, key)
            if key == "name":
                value = plan.idea
            elif key == "overview":
                value = f"{plan.idea}의 대상 고객은 {plan.customer}입니다."
                if plan.artifacts and plan.artifacts not in ("없음", "없어요", "아직 없음"):
                    value += f" 팀이 등록한 현재 보유 결과물은 ‘{plan.artifacts}’입니다."
            else:
                value = ("팀이 기록한 고객 피드백은 다음과 같습니다.\n" + application.feedback
                         if application.feedback else "")
            application.fields[key] = ApplicationField(value=value, status="draft" if value else "missing",
                sources=[label for label, text in facts.items() if text], input_snapshot=facts)
    plan.application = application
    return plan


def application_view(plan):
    """Derived metadata never changes the stored student edits."""
    if not plan or not plan.application:
        return None
    return {key: field.input_snapshot != inputs(plan, plan.application, key)
            for key, field in plan.application.fields.items()}
