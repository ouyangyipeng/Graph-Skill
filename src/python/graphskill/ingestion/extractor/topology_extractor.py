"""
拓扑关系抽取器。

基于 LLM 推演技能节点之间的四类拓扑关系：
- REQUIRES (强依赖)
- CONFLICTS_WITH (互斥)
- ENHANCES (增强)
- SUBSTITUTES (替代)

Reference: RFC-02 Section 3.3
"""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from graphskill.core.models import EdgeType
from graphskill.core.exceptions import IngestionError
from graphskill.ingestion.extractor.prompts import (
    SYSTEM_PROMPT,
    build_inference_prompt,
    build_batch_inference_prompt,
)


@dataclass
class InferredRelation:
    """推断的关系。"""
    
    target_uid: str
    edge_type: EdgeType
    confidence: float
    reasoning: str
    source_uid: Optional[str] = None
    is_declared: bool = False  # 是否来自人工声明
    
    def to_dict(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "target_uid": self.target_uid,
            "edge_type": self.edge_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "is_declared": self.is_declared,
        }
    
    def to_edge_dict(self) -> dict:
        """转换为边数据格式。"""
        return {
            "source_uid": self.source_uid,
            "target_uid": self.target_uid,
            "edge_type": self.edge_type.value,
            "weight": self.confidence,
        }


@dataclass
class TopologyInferenceResult:
    """拓扑推演结果。"""
    
    source_uid: str
    inferred_relations: list[InferredRelation] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: Optional[str] = None
    parse_errors: list[str] = field(default_factory=list)
    
    @property
    def relation_count(self) -> int:
        """关系数量。"""
        return len(self.inferred_relations)
    
    @property
    def has_relations(self) -> bool:
        """是否有关系。"""
        return len(self.inferred_relations) > 0
    
    def get_relations_by_type(self, edge_type: EdgeType) -> list[InferredRelation]:
        """按类型获取关系。"""
        return [r for r in self.inferred_relations if r.edge_type == edge_type]
    
    def to_dict(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "relation_count": self.relation_count,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "inferred_relations": [r.to_dict() for r in self.inferred_relations],
            "parse_errors": self.parse_errors,
        }


class TopologyExtractionError(IngestionError):
    """拓扑抽取错误。
    
    Error Code: GS-2020
    """
    
    def __init__(
        self,
        message: str,
        source_uid: Optional[str] = None,
        raw_response: Optional[str] = None,
    ):
        details = {}
        if source_uid:
            details["source_uid"] = source_uid
        if raw_response:
            details["raw_response"] = raw_response[:500]  # 截断
        super().__init__(message, details=details)
        self._source_uid = source_uid
        self._raw_response = raw_response
    
    @property
    def source_uid(self) -> Optional[str]:
        return self._source_uid
    
    @property
    def raw_response(self) -> Optional[str]:
        return self._raw_response
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self._source_uid:
            result["source_uid"] = self._source_uid
        if self._raw_response:
            result["raw_response"] = self._raw_response[:500]  # 截断
        return result


