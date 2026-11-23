"""Select relevant evidence for career and learning consultations."""
import re

from .contracts import Fact, Profile
from .memory import identity
from .privacy import catalog_text, provenance, redact, shareable
from .response_style import korean_list, particle
from .skill_context import mentioned

_CAREER = re.compile(r"직무|커리어|진로|어울리|맞는\s*일|어떤\s*일|목표|역량.*부족")
_CAREER_COMPARISON = re.compile(r"비교|중\s*(?:뭐|무엇|어떤|어느)|더\s*(?:잘\s*)?(?:맞|어울)|차이")
_CAREER_FIT = re.compile(r"맞을|잘\s*맞|적합|어울|추천|부족|보완|중\s*(?:뭐|무엇|어떤|어느).{0,20}(?:좋|나아|유리)")
_ROLE_TITLE = re.compile(r"직무|직업|분석가|엔지니어|개발자|디자이너|기획자|연구원")
_LEARNING = re.compile(r"학습|공부|배워|배우|연습|역량|실습|초급|중급|계획|다음\s*단계")
_SKILL_REFERENCE = re.compile(r"(?:그|이)\s*(?:기술|스킬|노드)|뭐가\s*달라|다음(?:에는)?\s*(?:뭘|무엇|뭐|단계)|선수\s*학습")
_TOPIC_RECALL = re.compile(r"아까|앞서|이전|전에|다시")
_RELATION_QUESTION = re.compile(r"선수\s*(?:학습|기술|노드)|선행|후속|건너뛰|생략|전체.*위치|트리.*관계|다음\s*노드|먼저\s*배우")
_PREREQUISITE = re.compile(r"선수\s*(?:학습|기술|노드)|선행")
_SUCCESSOR = re.compile(r"후속|다음\s*노드")
_GENERAL_ADVICE = re.compile(r"방법|추천|어떻게|비교|연습|실습|예시|계획|난이도|무슨\s*차이|뭐가\s*달라|배워야")
_SEQUENCE_ADVICE = re.compile(r"먼저\s*배우|어떤\s*순서|다음(?:에는)?\s*(?:뭘|무엇|뭐)")
_NODE_COMPARISON = re.compile(r"비교|차이|달라|다르|비슷|공통|vs\.?", re.I)
_TREE_COMPARISON = re.compile(r"스킬\s*트리|트리|직무별\s*(?:기술|역량)")
_CATALOG_CLAIM = re.compile(
    r"(?:선수학습|선수\s*(?:노드|기술)|선행\s*(?:노드|학습)|(?:후속|다음)\s*노드)(?:이|가|은|는|입|로)|"
    r"(?:카탈로그|스킬\s*트리|그래프).*(?:선수|후속|필수|먼저|연결|간선|의존|학습\s*순서|다음)"
)


def asks_about_previous_skill(message: str) -> bool:
    return bool(_SKILL_REFERENCE.search(message))


def names_previous_topic(message: str) -> bool:
    return bool(_TOPIC_RECALL.search(message))


def needs_related_questions(message: str) -> bool:
    return bool(_SEQUENCE_ADVICE.search(message) or asks_about_previous_skill(message))


def compares_careers(message: str) -> bool:
    return bool(_ROLE_TITLE.search(message) and _CAREER_COMPARISON.search(message))


def asks_for_career_fit(message: str) -> bool:
    return bool(_CAREER_FIT.search(message))


def asks_for_catalog_order(message: str) -> bool:
    return bool(_RELATION_QUESTION.search(message) or _SEQUENCE_ADVICE.search(message))


def compares_skill_nodes(message: str) -> bool:
    return bool(_NODE_COMPARISON.search(message))


def compares_skill_trees(message: str) -> bool:
    return bool(_TREE_COMPARISON.search(message) and compares_skill_nodes(message))


def skill_tree_comparison(data, message: str, job_id: str | None, previous_jobs: list[str]) -> dict | None:
    if not compares_skill_trees(message):
        return None
    provide_roles = getattr(data, "list_career_roles", None)
    get_tree = getattr(data, "get_skill_tree", None)
    if not provide_roles or not get_tree:
        return None
    available = {role.id: role for role in provide_roles()}
    named = [role.id for role in available.values() if mentioned(role.name, message) or mentioned(role.id, message)]
    refers_to_selection = re.search(r"(?:이|그|두|다른)\s*(?:직무|스킬\s*트리|트리)|현재|이전", message)
    references = [job_id, *previous_jobs] if not named or refers_to_selection else []
    ids = list(dict.fromkeys(key for key in [*named, *references] if key in available))[:2]
    trees = [(available[key], get_tree(key)) for key in ids]
    compared = [{"jobId": role.id, "jobName": catalog_text(role.name), **tree.overview()}
                for role, tree in trees if tree]
    shared = []
    if len(trees) == 2 and all(tree for _, tree in trees):
        left, right = (tree for _, tree in trees)
        shared = [{"skillId": key, "skillName": catalog_text(left.nodes[key].skill_name)}
                  for key in left.nodes if key in right.nodes][:10]
    return {"trees": compared, "sharedSkills": shared}


