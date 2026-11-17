import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import tidy  # noqa: E402


def posting():
    return {
        "id": "w24-1", "title": "신입 공채",
        "sections": [
            {"id": "§1", "title": "모집 분야", "text": "[영업] 해외영업 (경력: 신입, 학력: 박사)"},
            {"id": "§2", "title": "지원 자격", "text": "응시자격\n- 4년제 대학교 졸업(예정)자\n- TOEIC 700점 이상\n- 남자의 경우 병역필 또는 면제자\n- 무역 관련 자격증 소지자 우대"},
            {"id": "§3", "title": "전형 절차", "text": "서류전형 → 면접"},
        ],
        "required": [{"key": "degree", "label": "학력 조건은 원문에서 확인", "degree": "unknown", "src": "§1"}, {"key": "other", "label": "응시자격", "src": "§2"}],
        "facts": [{"label": "우대 사항", "value": "공고 화면에 명시 없음"}],
    }


AI = [
    {"category": "학력", "label": "4년제 졸업(예정)", "kind": "required", "quote": "4년제 대학교 졸업(예정)자", "degree": "bachelor"},
    {"category": "어학", "label": "토익 700점 이상", "kind": "required", "quote": "TOEIC 700점 이상", "skill": "SK-TOEIC", "min": "700"},
    {"category": "병역", "label": "병역필 또는 면제", "kind": "required", "quote": "남자의 경우 병역필 또는 면제자"},
    {"category": "자격증", "label": "무역 자격증 우대", "kind": "preferred", "quote": "무역 관련 자격증 소지자 우대"},
    {"category": "어학", "label": "오픽 AL 필수", "kind": "required", "quote": "OPIc AL 이상 필수", "skill": "SK-OPIC", "min": "AL"},
    {"category": "자격증", "label": "없는 자격", "kind": "required", "quote": "TOEIC 700점 이상", "skill": "SK-NOPE"},
]


def fake(conditions):
    return lambda prompt, schema: [{"id": "w24-1", "conditions": conditions}]


def test_conditions_are_tidied_and_only_quoted_ones_are_kept():
    p = tidy.tidy_batch([posting()], fake(AI))[0]
    assert [(c["key"], c["label"]) for c in p["required"]] == [
        ("degree", "4년제 대학 졸업(예정) 이상"),
        ("skill", "토익 700점 이상"),
        ("other", "병역: 병역필 또는 면제"),
        ("other", "자격증: 없는 자격"),
    ]
    assert p["required"][1] == {"label": "토익 700점 이상", "src": "§2", "key": "skill", "skill": "SK-TOEIC", "min": "700"}
    assert all("오픽" not in c["label"] for c in p["required"])  # 원문에 없는 구절은 버린다
    assert p["facts"][0] == {"label": "우대 사항", "value": "자격증: 무역 자격증 우대"} and p["conditionsBy"] == "ai"


def test_rule_conditions_are_kept_when_ai_gives_nothing_usable():
    for conds in ([], [{"category": "기타", "label": "지어낸 조건", "kind": "required", "quote": "원문에 없는 말입니다"}]):
        p = tidy.tidy_batch([posting()], fake(conds))[0]
        assert [c["label"] for c in p["required"]] == ["학력 조건은 원문에서 확인", "응시자격"] and p["conditionsBy"] == "rule"


def test_source_text_excludes_unrelated_sections():
    text = tidy.source_text(posting())
    assert "병역필" in text and "서류전형" not in text


def test_quote_with_small_wording_changes_is_accepted_but_invented_words_are_not():
    near = {"category": "병역", "label": "병역필 또는 면제", "kind": "required", "quote": "남자는 병역필 또는 면제자"}
    far = {"category": "어학", "label": "오픽 AL", "kind": "required", "quote": "오픽 AL 등급 보유자"}
    p = tidy.tidy_batch([posting()], fake([near, far]))[0]
    assert [c["label"] for c in p["required"]] == ["병역: 병역필 또는 면제"]


def kst(stage, age):
    return {
        "id": "kst-1", "title": "입주기업 모집",
        "sections": [{"id": "§1", "title": "신청 대상", "text": "성남시에 거주하거나 사업장이 있는 예비 또는 3년 이내 창업자"}, {"id": "§2", "title": "지원 분야·지역", "text": "지원 분야: 시설"}],
        "required": [{"key": "other", "label": "신청 대상: 대학생,일반인", "src": "§1"}],
        "facts": [{"label": "창업 단계(업력)", "value": stage}, {"label": "대상 연령", "value": age}],
    }


ALL_AGE = "만 20세 미만,만 20세 이상 ~ 만 39세 이하,만 40세 이상"


def test_startup_stage_age_and_region_become_checkable_conditions():
    ai = [
        {"category": "지역", "label": "성남시 거주 또는 사업장", "kind": "required", "quote": "성남시에 거주하거나 사업장이 있는", "regions": ["경기"]},
        {"category": "창업 단계", "label": "예비 또는 3년 이내", "kind": "required", "quote": "예비 또는 3년 이내 창업자"},
    ]
    p = tidy.tidy_batch([{**kst("예비창업자,1년미만,2년미만,3년미만", "만 20세 이상 ~ 만 39세 이하"), "id": "kst-1"}], lambda a, b: [{"id": "kst-1", "conditions": ai}])[0]
    assert [(c["key"], c["label"]) for c in p["required"]] == [
        ("startup", "창업 단계: 예비창업자 · 창업 3년 미만"),
        ("age", "연령: 만 20~39세"),
        ("region", "지역: 성남시 거주 또는 사업장"),
    ]
    assert p["required"][0]["stages"] == ["예비창업자", "1년미만", "2년미만", "3년미만"] and p["required"][2]["regions"] == ["경기"]


def test_no_startup_condition_when_unrestricted():
    assert tidy.startup_conditions(kst("예비창업자,1년미만,2년미만,3년미만,5년미만,7년미만,10년미만", ALL_AGE)) == []
    only = tidy.startup_conditions(kst("7년미만", ALL_AGE))
    assert [(c["key"], c["label"]) for c in only] == [("startup", "창업 단계: 창업 7년 미만")]