class TopologyExtractor:
    """
    拓扑关系抽取器。
    
    使用 LLM 分析技能描述，推断与其他技能的拓扑关系。
    
    Features:
        - LLM-based 关系推演
        - 支持人工声明优先
        - 批量处理支持
        - JSON 输出解析
    
    Example:
        >>> extractor = TopologyExtractor(openai_client)
        >>> result = await extractor.extract(skill_node, all_skills)
        >>> for relation in result.inferred_relations:
        ...     print(f"{relation.edge_type}: {relation.target_uid}")
    """
    
    # 默认模型配置
    DEFAULT_MODEL = "gpt-4-turbo-preview"
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 2000
    
    # 置信度阈值 (RFC-02 Section 3.3: MUST be >= 0.85)
    MIN_CONFIDENCE_THRESHOLD = 0.85
    DECLARED_HINT_CONFIDENCE = 1.0
    
    def __init__(
        self,
        openai_client: Optional[Any] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    ):
        """
        初始化抽取器。
        
        Args:
            openai_client: OpenAI 客户端实例
            model: 使用的模型名称
            temperature: 生成温度
            max_tokens: 最大输出 token 数
            min_confidence: 最小置信度阈值
        """
        self.client = openai_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_confidence = min_confidence
    
    async def extract(
        self,
        source_skill: dict,
        candidate_skills: list[dict],
        declared_hints: Optional[dict] = None,
    ) -> TopologyInferenceResult:
        """
        抽取拓扑关系。
        
        Args:
            source_skill: 源技能信息
            candidate_skills: 候选技能列表
            declared_hints: 人工声明的拓扑提示
            
        Returns:
            TopologyInferenceResult: 推演结果
        """
        source_uid = source_skill.get("uid", source_skill.get("skill_id", "unknown"))
        
        # 如果没有客户端，返回人工声明的关系
        if self.client is None:
            return self._build_declared_only_result(source_uid, declared_hints)
        
        # 构建 Prompt
        prompt = build_inference_prompt(source_skill, candidate_skills, declared_hints)
        
        try:
            # 调用 LLM
            response = await self._call_llm(prompt)
            
            # 解析响应
            result = self._parse_response(source_uid, response, declared_hints)
            
            return result
        
        except Exception as e:
            # LLM 调用失败，返回人工声明的关系
            result = self._build_declared_only_result(source_uid, declared_hints)
            result.parse_errors.append(f"LLM call failed: {e}")
            return result
    
    async def extract_batch(
        self,
        skills: list[dict],
        declared_hints_map: Optional[dict] = None,
    ) -> dict[str, TopologyInferenceResult]:
        """
        批量抽取拓扑关系。
        
        Args:
            skills: 技能列表
            declared_hints_map: 技能 UID 到拓扑提示的映射
            
        Returns:
            dict: UID 到 TopologyInferenceResult 的映射
        """
        if self.client is None:
            # 无客户端，只处理人工声明
            return {
                s.get("uid", s.get("skill_id", "unknown")):
                self._build_declared_only_result(
                    s.get("uid", s.get("skill_id", "unknown")),
                    declared_hints_map.get(s.get("uid", s.get("skill_id", "unknown")))
                )
                for s in skills
            }
        
        # 构建批量 Prompt
        prompt = build_batch_inference_prompt(skills, declared_hints_map)
        
        try:
            response = await self._call_llm(prompt)
            return self._parse_batch_response(response, skills, declared_hints_map)
        except Exception as e:
            # 失败时返回人工声明
            results: dict[str, TopologyInferenceResult] = {}
            for skill in skills:
                uid = skill.get("uid", skill.get("skill_id", "unknown"))
                result = self._build_declared_only_result(
                    uid, declared_hints_map.get(uid)
                )
                result.parse_errors.append(f"Batch LLM call failed: {e}")
                results[uid] = result
            return results
    
    async def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM。
        
        Args:
            prompt: 输入 Prompt
            
        Returns:
            str: LLM 响应
        """
        if self.client is None:
            raise TopologyExtractionError("No OpenAI client configured")
        
        try:
            # 使用 OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            return response.choices[0].message.content or ""
        
        except Exception as e:
            raise TopologyExtractionError(
                f"LLM API call failed: {e}",
                raw_response=str(e),
            )
    
    def _parse_response(
        self,
        source_uid: str,
        response: str,
        declared_hints: Optional[dict] = None,
    ) -> TopologyInferenceResult:
        """
        解析 LLM 响应。
        
        Args:
            source_uid: 源技能 UID
            response: LLM 响应字符串
            declared_hints: 人工声明的拓扑提示
            
        Returns:
            TopologyInferenceResult: 解析结果
        """
        relations: list[InferredRelation] = []
        parse_errors: list[str] = []
        confidence = 0.0
        reasoning = ""
        
        try:
            data = json.loads(response)
            
            # 解析推断关系
            inferred_list = data.get("inferred_relations", [])
            for item in inferred_list:
                try:
                    edge_type_str = item.get("edge_type", "")
                    edge_type = EdgeType(edge_type_str.upper())  # EdgeType 值是大写的
                    item_confidence = float(item.get("confidence", 0.0))
                    
                    # 过滤低置信度
                    if item_confidence < self.min_confidence:
                        continue
                    
                    relations.append(InferredRelation(
                        source_uid=source_uid,
                        target_uid=item.get("target_uid", ""),
                        edge_type=edge_type,
                        confidence=item_confidence,
                        reasoning=item.get("reasoning", ""),
                        is_declared=False,
                    ))
                except (ValueError, KeyError) as e:
                    parse_errors.append(f"Failed to parse relation: {item}, error: {e}")
            
            confidence = float(data.get("overall_confidence", 0.0))
            reasoning = data.get("reasoning", "")
        
        except json.JSONDecodeError as e:
            parse_errors.append(f"JSON decode error: {e}")
        
        # 添加人工声明的关系
        if declared_hints:
            declared_relations = self._parse_declared_hints(source_uid, declared_hints)
            relations.extend(declared_relations)
        
        return TopologyInferenceResult(
            source_uid=source_uid,
            inferred_relations=relations,
            confidence=confidence,
            reasoning=reasoning,
            raw_response=response,
            parse_errors=parse_errors,
        )
    
    def _parse_batch_response(
        self,
        response: str,
        skills: list[dict],
        declared_hints_map: Optional[dict] = None,
    ) -> dict[str, TopologyInferenceResult]:
        """
        解析批量响应。
        
        Args:
            response: LLM 响应
            skills: 技能列表
            declared_hints_map: 人工声明映射
            
        Returns:
            dict: 结果映射
        """
        results: dict[str, TopologyInferenceResult] = {}
        
        try:
            data = json.loads(response)
            topology_map = data.get("topology_map", {})
            
            for skill in skills:
                uid = skill.get("uid", skill.get("skill_id", "unknown"))
                skill_data = topology_map.get(uid, {})
                
                relations: list[InferredRelation] = []
                parse_errors: list[str] = []
                
                # 解析推断关系
                for item in skill_data.get("relations", []):
                    try:
                        edge_type_str = item.get("edge_type", "")
                        edge_type = EdgeType(edge_type_str.upper())  # EdgeType 值是大写的
                        item_confidence = float(item.get("confidence", 0.0))
                        
                        if item_confidence < self.min_confidence:
                            continue
                        
                        relations.append(InferredRelation(
                            source_uid=uid,
                            target_uid=item.get("target_uid", ""),
                            edge_type=edge_type,
                            confidence=item_confidence,
                            reasoning=item.get("reasoning", ""),
                            is_declared=False,
                        ))
                    except (ValueError, KeyError) as e:
                        parse_errors.append(f"Parse error: {e}")
                
                # 添加人工声明
                if declared_hints_map and uid in declared_hints_map:
                    declared = self._parse_declared_hints(uid, declared_hints_map[uid])
                    relations.extend(declared)
                
                results[uid] = TopologyInferenceResult(
                    source_uid=uid,
                    inferred_relations=relations,
                    confidence=float(skill_data.get("confidence", 0.0)),
                    reasoning=skill_data.get("reasoning", ""),
                    parse_errors=parse_errors,
                )
        
        except json.JSONDecodeError as e:
            # 解析失败，返回人工声明
            for skill in skills:
                uid = skill.get("uid", skill.get("skill_id", "unknown"))
                result = self._build_declared_only_result(
                    uid, declared_hints_map.get(uid) if declared_hints_map else None
                )
                result.parse_errors.append(f"JSON decode error: {e}")
                results[uid] = result
        
        return results
    
    def _parse_declared_hints(
        self,
        source_uid: str,
        declared_hints: dict,
    ) -> list[InferredRelation]:
        """
        解析人工声明的拓扑提示。
        
        Args:
            source_uid: 源技能 UID
            declared_hints: 拓扑提示字典
            
        Returns:
            list: 声明的关系列表
        """
        relations: list[InferredRelation] = []
        
        # REQUIRES
        requires_list = declared_hints.get("requires", [])
        for target_uid in requires_list:
            relations.append(InferredRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.REQUIRES,
                confidence=self.DECLARED_HINT_CONFIDENCE,
                reasoning="Human-declared dependency",
                is_declared=True,
            ))
        
        # CONFLICTS_WITH
        conflicts_list = declared_hints.get("conflicts_with", [])
        for target_uid in conflicts_list:
            relations.append(InferredRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.CONFLICTS_WITH,
                confidence=self.DECLARED_HINT_CONFIDENCE,
                reasoning="Human-declared conflict",
                is_declared=True,
            ))
        
        # ENHANCES
        enhances_list = declared_hints.get("enhances", [])
        for target_uid in enhances_list:
            relations.append(InferredRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.ENHANCES,
                confidence=self.DECLARED_HINT_CONFIDENCE,
                reasoning="Human-declared enhancement",
                is_declared=True,
            ))
        
        # SUBSTITUTES
        substitutes_list = declared_hints.get("substitutes", [])
        for target_uid in substitutes_list:
            relations.append(InferredRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.SUBSTITUTES,
                confidence=self.DECLARED_HINT_CONFIDENCE,
                reasoning="Human-declared substitution",
                is_declared=True,
            ))
        
        return relations
    
    def _build_declared_only_result(
        self,
        source_uid: str,
        declared_hints: Optional[dict],
    ) -> TopologyInferenceResult:
        """
        构建仅包含人工声明的结果。
        
        Args:
            source_uid: 源技能 UID
            declared_hints: 拓扑提示
            
        Returns:
            TopologyInferenceResult: 结果
        """
        relations: list[InferredRelation] = []
        
        if declared_hints:
            relations = self._parse_declared_hints(source_uid, declared_hints)
        
        return TopologyInferenceResult(
            source_uid=source_uid,
            inferred_relations=relations,
            confidence=1.0 if relations else 0.0,
            reasoning="Only human-declared relations (no LLM inference)",
        )
    
    def extract_sync(
        self,
        source_skill: dict,
        candidate_skills: list[dict],
        declared_hints: Optional[dict] = None,
    ) -> TopologyInferenceResult:
        """
        同步版本的抽取方法。
        
        Args:
            source_skill: 源技能信息
            candidate_skills: 候选技能列表
            declared_hints: 人工声明的拓扑提示
            
        Returns:
            TopologyInferenceResult: 推演结果
        """
        return asyncio.run(self.extract(source_skill, candidate_skills, declared_hints))
    
    def set_client(self, client: Any) -> None:
        """
        设置 OpenAI 客户端。
        
        Args:
            client: OpenAI 客户端实例
        """
        self.client = client
    
    def configure(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        min_confidence: Optional[float] = None,
    ) -> None:
        """
        配置参数。
        
        Args:
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token
            min_confidence: 最小置信度
        """
        if model:
            self.model = model
        if temperature:
            self.temperature = temperature
        if max_tokens:
            self.max_tokens = max_tokens
        if min_confidence:
            self.min_confidence = min_confidence