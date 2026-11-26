from types import SimpleNamespace

from app.assistant.contracts import ChatRequest
from app.assistant.service_data import MemoryAssistantStore
from app.assistant.startup_plan import StartupPlan, chat_plan, extract_fields


class OfflineModel:
    def generate(self, *args):
        raise OSError('model unavailable')


def test_service_description_advances_to_customer_without_inventing_one():
    service = SimpleNamespace(store=MemoryAssistantStore(), model=OfflineModel())
    message = '취/창업을 지원하는 AI 비서 컨셉의 웹사이트를 기획중이야'
    response = chat_plan(service, 'demo:intake', ChatRequest(message=message, mode='startup_intake'))
    plan = service.store.get_state('demo:intake').startup_plan
    assert plan.idea == message
    assert plan.customer == '' and plan.artifacts == '' and plan.goal == ''
    assert '누가 어떤 상황' in response.answer
    assert '어떤 제품이나 서비스' not in response.answer
    reply = chat_plan(service, 'demo:intake', ChatRequest(message='취업과 창업을 준비하는 대학생', mode='startup_intake'))
    assert service.store.get_state('demo:intake').startup_plan.customer == '취업과 창업을 준비하는 대학생'
    assert '준비된 결과물' in reply.answer
    reply = chat_plan(service, 'demo:intake', ChatRequest(message='아직 만든 건 없고 기획 단계야', mode='startup_intake'))
    assert service.store.get_state('demo:intake').startup_plan.artifacts == '없음'
    assert '다음으로 무엇' in reply.answer
    assert '공통 준비 트리를 열 수' not in reply.answer
    assert service.store.get_state('demo:other').startup_plan is None


def test_generic_description_and_short_reply_use_only_explicit_intake_context():
    plan = StartupPlan(idea='지역 서점 재고 관리 플랫폼')
    assert extract_fields('독립서점 점주', plan) == {}
    assert extract_fields('독립서점 점주', plan, expected='customer') == {'customer': '독립서점 점주'}
    for message in ('다른 팀이 만들면?', '아직 대상을 정하지 않았어', '모르겠어', '안녕', '네'):
        assert extract_fields(message, plan, expected='customer') == {}
    assert extract_fields('반려동물 산책 예약 앱을 만들고 있어', StartupPlan())['idea']
    assert 'customer' not in extract_fields('반려동물 산책 예약 앱을 만들고 있어', StartupPlan())


def test_intake_retries_are_idempotent():
    service = SimpleNamespace(store=MemoryAssistantStore(), model=OfflineModel())
    request = ChatRequest(message='도서 대여 웹사이트를 기획중이야', mode='startup_intake', request_id='first')
    first = chat_plan(service, 'demo:retry', request)
    again = chat_plan(service, 'demo:retry', request)
    assert first == again
    assert service.store.get_state('demo:retry').startup_plan.turns == 1


def test_model_uses_gemini_schema_and_blank_fields_do_not_erase_saved_facts():
    class Model:
        def generate(self, instruction, data, schema):
            assert schema['type'] == 'OBJECT'
            assert 'additionalProperties' not in schema
            assert all(p['type'] == 'STRING' for p in schema['properties'].values())
            assert data['asked_field'] == 'customer'
            return dict(idea='', customer='대학생', artifacts='', goal='', action='')
    plan = StartupPlan(idea='취창업 지원 웹사이트')
    fields = extract_fields('대학생', plan, Model(), expected='customer')
    assert fields == {'customer': '대학생'}
