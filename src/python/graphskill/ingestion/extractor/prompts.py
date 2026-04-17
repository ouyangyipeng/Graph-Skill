"""
LLM Prompt 模板定义。

定义拓扑关系推演的 Prompt 模板。

Reference: RFC-02 Section 3.3
"""

from __future__ import annotations

import json
from typing import Optional


# 系统提示词
SYSTEM_PROMPT = """
You are a topology analysis expert for LLM Agent skill systems.
Your task is to analyze skill descriptions and infer topological relationships.

**Relationship Types:**
1. **REQUIRES**: Hard dependency. Skill A needs Skill B to function properly.
   Example: "git:commit" REQUIRES "git:config" (need user info configured)

2. **CONFLICTS_WITH**: Logical conflict. Skills cannot be used together.
   Example: "fs:delete_recursive" CONFLICTS_WITH "fs:safe_delete"

3. **ENHANCES**: Soft enhancement. Skill B improves Skill A's success rate.
   Example: "db:query_postgres" ENHANCES "db:optimize_query"

4. **SUBSTITUTES**: Functional alternative. Skills can replace each other.
   Example: "db:query_mysql" SUBSTITUTES "db:query_postgres"

**Guidelines:**
- Only infer relationships with confidence > 0.5
- Respect human-declared hints with high priority
- Consider semantic similarity and functional overlap
- Be conservative with CONFLICTS_WITH (require strong evidence)
- Output must be valid JSON format

**Output Format:**
{
    "inferred_relations": [
        {
            "target_uid": "skill:uid",
            "edge_type": "REQUIRES|CONFLICTS_WITH|ENHANCES|SUBSTITUTES",
            "confidence": 0.0-1.0,
            "reasoning": "Brief explanation"
        }
    ],
    "overall_confidence": 0.0-1.0,
    "reasoning": "Overall analysis summary"
}
"""


def build_inference_prompt(
    source_skill: dict,
    candidate_skills: list[dict],
    declared_hints: Optional[dict] = None,
) -> str:
    """
    构建单个技能的拓扑推演 Prompt。
    
    Args:
        source_skill: 源技能信息
        candidate_skills: 候选技能列表
        declared_hints: 人工声明的拓扑提示
        
    Returns:
        str: 构建的 Prompt
    """
    candidates_str = json.dumps(
        [
            {
                "uid": s.get("uid", s.get("skill_id", "unknown")),
                "intent_description": s.get("intent_description", ""),
                "tags": s.get("tags", []),
                "permissions": s.get("permissions", []),
            }
            for s in candidate_skills
        ],
        indent=2,
        ensure_ascii=False,
    )
    
    hints_str = ""
    if declared_hints:
        hints_str = f"""
**Human-declared topology hints (HIGH CONFIDENCE - MUST RESPECT):**
{json.dumps(declared_hints, indent=2, ensure_ascii=False)}

These hints should be respected with high priority. Do not contradict them.
"""
    
    source_uid = source_skill.get("uid", source_skill.get("skill_id", "unknown"))
    
    output_format = '''
{
    "inferred_relations": [
        {
            "target_uid": "skill:uid",
            "edge_type": "REQUIRES|CONFLICTS_WITH|ENHANCES|SUBSTITUTES",
            "confidence": 0.0-1.0,
            "reasoning": "Brief explanation"
        }
    ],
    "overall_confidence": 0.0-1.0,
    "reasoning": "Overall analysis summary"
}
'''
    return f"""
Analyze the following skill and infer its topological relationships with other skills.

**Source Skill:**
- UID: {source_uid}
- Intent: {source_skill.get('intent_description', '')}
- Permissions: {json.dumps(source_skill.get('permissions', []), indent=2, ensure_ascii=False)}
- Tags: {json.dumps(source_skill.get('tags', []), indent=2, ensure_ascii=False)}

**Candidate Skills:**
{candidates_str}

{hints_str}

**Task:**
For each candidate skill, determine if there is a topological relationship with the source skill.
Consider:
1. **REQUIRES**: Does the source skill need the candidate skill as a prerequisite?
2. **CONFLICTS_WITH**: Can the source and candidate skills cause logical conflicts if used together?
3. **ENHANCES**: Does the candidate skill improve the success rate of the source skill?
4. **SUBSTITUTES**: Can the candidate skill replace the source skill in functionality?

**Important Rules:**
- Only output relationships with confidence > 0.5
- Human-declared hints MUST be included in output with confidence = 1.0
- Do not infer relationships that contradict human-declared hints
- Be conservative with CONFLICTS_WITH (require strong evidence)

**Output Format (JSON):**
Provide your analysis in the following JSON format:
{output_format}
"""