def tree_comparison_answer(comparison: dict) -> str:
    trees = comparison["trees"]
    if len(trees) < 2:
        return "어느 두 직무의 스킬트리를 비교할지 직무 이름을 알려 주세요."
    shared = [item["skillName"] for item in comparison["sharedSkills"]]
    mock = all(tree["mock"] for tree in trees)
    source = "두 가상 스킬트리" if mock else "제공된 두 스킬트리"
    lines = [(f"{source}에서 공통으로 배우는 기술은 {korean_list(shared)}{particle(shared[-1], '이에요', '예요')}."
              if shared else f"{source}에서 공통으로 등록된 기술은 확인되지 않아요.")]
    for tree in trees:
        names = {item["skillId"]: item["skillName"] for item in tree["nodes"]}
        # One verified path makes the contrast concrete without listing the whole tree.
        edges = tree["edges"]
        edge = next((item for item in reversed(edges) if names[item["to"]] not in shared), edges[-1] if edges else None)
        label = f"{tree['jobName']} 스킬트리{'(가상)' if tree['mock'] and not mock else ''}"
        if edge:
            earlier, later = names[edge["from"]], names[edge["to"]]
            lines.append(f"{label}에는 {earlier} 다음에 {later}{particle(later, '을', '를')} 배우는 경로가 있어요.")
        else:
            lines.append(f"{label}에서는 이어서 배울 기술의 연결이 확인되지 않아요.")
        if tree["hasCycles"]:
            lines.append("순환에 속한 연결은 학습 순서에서 제외했어요.")
    return " ".join(dict.fromkeys(lines))


def complementary_skill_advice(answer: str) -> str:
    """Leave catalog assertions to the server's rendered relationships."""
    paragraphs = []
    for line in answer.splitlines():
        sentences = re.split(r"(?<=[.!?。])\s+", line)
        paragraphs.append(" ".join(sentence for sentence in sentences if not _CATALOG_CLAIM.search(sentence)))
    return "\n".join(paragraphs).strip()


def skill_evidence(names: list[str], facts: list[Fact], fixture_ids: set[str]) -> list[dict]:
    evidence = []
    for name in names:
        base = identity(re.sub(r"\s+(?:기초|입문)$", "", name))
        matches = [
            fact for fact in facts if fact.kind in ("skill", "certification", "training") and shareable(fact)
            and (identity(fact.value) == identity(name) or fact.kind == "skill" and identity(fact.value) == base)
        ]
        evidence.append({
            "skill": redact(name),
            "records": [
                {"value": redact(fact.value), "provenance": provenance(fact, fact.id in fixture_ids),
                 "progress": fact.progress, "kind": fact.kind} for fact in matches[:3]
            ],
        })
    return evidence


def learning_context(message: str, facts: list[Fact], node, graph, fixture_ids: set[str]) -> dict | None:
    if not node and not _LEARNING.search(message):
        return None
    names = [node.skill_name, *node.prerequisites] if node else []
    if graph:
        names.extend(item["skillName"] for item in graph["nodes"])
    return {
        "skillEvidence": skill_evidence(list(dict.fromkeys(names))[:16], facts, fixture_ids),
        "availableTime": next((redact(fact.value) for fact in facts if fact.kind == "study_time" and shareable(fact)), None),
    }


