"""Concrete startup work definitions and the artifacts each task can reuse."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    action: str
    title: str
    completion: str
    output: str
    stage: int
    uses: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()


def product_kind(idea: str) -> str:
    if re.search(r"AI|소프트웨어|앱|플랫폼|알고리즘|예측|자동화|SaaS", idea, re.I):
        return "software"
    if re.search(r"굿즈|의류|식품|음료|제품 제조|생활용품|키트|가구", idea):
        return "physical"
    if re.search(r"코칭|교육|컨설팅|클래스|레슨|돌봄|체험|상담 서비스", idea):
        return "service"
    return "unknown"


def artifact_types(text: str) -> set[str]:
    """Only explicit owned artifacts count. Unknown free text supplies no prerequisite."""
    if re.search(r"없|아직|미보유|미완성|안\s*만들", text):
        return set()
    found = set()
    if re.search(r"시제품|프로토타입|MVP|작동|구현|모듈|알고리즘|샘플", text, re.I):
        found.add("prototype")
    if re.search(r"도안|디자인|설계|커리큘럼", text):
        found.add("design")
    if re.search(r"시연본|시연 영상|고객.*시연.*완료", text):
        found.add("customer_demo")
    if re.search(r"인터뷰.*결과|고객.*검증.*결과|미팅.*기록", text):
        found.add("customer_findings")
    return found


def goal_intent(goal: str, hint: str = "") -> str:
    # Intent is independent of whether a prototype has already been supplied.
    rules = (
        ("competition", r"대회|경진|지원사업|패키지"),
        ("preorder", r"선주문|사전\s*판매|예약\s*판매"),
        ("launch", r"출시|런칭|론칭"),
        ("demo", r"시연|보여|데모"),
        ("meeting", r"미팅|첫\s*고객\s*만나"),
        ("customer", r"인터뷰|고객\s*조사|고객\s*검증"),
    )
    return next((intent for intent, pattern in rules if re.search(pattern, goal)),
                hint if hint in {"competition", "preorder", "launch", "demo", "meeting", "customer"} else "customer")


def task_for(plan, action: str) -> Task:
    kind = product_kind(plan.idea)
    subject = f"{plan.customer}용 {plan.idea}"
    tasks = {
        "customer": Task(action, f"{plan.customer} 첫 고객 미팅 질문지",
            f"{plan.idea}를 사용할 상황, 현재 해결 방법, 사용 의사를 확인할 질문과 미팅 결과 기록 양식을 저장하세요.",
            "interview_guide", 1),
        "prototype": Task(action, f"{subject} 핵심 사용 흐름 시제품",
            f"{plan.customer}가 {plan.idea}의 핵심 과업 하나를 처음부터 끝까지 실행하는 시제품과 실행 방법을 저장하세요.",
            "prototype", 2, ("design",)),
        "choose_opportunity": Task(action, "우리 팀이 지원할 창업 공고 선택",
            "공고 목록에서 팀의 목표에 맞는 공고를 골라 ‘이 공고 준비하기’를 누르세요. 신청 자격과 기한은 원문에서 확인하세요.",
            "chosen_opportunity", 1),
    }
    if action in tasks:
        return tasks[action]
    if action == "demo":
        criteria = {
            "software": "가상 입력 자료, 작동하는 결과, 고객이 수정할 수 있는 화면을 담은 시연본과 원본 파일을 저장하세요.",
            "physical": f"{plan.customer}가 샘플의 사용 방법, 크기·재질, 품질을 확인할 수 있는 시연 사진·영상과 고객 의견 기록을 저장하세요.",
            "service": f"{plan.customer}의 체험 순서, 제공 시간, 진행 자료와 체험 후 의견을 담은 서비스 시연 기록을 저장하세요.",
            "unknown": f"{plan.customer}가 {plan.idea}를 사용하는 핵심 과정과 결과, 고객 의견을 남길 방법을 담은 시연 자료를 저장하세요.",
        }
        return Task(action, f"{plan.customer} 미팅용 {plan.idea} 시연본",
                    criteria[kind], "customer_demo", 3, ("prototype",), ("prototype",))
    if action == "preorder":
        criteria = {
            "physical": f"{plan.idea}의 기존 도안과 수량별 가격, 제작 기간, 수령 방식을 담은 편집 가능한 주문 페이지를 저장하세요.",
            "software": f"{plan.customer}의 사용 시나리오, {plan.idea}의 체험 신청, 도입 가격 가설, 도입 문의 경로를 담은 사전판매 페이지를 저장하세요.",
            "service": f"{plan.customer}가 {plan.idea}의 제공 범위, 예약 일정, 가격과 취소 조건을 확인하고 예약할 수 있는 페이지를 저장하세요.",
            "unknown": f"{plan.customer}가 {plan.idea}의 제공 내용, 가격 가설, 제공 시기와 신청 경로를 확인할 수 있는 선주문 페이지를 저장하세요.",
        }
        return Task(action, "첫 선주문 상품 페이지 초안", criteria[kind], "offer", 4,
                    ("design", "customer_demo", "customer_findings"))
    if action == "launch":
        detail = {
            "physical": "제품 사진, 가격, 제작·수령 일정",
            "software": "핵심 기능 화면, 체험 방법, 도입 가격 가설",
            "service": "제공 범위, 예약 일정, 가격 가설",
            "unknown": "제공 내용, 사용 방법, 가격 가설",
        }[kind]
        return Task(action, f"{plan.idea} 첫 출시용 소개 페이지",
            f"{plan.customer}에게 보여줄 {detail}, 문의 경로를 담은 소개 페이지를 저장하세요.",
            "offer", 4, ("customer_demo", "customer_findings", "design"))
    raise ValueError("지원하지 않는 창업 행동입니다.")

