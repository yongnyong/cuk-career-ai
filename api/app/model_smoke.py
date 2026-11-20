"""Explicit live inference check: python -m app.model_smoke (uses one model call)."""
import json
from .ai_provider import generate_json, provider_name

if __name__ == '__main__':
    output = generate_json('연결 확인용 가상 입력입니다. ok를 true로 반환하세요.',
        {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False})
    if output != {'ok': True}:
        raise SystemExit('Unexpected inference response')
    print(json.dumps({'provider': provider_name(), 'status': 'completed', 'response': output}))