def catalog_relationship_answer(node, graph: dict, message: str, comparison_skill: dict | None = None
                                ) -> tuple[str, bool] | None:
    """Render the catalog portion server-side and indicate whether advice is also requested."""
    compares_nodes = comparison_skill is not None and compares_skill_nodes(message)
    if not (_RELATION_QUESTION.search(message) or compares_nodes):
        return None
    if not (graph["prerequisitesDeclared"] or graph["cycleNearSelection"] or compares_nodes):
        return None
    names = {item["skillId"]: item["skillName"] for item in graph["nodes"]}
    before = [names[edge["from"]] for edge in graph["edges"] if edge["to"] == node.skill_id]
    after = [names[edge["to"]] for edge in graph["edges"] if edge["from"] == node.skill_id]
    current = catalog_text(node.skill_name)
    source = f"{catalog_text(node.job_name)}의 {'가상 ' if graph['mock'] else ''}스킬트리"
    prerequisite, successor = _PREREQUISITE.search(message), _SUCCESSOR.search(message)
    skip = re.search(r"건너뛰|생략", message)
    named = graph["mentionedSkillIds"][:3]
    overview = not (prerequisite or successor or skip or named or compares_nodes)
    lines = []
    if skip:
        if after:
            lines.append(f"{source}에서 {current} 다음에 배우는 기술은 {korean_list(after)}"
                         f"{particle(after[-1], '이에요', '예요')}. 건너뛴다면 후속 기술을 공부하기 전에 필요한 부분을 따로 익혀 보세요.")
        else:
            lines.append(f"{source}에서 이 기술 다음에 바로 이어지는 기술은 확인되지 않아요.")
    if prerequisite or overview or skip:
        if before:
            lines.append(f"{source}에서는 {current} 전에 {korean_list(before)}부터 배워요.")
        else:
            lines.append(f"{source}에서 {current}에 바로 앞서는 기술은 확인되지 않아요.")
    if (successor and not skip) or overview:
        subject = f"{current} 다음에는" if lines else f"{source}에서 {current} 다음에는"
        lines.append(f"{subject} {korean_list(after)}{particle(after[-1], '을', '를')} 배워요." if after
                     else f"{subject} 바로 이어지는 기술이 확인되지 않아요.")
    for key in named:
        other = names[key]
        if key in graph["nearestAncestorHops"]:
            relation = f"{source}에서는 {other}에서 {current}로 이어지는 학습 경로가 있어요."
        elif key in graph["nearestSuccessorHops"]:
            relation = f"{source}에서는 {current}에서 {other}로 이어지는 학습 경로가 있어요."
        else:
            relation = f"{source}에서는 {korean_list([other, current])}의 학습 순서가 정해져 있는지 확인되지 않아요."
        lines.append(relation)
    if compares_nodes and comparison_skill["jobId"] != node.job_id:
        other = comparison_skill["skillName"]
        other_source = f"{comparison_skill['jobName']}의 {'가상 ' if comparison_skill.get('mock') else ''}스킬트리"
        lines.append(f"{current}{particle(current, '은', '는')} {source}에 있고, "
                     f"{other}{particle(other, '은', '는')} {other_source}에 있어요. "
                     "각 트리의 연결만으로 두 기술의 학습 순서를 정할 수는 없어요.")
    if "위치" in message:
        lines.append(f"{source}에는 기술이 {graph['nodeCount']}개 있어요.")
    if graph["cycleNearSelection"]:
        lines.append("서로를 선행 조건으로 가리키는 연결은 학습 순서에서 제외했어요.")
    if (prerequisite and len(before) < graph["directPrerequisiteCount"]
            or successor and len(after) < graph["directSuccessorCount"]):
        lines.append("가까운 연결 중 현재 볼 수 있는 항목을 안내했어요.")
    if not lines:
        return None
    return " ".join(lines), bool(compares_nodes or _GENERAL_ADVICE.search(message) or _SEQUENCE_ADVICE.search(message))


def career_context(data, profile: Profile, facts: list[Fact], message: str, job_id: str | None) -> list[dict]:
    provide_roles = getattr(data, "list_career_roles", None)
    if not provide_roles:
        return []
    available = provide_roles()
    if not (_CAREER.search(message) or compares_careers(message)
            or any(mentioned(role.name, message) for role in available)):
        return []
    fixture_ids = {fact.id for fact in profile.facts} if profile.mock else set()
    interests = [fact for fact in facts if fact.kind in ("goal", "interest") and shareable(fact)]
    tree_lookup = getattr(data, "get_skill_tree", None)
    candidates = []
    for role in available:
        themes = [role.name, *role.interests]
        direct = mentioned(role.name, message)
        matched = [
            {"value": redact(fact.value), "provenance": provenance(fact, fact.id in fixture_ids)}
            for fact in interests if any(mentioned(theme, fact.value) or mentioned(fact.value, theme) for theme in themes)
        ]
        candidates.append((role, direct, matched))
    candidates.sort(key=lambda entry: (not entry[1], entry[0].id != job_id,
                                       -sum(match["provenance"] != "fixture" for match in entry[2]), entry[0].id))
    result = []
    direct_candidates = [entry for entry in candidates if entry[1]] if compares_careers(message) else []
    for role, _, matched in (direct_candidates or candidates)[:4]:
        tree = tree_lookup(role.id) if tree_lookup else None
        required = list(dict.fromkeys(node.skill_name for node in tree.nodes.values() if node.required)) if tree else []
        result.append({
            "name": catalog_text(role.name), "purpose": catalog_text(role.description)[:360], "mock": role.mock,
            "matchingInterestsAndGoals": matched[:6],
            "catalogRequiredSkills": skill_evidence(required[:10], facts, fixture_ids),
            "requiredSkillsPartial": len(required) > 10 or bool(tree and tree.incomplete),
        })
    return result


