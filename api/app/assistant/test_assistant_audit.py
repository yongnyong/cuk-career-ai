"""Multi-turn audit of the chat service with synthetic data and zero network calls."""

import re
import sqlite3

import pytest

from . import model
from .contracts import ChatRequest, Fact, Profile
from .errors import ModelTimeout, StorageUnavailable
from .prompts import CONSULTATION
from .test_chat import FakeModel, update
from .test_documents import json_template
from .test_skill_lab import AI, DE, PIPELINE, lab_service

PANDAS = {"page": "tree", "job_id": AI, "skill_id": "mock-pandas"}
NUMPY = {"page": "tree", "job_id": AI, "skill_id": "mock-numpy"}
DATA = {"page": "tree", "job_id": DE, "skill_id": PIPELINE}
MEMORY = "memory"
CHAT = "consultation"
NARRATIVE = "narrative"


class AuditModel(FakeModel):
    def __init__(self):
        super().__init__()
        self.stages = []

    def generate(self, instruction, data, schema):
        self.stages.append(model._STAGE.get())
        generated = super().generate(instruction, data, schema)
        if self.stages[-1] == "consultation_with_memory":
            return {**generated, "updates": self.updates.get(data["message"], [])}
        return generated


def block_transport(*args, **kwargs):
    pytest.fail("Unexpected real Gemini transport call")


class AuditSession:
    def __init__(self, service):
        self.service = service
        self.model = service.model

    def turn(self, message, stages=(CHAT,), *, screen=None, user="alice", conversation="audit",
             answer=None, updates=None, memory=False):
        request = ChatRequest(message=message, context=screen or {}, conversation_id=conversation)
        paths = len(self.model.stages)
        before = self.service.store.get_state(user)
        self.model.answer = {"answer": answer} if isinstance(answer, str) else answer or {
            "answer": "확인할 수 있는 내용부터 차근히 살펴봐요.",
        }
        if updates is not None:
            self.model.updates[message] = updates
        reply = self.service.chat(user, request)
        after = self.service.store.get_state(user)
        assert tuple(self.model.stages[paths:]) == stages
        assert after.revision == before.revision + 1
        assert reply.memory_updated == memory == (after.memory != before.memory)
        prior = before.conversations.get(conversation)
        history = after.conversations[conversation].turns
        assert len(history) == (len(prior.turns) if prior else 0) + 1
        assert history[-1].context == request.context and history[-1].result == reply
        assert reply.answer.strip() and reply.conversation_id == conversation
        return reply

    @property
    def data(self):
        return self.model.calls[-1][1]


@pytest.fixture
def audit(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "urlopen", block_transport)
    return AuditSession(lab_service(tmp_path / "local", AuditModel()))


def body(reply, limit):
    title, text, *_ = reply.answer.splitlines()
    assert title == "[AI 초안]" and 0 < len(text) <= limit
    return text


def schedule(count, minutes, task="예시 데이터의 값 한 개를 확인해요."):
    return {"answer": "요청한 기간의 실습 흐름이에요.", "schedule": [
        {"task": task, "minutes": minutes, "done": f"{day}일차 결과를 작업 노트에 남겨요."}
        for day in range(1, count + 1)
    ]}