def build_batch_inference_prompt(
    skills: list[dict],
    declared_hints_map: Optional[dict] = None,
) -> str:
    """
    构建批量拓扑推演 Prompt。
    
    Args:
        skills: 技能列表
        declared_hints_map: 技能 UID 到拓扑提示的映射
        
    Returns:
        str: 构建的 Prompt
    """
    skills_str = json.dumps(
        [
            {
                "uid": s.get("uid", s.get("skill_id", "unknown")),
                "intent_description": s.get("intent_description", ""),
                "tags": s.get("tags", []),
                "permissions": s.get("permissions", []),
                "topology_hints": declared_hints_map.get(
                    s.get("uid", s.get("skill_id", "unknown")), {}
                ) if declared_hints_map else {},
            }
            for s in skills
        ],
        indent=2,
        ensure_ascii=False,
    )
    
    output_format = '''
{
    "topology_map": {
        "skill:uid1": {
            "relations": [
                {
                    "target_uid": "skill:uid2",
                    "edge_type": "REQUIRES|CONFLICTS_WITH|ENHANCES|SUBSTITUTES",
                    "confidence": 0.0-1.0,
                    "reasoning": "Explanation"
                }
            ]
        },
        "skill:uid2": {
            "relations": [...]
        }
    },
    "overall_confidence": 0.0-1.0,
    "analysis_summary": "Brief summary of findings"
}
'''
    return f"""
Analyze the following skills and infer topological relationships between them.

**Skills to Analyze:**
{skills_str}

**Task:**
For each skill, identify its relationships with other skills in the list.
Consider all four relationship types: REQUIRES, CONFLICTS_WITH, ENHANCES, SUBSTITUTES.

**Important Rules:**
- Only output relationships with confidence > 0.5
- Human-declared topology_hints MUST be included with confidence = 1.0
- Do not contradict declared hints
- Be conservative with CONFLICTS_WITH

**Output Format (JSON):**
{output_format}
"""


def build_conflict_resolution_prompt(
    source_uid: str,
    declared_relation: dict,
    inferred_relation: dict,
) -> str:
    """
    构建冲突解决 Prompt。
    
    Args:
        source_uid: 源技能 UID
        declared_relation: 人工声明的关系
        inferred_relation: LLM 推断的关系
        
    Returns:
        str: 构建的 Prompt
    """
    output_format = '''
{
    "resolution": "keep_declared|keep_inferred|merge|reject_both",
    "final_relation": {
        "target_uid": "...",
        "edge_type": "...",
        "confidence": 0.0-1.0,
        "reasoning": "Resolution explanation"
    },
    "resolution_reason": "Why this resolution was chosen"
}
'''
    return f"""
Resolve the conflict between human-declared and LLM-inferred topology relationships.

**Source Skill UID:** {source_uid}

**Human-declared Relation:**
{json.dumps(declared_relation, indent=2, ensure_ascii=False)}

**LLM-inferred Relation:**
{json.dumps(inferred_relation, indent=2, ensure_ascii=False)}

**Task:**
Analyze the conflict and provide a resolution recommendation.

**Output Format (JSON):**
{output_format}
"""


# 关系类型描述
RELATION_TYPE_DESCRIPTIONS = {
    "REQUIRES": """
REQUIRES represents a hard dependency relationship.
- Skill A REQUIRES Skill B means A cannot function properly without B.
- This creates a directed edge in the dependency graph.
- The dependency graph MUST be a DAG (no cycles allowed).
- Example: "git:push" REQUIRES "git:config" (needs user identity)
""",
    "CONFLICTS_WITH": """
CONFLICTS_WITH represents a logical conflict relationship.
- Skill A CONFLICTS_WITH Skill B means they cannot be used together.
- This is an undirected edge (bidirectional conflict).
- Conflicts are used in MWIS algorithm for skill pruning.
- Example: "fs:force_delete" CONFLICTS_WITH "fs:safe_delete"
""",
    "ENHANCES": """
ENHANCES represents a soft enhancement relationship.
- Skill A ENHANCES Skill B means A improves B's success rate or quality.
- This is a directed edge with weight representing enhancement degree.
- Enhancement edges contribute to scoring in routing.
- Example: "db:optimize_query" ENHANCES "db:query_postgres"
""",
    "SUBSTITUTES": """
SUBSTITUTES represents a functional alternative relationship.
- Skill A SUBSTITUTES Skill B means A can replace B in functionality.
- This is an undirected edge (bidirectional substitution).
- Substitution is used for fallback when primary skill fails.
- Example: "db:query_mysql" SUBSTITUTES "db:query_postgres"
""",
}


def get_relation_type_description(edge_type: str) -> str:
    """
    获取关系类型描述。
    
    Args:
        edge_type: 关系类型
        
    Returns:
        str: 描述文本
    """
    return RELATION_TYPE_DESCRIPTIONS.get(edge_type, f"Unknown relation type: {edge_type}")