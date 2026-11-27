"""Validated, cached model proposals. Model output never supplies evidence or completion."""
import hashlib
import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .errors import ModelUnavailable
from .model import generate_for
from .privacy import redact
from .prompts import object_schema
from .startup_node_prompt import COMMON, INSTRUCTION, PROMPT_VERSION, SECTIONS

logger = logging.getLogger(__name__)


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,47}$")
    section: Literal["공통 준비", "고객·시장 검증", "아이템 구체화", "사업화 준비"]
    title: str = Field(min_length=4, max_length=90)
    completion: str = Field(min_length=15, max_length=500)
    reason: str = Field(min_length=10, max_length=300)
    priority: int = Field(ge=1, le=3)
    depends_on: list[str] = Field(max_length=5)


def context(plan):
    return {"facts": {k: redact(getattr(plan, k)) for k in ("idea", "customer", "artifacts", "goal")},
            "project_id": plan.project_id,
            "opportunity": plan.opportunity.model_dump() if plan.opportunity else None}


def fingerprint(plan):
    return hashlib.sha256((PROMPT_VERSION + json.dumps(context(plan), sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def generate_nodes(plan, model):
    from .startup_plan import PlanNode
    text = {"type": "STRING"}
    item = object_schema(key=text, section={"type": "STRING", "enum": list(SECTIONS)},
                         title=text, completion=text, reason=text,
                         priority={"type": "INTEGER"}, depends_on={"type": "ARRAY", "items": text})
    data = context(plan)
    data["existing_nodes"] = [{"key": n.action.removeprefix("generated:"), "title": n.title,
                               "completed": n.completed, "output": n.completion}
                              for n in plan.nodes if n.project_id == plan.project_id][:30]
    # Redact both persisted facts and source/document text before leaving the server.
    data = json.loads(redact(json.dumps(data, ensure_ascii=False)))
    try:
        response = generate_for(model, "startup_nodes", INSTRUCTION, data,
                                object_schema(nodes={"type": "ARRAY", "items": item}))
        if not isinstance(response, dict) or set(response) != {"nodes"} or not isinstance(response["nodes"], list):
            raise ValueError("invalid envelope")
        if not 6 <= len(response["nodes"]) <= 15:
            raise ValueError("invalid node count")
        proposals = [Proposal.model_validate(n) for n in response["nodes"]]
        by_key = {n.key: n for n in proposals}
        if len(by_key) != len(proposals) or len({n.title.strip() for n in proposals}) != len(proposals):
            raise ValueError("duplicate nodes")
        if sorted(n.title for n in proposals if n.section == SECTIONS[0]) != sorted(COMMON):
            raise ValueError("invalid common foundation")
        if any(not 1 <= sum(n.section == section for n in proposals) <= 4 for section in SECTIONS[1:]):
            raise ValueError("missing or excessive section")
        ordered, visiting, visited = [], set(), set()
        def visit(key):
            if key not in by_key or key in visiting:
                raise ValueError("missing dependency or cycle")
            if key in visited:
                return
            visiting.add(key)
            for dependency in by_key[key].depends_on:
                visit(dependency)
            visiting.remove(key)
            visited.add(key)
            ordered.append(by_key[key])
        for n in sorted(proposals, key=lambda n: n.priority):
            visit(n.key)
        def node_id(key):
            return "SUP-G-" + hashlib.sha256((plan.project_id + "|" + key).encode()).hexdigest()[:16]
        old = {n.id: n for n in plan.nodes if n.project_id == plan.project_id}
        nodes = []
        for p in ordered:
            identity = node_id(p.key)
            if identity in old and old[identity].completed:
                node = old[identity].model_copy(deep=True)
                node.active = True
            else:
                node = PlanNode(id=identity, action="generated:" + p.key, title=redact(p.title),
                    completion=redact(p.completion), reason=redact(p.reason), output=p.key,
                    project_id=plan.project_id, goal_id=plan.goal_id, section=p.section,
                    stage=SECTIONS.index(p.section), requires=[node_id(k) for k in p.depends_on],
                    reuse=[node_id(k) for k in p.depends_on])
            nodes.append(node)
        return nodes
    except (ValueError, OSError, ModelUnavailable) as exc:
        logger.info("startup_nodes generation=failed error=%s", getattr(exc, "code", type(exc).__name__))
        return None