def test_audit_career_comparison_memory_and_tree(audit):
    audit.turn("안뇽? 진로 상담 가능?", answer="네. 관심 있는 업무부터 살펴볼 수 있어요.")
    question = "데이터 분석가랑 데이터 엔지니어 차이 뭐임?"
    plain = "데이터 분석가는 지표를 해석하고, 데이터 엔지니어는 처리 흐름을 구축해요."
    assert audit.turn(question, answer=plain).answer == plain
    claim = "나는 데이터 분석에 관심이 있어. 이 내용을 기억해줘."
    audit.turn(claim, (MEMORY,), updates=[update("interest", "add", "데이터 분석", claim.split(". ")[0])], memory=True)
    audit.turn("그중 내게 더 잘 맞는 데이터 분석가와 데이터 엔지니어는 어느 쪽일까?", answer=plain)
    assert any(f["kind"] == "interest" and f["provenance"] == "user_statement" for f in audit.data["facts"])
    assert "Python 기초" in audit.turn("선수학습 알려줘?", (), screen=PANDAS).answer
    compared = audit.turn("이전 노드랑 차이가 뭐야?", screen=DATA, answer="표 정리와 데이터 흐름 설계의 차이가 있어요.")
    assert compared.mock_data and audit.data["comparisonSkill"]["jobId"] == AI
    recalled = audit.turn("내가 직접 말한 관심 분야 알려줘.", (), screen=DATA)
    assert "데이터 분석" in recalled.answer and "말씀하셨어요" in recalled.answer
    previous, = audit.service.memory("alice")
    remove = "전에 말한 데이터 분석 관심은 삭제해줘."
    current = "나는 로보틱스에 관심 있어."
    audit.turn(f"{remove} {current} 이 내용을 기억해줘.", (MEMORY,), memory=True, updates=[
        update("interest", "remove", "데이터 분석", remove, target_id=previous.id),
        update("interest", "add", "로보틱스", current),
    ])
    recalled = audit.turn("내가 직접 말한 관심 분야 알려줘.", ())
    assert "로보틱스" in recalled.answer and "데이터 분석" not in recalled.answer


def test_audit_draft_correction_and_return(audit):
    draft = audit.turn("데이터 분석 직무 지원동기 300자 이내로 써줘. 가상 경력은 빼줘.", ())
    assert "데이터 분석" in body(draft, 300)
    claim = "나 SQLD 취득했어."
    audit.turn(claim, (MEMORY, CHAT), updates=[update("certification", "add", "SQLD", claim)], memory=True)
    correction = "나 SQLD 자격증을 취득했어. 사실 취득한 건 아니고 지금 준비 중이야. 내가 취득한 자격증은 뭐야?"
    corrected = audit.turn(correction, (MEMORY,), updates=[], memory=True)
    assert "준비 중" in corrected.answer and "취득 기록은 없어요" in corrected.answer
    audit.turn("데이터 엔지니어는 무슨 일을 하나요?", answer="데이터가 들어오고 전달되는 흐름을 설계해요.")
    revision = audit.turn("아까 지원동기를 100자 이내로 줄이고 SQLD 준비 중인 점을 반영해줘.", ())
    assert "SQLD 자격증을 준비 중" in body(revision, 100)
    expanded = audit.turn("이전 지원동기를 500자 이내로 다시 작성해줘. 지원 직무를 데이터 엔지니어로 바꿔줘.", ())
    assert "데이터 엔지니어" in body(expanded, 500) and "Campus Data Lab" not in expanded.answer


def test_audit_week_plan_timebox_and_next_exercise(audit):
    first = audit.turn("Pandas를 7일 동안 공부할 계획은 어떻게 세울까?", screen=PANDAS, answer=schedule(7, 35))
    assert first.answer.count("일차 ·") == 7
    revised = audit.turn("하루 20분밖에 못 하고 너무 부담스러워요.", (MEMORY, CHAT), screen=PANDAS,
                         answer=schedule(7, 20), updates=[])
    assert audit.data["practiceRequest"] == {"mode": "adjust", "days": 7, "dailyMinutes": 20}
    assert all(int(value) <= 20 for value in re.findall(r"일차 · (\d+)분", revised.answer))
    activity = {"answer": "오늘은 표 한 개를 만들어요.", "exercise": {
        "task": "값 세 개를 입력하고 출력해요.", "minutes": 10, "done": "세 행이 출력되면 끝이에요.",
    }}
    audit.turn("오늘 당장 할 일 하나만 알려줄래?", screen=PANDAS, answer=activity)
    assert audit.data["practiceRequest"]["dailyMinutes"] == 20
    audit.turn("방금 실습을 제대로 끝냈는지 어떻게 확인해?", screen=PANDAS, answer="출력에 행이 세 개 있는지 세어 보세요.")
    assert audit.data["practiceRequest"]["verify"] and any(
        "세 행" in turn["assistant"] for turn in audit.data["conversation"]["recent"] if turn.get("priorPractice")
    )
    audit.turn("첫 실습은 마쳤어요. 다음 실습 하나만 추천해줄래요?", (MEMORY, CHAT), screen=PANDAS,
               updates=[], answer={**activity, "exercise": {**activity["exercise"], "task": "표의 첫 열만 출력해요."}})
    assert audit.data["practiceRequest"]["mode"] == "task"