def career_fit_note(candidates: list[dict], answer: str) -> tuple[str, str]:
    """Add relevant fit evidence that the model's comparison did not cover."""
    matching = []
    for role in candidates:
        interests = [item["value"] for item in role["matchingInterestsAndGoals"] if item["provenance"] != "fixture"]
        if interests:
            matching.append((role["name"], interests))
    sentences = re.split(r"[.!?。\n]", answer)
    addresses_fit = any(
        re.search(r"판단하기\s*어려|잘\s*맞는지.*(?:어렵|모르)", sentence)
        or ((_ROLE_TITLE.search(sentence) or any(mentioned(role["name"], sentence) for role in candidates))
            and re.search(r"잘\s*맞|더\s*(?:가까|맞|적합)|추천|부터\s*살펴", sentence))
        for sentence in sentences
    )
    opening, paragraphs = "", []
    if len(matching) == 1:
        role, interests = matching[0]
        if not addresses_fit:
            opening = f"말씀하신 {korean_list(interests[:2])}에 대한 관심을 보면, 우선 {role}부터 살펴보는 게 좋아 보여요."
        elif not any(re.search(r"말씀|관심|흥미|목표", sentence) and mentioned(interest, sentence)
                     for sentence in sentences for interest in interests):
            paragraphs.append(f"말씀하신 관심 분야인 {korean_list(interests[:2])}도 비교 기준으로 삼을 수 있어요.")
    elif len(matching) > 1 and not addresses_fit:
        opening = "말씀하신 관심이 두 직무에 걸쳐 있어요. 어느 쪽 일을 더 해 보고 싶은지가 판단 기준이 될 수 있어요."
    elif not matching and not addresses_fit:
        opening = "지금까지 말씀해 주신 내용만으로는 어느 쪽이 더 잘 맞는지 판단하기 어려워요."

    for role in candidates:
        verified, reported, registered, developing, unknown = [], [], [], [], []
        for item in role["catalogRequiredSkills"]:
            name = item["skill"]
            records = [record for record in item["records"]
                       if record["provenance"] != "fixture" and record["kind"] == "skill"]
            related = [sentence for sentence in sentences if mentioned(name, sentence)]
            for group, applies, covered in (
                (verified, any(record["provenance"] == "verified" and record["progress"] not in ("preparing", "not_held")
                               for record in records), r"공식|검증"),
                (developing, any(record["provenance"] == "user_statement" and record["progress"] in
                                 ("preparing", "beginner", "not_held") for record in records), r"기초|준비\s*중|경험.*없"),
                (reported, any(record["provenance"] == "user_statement" and record["progress"] not in
                               ("preparing", "beginner", "not_held") for record in records), r"말씀|말해"),
                (registered, any(record["provenance"] == "registered" for record in records), r"프로필|등록"),
                (unknown, not records, r"확인|점검|알려진"),
            ):
                if applies and not any(re.search(covered, sentence) for sentence in related):
                    group.append(name)
        details = [sentence.format(skills=korean_list(names[:2])) for names, sentence in (
            (verified, "공식 기록에서 {skills} 역량을 확인할 수 있어요."),
            (reported, "말씀하신 {skills} 경험을 준비 방향에 참고할 수 있어요."),
            (registered, "{skills} 역량은 프로필에 기록돼 있어요."),
            (developing, "말씀하신 수준을 바탕으로 {skills}부터 연습해 볼 수 있어요."),
            (unknown, "{skills} 역량은 어느 정도 갖췄는지 확인되면 준비 방향을 더 구체화할 수 있어요."),
        ) if names]
        if details:
            title = role["name"]
            paragraphs.append(f"{title}{particle(title, '을', '를')} 준비한다면, {' '.join(details)}")
    return opening, "\n\n".join(paragraphs)
