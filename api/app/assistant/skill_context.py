"""Read catalog relationships and project a bounded part of the current role's tree."""
import re
from collections import deque
from collections.abc import Mapping, Sequence

from .contracts import CareerRole, SkillNode
from .privacy import catalog_text

_MAX_NODES = 14
_MAX_DISTANCE = 4
_MAX_EDGES = 32


def mentioned(name: str, text: str) -> bool:
    if len(name) < 2:
        return False
    if name.isascii():
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text, re.I) is not None
    return "".join(name.split()).casefold() in "".join(text.split()).casefold()


def skill_payload(node: SkillNode) -> dict:
    result = node.model_dump(by_alias=True, exclude_none=True)
    for key, value in result.items():
        if isinstance(value, str) and key not in ("jobId", "skillId"):
            result[key] = catalog_text(value)[:420]
        elif isinstance(value, list):
            result[key] = [catalog_text(item)[:120] for item in value[:12]]
    return result


class SkillTree:
    """Edges point from a prerequisite to the node that depends on it."""

    def __init__(self, nodes: Sequence[SkillNode], prerequisites: Mapping[str, Sequence[str]]):
        self.nodes = {node.skill_id: node for node in nodes}
        self.mock = any(node.mock for node in nodes)
        self.prerequisites = {}
        self.following: dict[str, list[str]] = {key: [] for key in self.nodes}
        self.incomplete = len(self.nodes) != len(nodes)
        self.declared = set(prerequisites) & self.nodes.keys()
        by_name: dict[str, list[str]] = {}
        for key, node in self.nodes.items():
            by_name.setdefault(node.skill_name, []).append(key)
        for key, node in self.nodes.items():
            if key in self.declared:
                raw = prerequisites[key]
                if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
                    parents = tuple(dict.fromkeys(parent for parent in raw if isinstance(parent, str)))
                    self.incomplete |= any(not isinstance(parent, str) for parent in raw)
                else:
                    parents = ()
                    self.incomplete = True
            else:
                matches = [by_name.get(label, []) for label in node.prerequisites]
                parents = tuple(dict.fromkeys(row[0] for row in matches if len(row) == 1))
                self.incomplete |= any(len(row) != 1 for row in matches)
            valid = tuple(parent for parent in parents if parent in self.nodes and parent != key)
            self.incomplete |= len(parents) != len(valid)
            self.prerequisites[key] = valid
            for parent in valid:
                self.following[parent].append(key)
        self.cycles = self._cycle_groups()
        if self.cycles:
            self.incomplete = True
            for key, group in self.cycles.items():
                for parent in self.prerequisites[key]:
                    if self.cycles.get(parent) == group:
                        self.following[parent].remove(key)
                self.prerequisites[key] = tuple(parent for parent in self.prerequisites[key]
                                                if self.cycles.get(parent) != group)

    def _cycle_groups(self) -> dict[str, str]:
        """Find mutually reachable nodes without recursion or the prompt depth limit."""
        finished = []
        visited = set()
        for root in self.nodes:
            pending = [(root, False)]
            while pending:
                key, expanded = pending.pop()
                if expanded:
                    finished.append(key)
                elif key not in visited:
                    visited.add(key)
                    pending.append((key, True))
                    pending.extend((child, False) for child in self.following[key])
        visited.clear()
        cycles = {}
        for root in reversed(finished):
            if root in visited:
                continue
            component, pending = [], [root]
            visited.add(root)
            while pending:
                key = pending.pop()
                component.append(key)
                for parent in self.prerequisites[key]:
                    if parent not in visited:
                        visited.add(parent)
                        pending.append(parent)
            if len(component) > 1:
                cycles.update(dict.fromkeys(component, root))
        return cycles

    @classmethod
    def from_catalog(cls, role: dict, skills: Mapping[str, dict], *, mock: bool = False):
        """Adapt the team's skill/prereq/required format without changing its IDs or graph."""
        nodes, parents = [], {}
        incomplete = False
        for item in role["nodes"]:
            skill_id = item.get("skill") if isinstance(item, dict) else None
            if not isinstance(skill_id, str) or skill_id in parents:
                incomplete = True
                continue
            skill = skills.get(skill_id)
            if not skill:
                incomplete = True
                continue
            raw = item.get("prereq", [])
            prerequisites = [key for key in raw if isinstance(key, str)] if isinstance(raw, list) else []
            incomplete |= "prereq" not in item or not isinstance(raw, list) or len(prerequisites) != len(raw)
            nodes.append(SkillNode(
                job_id=role["id"], job_name=role["name"], skill_id=skill_id,
                skill_name=skill["name"], description=skill.get("description") or skill["name"],
                prerequisites=[skills[key]["name"] for key in prerequisites if key in skills][:20],
                learning_topics=skill.get("learningTopics", [])[:20], importance=skill.get("importance"),
                required=item.get("required"), difficulty=skill.get("difficulty"), mock=mock,
            ))
            parents[skill_id] = prerequisites
        tree = cls(nodes, parents)
        tree.incomplete |= incomplete
        return tree

    def _nearby(self, start: str, links: Mapping[str, Sequence[str]], limit: int = _MAX_NODES) -> dict[str, int]:
        seen = {start: 0}
        remaining = deque([start])
        while remaining and len(seen) <= limit:
            node = remaining.popleft()
            if seen[node] == _MAX_DISTANCE:
                continue
            for adjacent in links[node]:
                if adjacent not in seen and len(seen) <= limit:
                    seen[adjacent] = seen[node] + 1
                    remaining.append(adjacent)
        del seen[start]
        return seen

    def node_payload(self, skill_id: str) -> dict:
        payload = skill_payload(self.nodes[skill_id])
        payload["prerequisites"] = [catalog_text(self.nodes[key].skill_name)[:120]
                                    for key in self.prerequisites[skill_id][:_MAX_NODES]]
        return payload

    def _edges(self, keys: Sequence[str]) -> list[dict]:
        included = set(keys)
        return [{"from": parent, "to": key} for key in keys
                for parent in self.prerequisites[key] if parent in included]

    def overview(self) -> dict:
        keys = list(self.nodes)[:_MAX_NODES]
        edges = self._edges(keys)
        return {
            "mock": self.mock, "nodeCount": len(self.nodes), "hasCycles": bool(self.cycles),
            "partial": self.incomplete or len(keys) < len(self.nodes) or len(edges) > _MAX_EDGES,
            "nodes": [
                {"skillId": key, "skillName": catalog_text(self.nodes[key].skill_name),
                 "required": self.nodes[key].required} for key in keys
            ],
            "edges": edges[:_MAX_EDGES],
        }

    def context(self, skill_id: str, question: str, related_questions: Sequence[str] = (),
                *, references: Sequence[str] = ()) -> dict:
        ancestors = self._nearby(skill_id, self.prerequisites)
        descendants = self._nearby(skill_id, self.following)
        reference = "\n".join((question, *related_questions))
        named_by_question = [key for key, node in self.nodes.items() if key != skill_id and (
            mentioned(node.skill_name, reference) or mentioned(key, reference)
        )]
        named = list(dict.fromkeys([*(key for key in references if key in self.nodes and key != skill_id),
                                   *named_by_question]))[:_MAX_NODES]
        direct = []
        parents, children = self.prerequisites[skill_id], self.following[skill_id]
        for index in range(min(_MAX_NODES, max(len(parents), len(children)))):
            direct.extend(keys[index] for keys in (parents, children) if index < len(keys))
        peers = [key for key, group in self.cycles.items() if key != skill_id and group == self.cycles.get(skill_id)]
        candidates = list(dict.fromkeys([*direct[:6], *named, *direct[6:], *ancestors, *descendants, *peers]))
        keys = [skill_id, *candidates[:_MAX_NODES - 1]]
        included = set(keys)
        edges = self._edges(keys)
        truncated = len(candidates) >= _MAX_NODES or len(edges) > _MAX_EDGES or any(
            any(adjacent not in included for adjacent in links[key])
            for key in keys for links in (self.prerequisites, self.following)
        )
        return {
            "source": "catalog", "mock": self.mock, "nodeCount": len(self.nodes),
            "partial": self.incomplete or truncated or len(keys) < len(self.nodes),
            "prerequisitesDeclared": skill_id in self.declared,
            "directPrerequisiteCount": len(parents), "directSuccessorCount": len(children),
            "cycleNearSelection": any(key in self.cycles for key in keys),
            "mentionedSkillIds": [key for key in named if key in included],
            "nearestAncestorHops": {key: ancestors[key] for key in keys if key in ancestors},
            "nearestSuccessorHops": {key: descendants[key] for key in keys if key in descendants},
            "nodes": [self.node_payload(key) for key in keys],
            "edges": edges[:_MAX_EDGES],
        }


class CatalogSkillData:
    """Optional component for a CareerData provider backed by a normalized team catalog."""

    def __init__(self, catalog: dict, *, mock: bool = False):
        skills = {skill["id"]: skill for skill in catalog["skills"]}
        self.roles = {}
        self.trees = {}
        for role in catalog["jobs"]:
            self.roles[role["id"]] = CareerRole(
                id=role["id"], name=role["name"], description=role.get("description") or role.get("summary") or role["name"],
                interests=role.get("interests", [])[:20], mock=mock,
            )
            self.trees[role["id"]] = SkillTree.from_catalog(role, skills, mock=mock)

    def get_skill_tree(self, job_id: str) -> SkillTree | None:
        return self.trees.get(job_id)

    def get_skill_node(self, job_id: str, skill_id: str) -> SkillNode | None:
        tree = self.get_skill_tree(job_id)
        return tree.nodes.get(skill_id) if tree else None

    def list_career_roles(self) -> list[CareerRole]:
        return list(self.roles.values())