def test_audit_fixture_is_not_real_application_evidence(audit):
    query = "내가 직접 말한 프로젝트 경험과 가상 기록을 구분해 알려줘."
    reply = audit.turn(query, ())
    assert "Campus Data Lab" in reply.answer.split("가상 사용자 데이터", 1)[1]
    negative = "나는 데이터 분석 프로젝트를 해 본 경험이 없어. 이 내용을 기억해줘."
    audit.turn(negative, (MEMORY,), updates=[update("project", "add", "데이터 분석 프로젝트",
               negative.split(". ")[0], progress="not_held")], memory=True)
    reply = audit.turn(query, ())
    assert "해 본 경험이 없다고" in reply.answer and "Campus Data Lab" in reply.answer.split("가상 사용자 데이터", 1)[1]
    draft = audit.turn("데이터 분석 직무 지원동기 300자 이내로 작성해줘. 실제 경험만 사용해줘.", ())
    assert "Campus Data Lab" not in body(draft, 300)
    experience = audit.turn("실제 프로젝트 경험 중심 자기소개서 문항을 작성해줘.", ())
    assert "[AI 초안]" not in experience.answer and "Campus Data Lab" not in experience.answer
    owned = "나는 지역 통계 프로젝트에 참여해서 공개 통계 표 정리를 맡았어."
    audit.turn(f"{owned} 이 내용을 기억해줘.", (MEMORY,), memory=True, updates=[
        update("project", "add", "지역 통계 프로젝트", owned, detail="공개 통계 표 정리를 맡았어"),
    ])
    project = next(fact for fact in audit.service.memory("alice") if fact.value == "지역 통계 프로젝트")
    audit.model.fact_ids = [project.id, "demo-project"]
    with_experience = audit.turn("지역 통계 프로젝트 경험 중심 자기소개서를 300자 이내로 작성해줘.", (NARRATIVE,))
    assert "지역 통계 프로젝트" in body(with_experience, 300) and "Campus Data Lab" not in with_experience.answer
    assert {fact["id"] for fact in audit.data["facts"]} == {project.id}


def test_audit_node_selection_sources_and_cross_job_comparison(audit):
    audit.turn("이 기술 개념 좀 설명해 줄래?", screen=PANDAS, answer="Pandas는 표를 다뤄요.")
    assert audit.data["selectedSkill"]["skillName"] == "Pandas"
    following = audit.turn("후속 노드가 뭐야?", (), screen=PANDAS)
    assert "특성 공학" in following.answer and following.mock_data
    audit.turn("NumPy랑 뭐가 달라?", screen=PANDAS,
               answer="NumPy는 Pandas의 선수학습이에요. 배열과 표의 용도를 비교해요.")
    assert audit.data["serverShowsRelationships"] and audit.data["comparisonSkill"]["skillName"] == "NumPy"
    audit.turn("이전 노드와 현재 노드의 차이는?", screen=DATA, answer="표를 다루는 작업과 흐름을 설계하는 작업은 달라요.")
    assert audit.data["comparisonSkill"]["jobId"] == AI
    result = audit.turn("AI 엔지니어와 데이터 엔지니어 스킬트리 비교해 줄래?", screen={"page": "tree", "job_id": DE})
    assert result.mock_data and {item["skillName"] for item in audit.data["skillTreeComparison"]["sharedSkills"]} == {"Python 기초", "SQL"}
    audit.turn("아까 Pandas 스킬의 활용은 어떤가요?", answer="정리하거나 요약할 표를 다룰 때 활용해요.")
    assert audit.data["priorSkill"]["skillId"] == "mock-pandas"


def test_audit_users_conversations_and_storage_roots_are_isolated(audit, tmp_path):
    message = "Python 기초 문법만 알아. 이 내용을 기억해줘."
    audit.turn(message, (MEMORY,), updates=[update("skill", "add", "Python", "Python 기초 문법만 알아.",
               progress="beginner")], memory=True)
    look = "내가 직접 말한 Python 실력을 알려줘."
    assert "Python" in audit.turn(look, ()).answer
    assert "기초" in audit.turn(look, (), conversation="other").answer
    assert "저장돼 있지" in audit.turn(look, (), user="bob").answer
    bob = "나는 SQL이 중급 수준이야. 이 내용을 기억해줘."
    audit.turn(bob, (MEMORY,), user="bob", updates=[update("skill", "add", "SQL", bob.split(". ")[0],
               progress="intermediate")], memory=True)
    assert {fact.value for fact in audit.service.memory("alice")} == {"Python"}
    assert {fact.value for fact in audit.service.memory("bob")} == {"SQL"}
    other_store = lab_service(tmp_path / "independent", AuditModel())
    assert not other_store.memory("alice") and not other_store.store.get_state("alice").conversations


def test_audit_unicode_named_example_and_subject_switch(audit):
    audit.turn("안녕! 진로 상담을 시작할 수 있을까?", (MEMORY, CHAT),
               answer="진로와 학습 중 먼저 궁금한 것을 살펴봐요.")
    example = "별빛정리"
    ask = f"예시 이름을 {example}라고 정하고 그대로 써 줄래요?"
    assert example in audit.turn(ask, answer=f"이름은 **{example}**예요.").answer
    audit.turn("Pythno\t입문용 🐍 도구라는 게 뭐야?", answer="Python 입문 예시를 질문하신 것으로 이해했어요.")
    assert "🐍" in audit.data["message"] and "Pythno" in audit.data["message"]
    audit.turn("데이터 파이프라인 다음 노드가 뭐야?", (), screen=DATA)
    result = audit.turn("아까 정한 그 이름을 다시 알려줄래?", screen={"page": "profile"}, answer=f"이름은 **{example}**예요.")
    assert example in result.answer and example in audit.data["exampleNames"]


def test_audit_active_skill_correction_after_switching_jobs(audit):
    first = "Python은 중급이라고 생각해. 이 내용을 기억해줘."
    audit.turn(first, (MEMORY,), updates=[update("skill", "add", "Python", first.split(". ")[0],
               progress="intermediate")], memory=True)
    earlier, = audit.service.memory("alice")
    audit.turn("Pandas를 먼저 배우면 어때?", screen=PANDAS)
    corrected = "Python은 사실 기초 문법만 알아. 이 내용을 기억해줘."
    audit.turn(corrected, (MEMORY,), updates=[update("skill", "set", "Python", corrected.split(". ")[0],
               progress="beginner", target_id=earlier.id)], screen=DATA, memory=True)
    assert [(f.id, f.progress, f.source) for f in audit.service.memory("alice")] == [(earlier.id, "beginner", "conversation")]
    audit.turn("이 노드부터 실습하려면 어떤 걸 연습하면 좋을까?", screen=DATA)
    assert any(record["progress"] == "beginner" and record["provenance"] == "user_statement"
               for skill in audit.data["learning"]["skillEvidence"] for record in skill["records"])
    recalled = audit.turn("내가 직접 말한 기술 수준을 알려줘.", (), screen=NUMPY)
    assert "기초" in recalled.answer and "중급" not in recalled.answer


def test_audit_sql_code_and_fourteen_day_timing(audit):
    plan = audit.turn("SQL 14일 학습 계획을 하루 1시간으로 어떻게 짜면 될까?", answer=schedule(14, 60))
    assert plan.answer.count("일차 · 60분") == 14 and audit.data["practiceRequest"]["dailyMinutes"] == 60
    shorter = audit.turn("아까 14일 계획을 하루 20분으로 바꾸고 3일로 줄여줄래?", answer=schedule(3, 20))
    assert "3일차" in shorter.answer and "4일차" not in shorter.answer
    assert any("14일차" in turn["assistant"] for turn in audit.data["conversation"]["recent"] if turn.get("priorPractice"))
    query = "SELECT SUM(amount) FROM sample;"
    audit.turn("오늘 할 일 하나만 부탁할게요?", answer={"answer": "합계 한 번만 구해요.", "exercise": {
        "task": f"예시 표에서 실행해요.\n```sql\n{query}\n```", "minutes": 10, "done": "30이 한 칸에 출력돼요.",
    }})
    with sqlite3.connect(":memory:") as db:
        db.executescript("CREATE TABLE sample(amount INTEGER); INSERT INTO sample VALUES (10), (20);")
        assert db.execute(query).fetchone() == (30,)
    audit.turn("그 SQL 실습을 제대로 끝냈는지 어떻게 확인해?", answer="결과가 30인 한 행인지 확인해요.")
    assert audit.data["practiceRequest"]["verify"]
    new = audit.turn("SQLD 자격증 하루 학습 계획은 어떻게 세우면 좋을까?", answer="개념 하나를 읽고 예제 한 문제를 풀어요.")
    assert "예제" in new.answer and audit.data["practiceRequest"]["mode"] == "plan"


def test_audit_document_roundtrip_and_consultation_do_not_mutate_original(audit):
    service = audit.service
    original = json_template()
    record = service.documents.upload("alice", "fixture.json", original)
    screen = {"page": "profile", "document_id": record.id}
    job = "데이터 분석 직무"
    audit.turn(f"{job} 지원동기 100자 이내로 작성해줘.", (), screen=screen)
    saved = service.documents.get("alice", record.id).draft
    assert saved and saved.revision == 1
    audit.turn("데이터 분석가는 어떤 일을 하나요?", answer="지표를 해석하고 결론을 전달해요.")
    assert service.documents.get("alice", record.id).draft == saved
    audit.turn("문서에서 어떤 항목이 비어 있는지 확인해줘.", (), screen=screen)
    audit.turn("아까 문서의 지원동기를 300자 이내로 다시 작성해줘.", (), screen=screen)
    changed = service.documents.get("alice", record.id).draft
    assert changed.revision == saved.revision + 1
    assert all(len(field.value or "") <= 300 for field in changed.fields)
    audit.turn("데이터 파이프라인 선수학습이 뭐야?", (), screen=DATA)
    assert service.store.get_original("alice", record.id) == original


def test_audit_model_and_store_failures_preserve_the_last_committed_turn(audit, monkeypatch):
    service = audit.service
    audit.turn("진로를 알아볼 수 있나요?")
    snapshot = service.store.get_state("alice")
    message = "나 SQLD 취득했어."
    audit.model.failures[CONSULTATION] = ModelTimeout("모의 시간 초과")
    with pytest.raises(ModelTimeout):
        service.chat("alice", ChatRequest(message=message, conversation_id="audit"))
    audit.model.failures.clear()
    assert service.store.get_state("alice") == snapshot
    with monkeypatch.context() as patch:
        def failed_write(*args):
            raise StorageUnavailable("모의 쓰기 실패")
        patch.setattr(service.store, "save_state", failed_write)
        with pytest.raises(StorageUnavailable):
            service.chat("alice", ChatRequest(message="이 내용을 기억해줘.", conversation_id="audit"))
    assert service.store.get_state("alice") == snapshot
    audit.turn(message, (MEMORY, CHAT), memory=True)
    assert "확인이 필요한 기록 · SQLD" in audit.turn("내가 취득한 자격증은 뭐야?", ()).answer
    audit.turn("축약해서 설명해 줄래?", answer="취득은 사용자 진술로 기록돼요.")
    audit.turn("선택한 노드의 후속 노드는 뭐야?", (), screen=DATA)


def test_audit_verified_claimed_and_mock_certificates_remain_distinct(audit):
    data = audit.service.data
    data.profiles["demo001"] = Profile(facts=[Fact(id="audit-official", kind="certification", value="정보처리기사", source="official")])
    request = "내 자격증을 공식 확인과 사용자 주장으로 구분해 알려줘."
    official = audit.turn(request, ())
    assert "공식 확인 기록 · 정보처리기사" in official.answer and not official.mock_data
    audit.turn("나 SQLD 취득했어.", (MEMORY, CHAT), memory=True)
    report = audit.turn(request, ())
    assert "확인이 필요한 기록 · SQLD" in report.answer and "공식 확인 기록 · 정보처리기사" in report.answer
    simulated = audit.turn(request, (), user="bob")
    assert simulated.mock_data and "정보처리기사" not in simulated.answer
    audit.turn("데이터 엔지니어 준비는 어떤 순서가 좋을까?", answer="기초 조회부터 연습하고 작은 데이터 흐름을 구성해 봐요.")
    assert all(fact.source != "official" for fact in audit.service.memory("alice"))
