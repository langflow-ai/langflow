# Path: src/backend/base/langflow/services/specification/service.py

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import yaml
from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from langflow.services.database.models.specification.model import (
    AgentSpecification,
    AgentSpecificationCreate,
    SpecificationComponent,
    SpecificationUsage,
)
from langflow.services.specification.models import (
    AgentRequirements,
    ComponentPattern,
    ConversionResult,
    ConversionStrategy,
    EnhancedAgentSpec,
    ReusableComponent,
    ResearchResults,
    SimilarityMatch,
    SpecificationAnalytics,
    SpecificationQuery,
    SpecificationSummary,
    WorkflowPattern,
)


class SpecificationStorageService:
    """Service for managing agent specifications with search capabilities"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_specification(
        self,
        spec: EnhancedAgentSpec,
        user_id: Optional[UUID] = None,
        flow_id: Optional[UUID] = None
    ) -> UUID:
        """Store specification with computed metadata"""

        # Convert enhanced spec to database model
        spec_yaml = spec.to_yaml()
        spec_json = spec.model_dump(exclude_none=True)

        # Calculate metadata
        reusability_score = self._calculate_reusability_score(spec)
        complexity_score = self._calculate_complexity_score(spec)

        # Create database record
        db_spec = AgentSpecification(
            name=spec.name,
            version=spec.version,
            spec_yaml=spec_yaml,
            spec_json=spec_json,
            domain=spec.domain,
            subdomain=spec.subdomain,
            owner_email=spec.owner,
            fully_qualified_name=spec.fully_qualified_name or f"{spec.domain}.{spec.name}",
            kind=spec.kind,
            target_user=spec.target_user,
            value_generation=spec.value_generation,
            interaction_mode=spec.interaction_mode,
            run_mode=spec.run_mode,
            agency_level=spec.agency_level,
            goal=spec.goal,
            description=spec.description,
            tags=spec.tags,
            components={"components": [comp.model_dump() for comp in spec.components]},
            variables={"variables": [var.model_dump() for var in spec.variables] if spec.variables else None},
            reusability_score=reusability_score,
            complexity_score=complexity_score,
            user_id=user_id,
            flow_id=flow_id,
        )

        self.session.add(db_spec)
        await self.session.flush()

        # Store component details
        for component in spec.components:
            component_record = SpecificationComponent(
                spec_id=db_spec.id,
                component_id=component.id,
                component_type=component.type,
                component_config=component.config,
                provides_config=component.provides,
                reusable=self._is_component_reusable(component),
                usage_count=0
            )
            self.session.add(component_record)

        await self.session.commit()
        return db_spec.id

    async def search_specifications(self, query: SpecificationQuery) -> List[SpecificationSummary]:
        """Advanced search with filters, scoring, and ranking"""

        from sqlalchemy import select

        # Build base query
        stmt = select(AgentSpecification)

        # Apply filters
        conditions = []

        if query.text_query:
            # Full-text search on name, description, goal
            text_condition = or_(
                AgentSpecification.name.ilike(f"%{query.text_query}%"),
                AgentSpecification.description.ilike(f"%{query.text_query}%"),
                AgentSpecification.goal.ilike(f"%{query.text_query}%"),
            )
            conditions.append(text_condition)

        if query.domains:
            conditions.append(AgentSpecification.domain.in_(query.domains))

        if query.kinds:
            conditions.append(AgentSpecification.kind.in_(query.kinds))

        if query.target_users:
            conditions.append(AgentSpecification.target_user.in_(query.target_users))

        if query.value_generations:
            conditions.append(AgentSpecification.value_generation.in_(query.value_generations))

        if query.interaction_modes:
            conditions.append(AgentSpecification.interaction_mode.in_(query.interaction_modes))

        if query.run_modes:
            conditions.append(AgentSpecification.run_mode.in_(query.run_modes))

        if query.tags:
            # JSON array contains any of the tags
            tag_conditions = []
            for tag in query.tags:
                tag_conditions.append(
                    AgentSpecification.tags.op('?')(tag)
                )
            conditions.append(or_(*tag_conditions))

        if query.min_reusability_score:
            conditions.append(AgentSpecification.reusability_score >= query.min_reusability_score)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Apply sorting
        if query.sort_by == "name":
            order_col = AgentSpecification.name
        elif query.sort_by == "created_at":
            order_col = AgentSpecification.created_at
        elif query.sort_by == "reusability_score":
            order_col = AgentSpecification.reusability_score
        else:  # relevance or default
            order_col = AgentSpecification.updated_at

        if query.sort_order == "asc":
            stmt = stmt.order_by(order_col.asc())
        else:
            stmt = stmt.order_by(order_col.desc())

        # Apply pagination
        stmt = stmt.offset(query.offset).limit(query.limit)

        # Execute query
        result = await self.session.execute(stmt)
        specifications = result.scalars().all()

        # Convert to summary objects
        summaries = []
        for spec in specifications:
            # Get component count
            component_count = len(spec.spec_json.get("components", [])) if spec.spec_json else 0

            # Get usage count (simplified for now)
            usage_stmt = select(func.count(SpecificationUsage.id)).where(
                SpecificationUsage.spec_id == spec.id
            )
            usage_result = await self.session.execute(usage_stmt)
            usage_count = usage_result.scalar() or 0

            summary = SpecificationSummary(
                id=spec.id,
                name=spec.name,
                version=spec.version,
                description=spec.description,
                domain=spec.domain,
                subdomain=spec.subdomain,
                owner=spec.owner_email,
                goal=spec.goal,
                kind=spec.kind.value,
                target_user=spec.target_user.value,
                tags=spec.tags or [],
                reusability_score=spec.reusability_score,
                complexity_score=spec.complexity_score,
                created_at=spec.created_at,
                updated_at=spec.updated_at,
                component_count=component_count,
                usage_count=usage_count,
            )
            summaries.append(summary)

        return summaries

    async def find_similar_specifications(
        self,
        spec: EnhancedAgentSpec,
        limit: int = 10
    ) -> List[SimilarityMatch]:
        """Find specifications similar to given spec for reuse recommendations"""

        from sqlalchemy import select

        # Build similarity query
        stmt = select(AgentSpecification).where(
            and_(
                AgentSpecification.domain == spec.domain,
                AgentSpecification.status != "deprecated"
            )
        ).limit(limit * 2)  # Get more to filter and rank

        result = await self.session.execute(stmt)
        candidates = result.scalars().all()

        # Calculate similarity scores
        matches = []
        for candidate in candidates:
            similarity = self._calculate_similarity(spec, candidate)
            if similarity.similarity_score > 0.3:  # Minimum similarity threshold
                matches.append(similarity)

        # Sort by similarity score and return top matches
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:limit]

    async def extract_reusable_components(self, spec_ids: List[UUID]) -> List[ReusableComponent]:
        """Analyze specifications to identify reusable components"""

        from sqlalchemy import select

        # Get component usage across specifications
        stmt = select(SpecificationComponent).where(
            SpecificationComponent.spec_id.in_(spec_ids)
        )

        result = await self.session.execute(stmt)
        components = result.scalars().all()

        # Group by component type and analyze reusability
        component_groups = {}
        for comp in components:
            comp_type = comp.component_type
            if comp_type not in component_groups:
                component_groups[comp_type] = []
            component_groups[comp_type].append(comp)

        reusable_components = []
        for comp_type, comp_list in component_groups.items():
            if len(comp_list) >= 3:  # Used in at least 3 specifications
                # Calculate reusability score
                reusability_score = min(len(comp_list) / 10.0, 1.0)  # Max score at 10+ uses

                # Extract common configuration patterns
                config_template = self._extract_config_template(comp_list)
                provides_template = self._extract_provides_template(comp_list)

                reusable_comp = ReusableComponent(
                    component_id=f"reusable_{comp_type}",
                    component_type=comp_type,
                    config_template=config_template,
                    provides_template=provides_template,
                    reusability_score=reusability_score,
                    usage_count=len(comp_list),
                    source_specs=[str(comp.spec_id) for comp in comp_list]
                )
                reusable_components.append(reusable_comp)

        return reusable_components

    async def get_specification_analytics(self, spec_id: UUID) -> SpecificationAnalytics:
        """Get usage analytics and reusability metrics"""

        from sqlalchemy import select

        # Get specification
        spec_stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        spec_result = await self.session.execute(spec_stmt)
        spec = spec_result.scalar_one_or_none()

        if not spec:
            raise ValueError(f"Specification {spec_id} not found")

        # Get usage statistics
        usage_stmt = select(SpecificationUsage).where(SpecificationUsage.spec_id == spec_id)
        usage_result = await self.session.execute(usage_stmt)
        usage_records = usage_result.scalars().all()

        # Calculate analytics
        total_views = len([u for u in usage_records if u.usage_type == "view"])
        total_copies = len([u for u in usage_records if u.usage_type == "copy"])
        total_reuses = len([u for u in usage_records if u.usage_type == "reuse"])

        # Get popular components
        components = spec.spec_json.get("components", []) if spec.spec_json else []
        popular_components = [comp.get("type", "unknown") for comp in components[:5]]

        # Find similar specifications
        enhanced_spec = EnhancedAgentSpec(**spec.spec_json)
        similar_matches = await self.find_similar_specifications(enhanced_spec, limit=5)
        similar_specs = [match.specification.id for match in similar_matches]

        return SpecificationAnalytics(
            spec_id=spec_id,
            total_views=total_views,
            total_copies=total_copies,
            total_reuses=total_reuses,
            reusability_score=spec.reusability_score or 0.0,
            complexity_score=spec.complexity_score or 0.0,
            popular_components=popular_components,
            usage_trends={},  # TODO: Implement usage trends
            similar_specs=similar_specs
        )

    async def record_usage(
        self,
        spec_id: UUID,
        usage_type: str,
        user_id: Optional[UUID] = None,
        context_info: Optional[Dict] = None
    ) -> None:
        """Record specification usage for analytics"""

        usage_record = SpecificationUsage(
            spec_id=spec_id,
            user_id=user_id,
            usage_type=usage_type,
            context_info=context_info,
        )

        self.session.add(usage_record)
        await self.session.commit()

    def _calculate_reusability_score(self, spec: EnhancedAgentSpec) -> float:
        """Calculate reusability score based on specification characteristics"""
        score = 0.5  # Base score

        # Boost for well-defined components
        if spec.components:
            score += 0.1 * min(len(spec.components) / 5, 1)

        # Boost for variables (makes it configurable)
        if spec.variables:
            score += 0.1 * min(len(spec.variables) / 3, 1)

        # Boost for clear documentation
        if spec.description and len(spec.description) > 50:
            score += 0.1

        # Boost for sample input/output
        if spec.sample_input and spec.expected_output:
            score += 0.1

        # Boost for reusability configuration
        if spec.reusability:
            score += 0.2

        return min(score, 1.0)

    def _calculate_complexity_score(self, spec: EnhancedAgentSpec) -> float:
        """Calculate complexity score based on specification structure"""
        complexity = 0.0

        # Component complexity
        complexity += len(spec.components) * 0.1

        # Variable complexity
        if spec.variables:
            complexity += len(spec.variables) * 0.05

        # Dependency complexity
        if spec.dependencies:
            complexity += len(spec.dependencies) * 0.15

        # Multi-agent complexity
        if spec.kind != "Single Agent":
            complexity += 0.3

        return min(complexity, 1.0)

    def _calculate_similarity(self, spec: EnhancedAgentSpec, candidate: AgentSpecification) -> SimilarityMatch:
        """Calculate similarity between specifications"""
        similarity_score = 0.0
        match_reasons = []
        shared_components = []
        shared_tags = []

        try:
            candidate_spec = EnhancedAgentSpec(**candidate.spec_json)
        except Exception:
            # Fallback for invalid spec data
            candidate_spec = None

        if candidate_spec:
            # Domain similarity
            if spec.domain == candidate_spec.domain:
                similarity_score += 0.2
                match_reasons.append("Same domain")

            # Kind similarity
            if spec.kind == candidate_spec.kind:
                similarity_score += 0.1
                match_reasons.append("Same agent kind")

            # Component type similarity
            spec_component_types = {comp.type for comp in spec.components}
            candidate_component_types = {comp.type for comp in candidate_spec.components}
            common_components = spec_component_types & candidate_component_types

            if common_components:
                similarity_score += 0.3 * len(common_components) / max(len(spec_component_types), 1)
                shared_components = list(common_components)
                match_reasons.append(f"Shared {len(common_components)} component types")

            # Tag similarity
            spec_tags = set(spec.tags)
            candidate_tags = set(candidate.tags or [])
            common_tags = spec_tags & candidate_tags

            if common_tags:
                similarity_score += 0.2 * len(common_tags) / max(len(spec_tags), 1)
                shared_tags = list(common_tags)
                match_reasons.append(f"Shared {len(common_tags)} tags")

            # Use case similarity (simplified)
            if spec.value_generation == candidate_spec.value_generation:
                similarity_score += 0.1
                match_reasons.append("Same value generation type")

        # Create summary
        candidate_summary = SpecificationSummary(
            id=candidate.id,
            name=candidate.name,
            version=candidate.version,
            description=candidate.description,
            domain=candidate.domain,
            subdomain=candidate.subdomain,
            owner=candidate.owner_email,
            goal=candidate.goal,
            kind=candidate.kind.value,
            target_user=candidate.target_user.value,
            tags=candidate.tags or [],
            reusability_score=candidate.reusability_score,
            complexity_score=candidate.complexity_score,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )

        return SimilarityMatch(
            specification=candidate_summary,
            similarity_score=similarity_score,
            match_reasons=match_reasons,
            shared_components=shared_components,
            shared_tags=shared_tags,
        )

    def _is_component_reusable(self, component: "ComponentSpec") -> bool:
        """Determine if a component is reusable"""
        # Simple heuristic: components with provides patterns are more reusable
        return bool(component.provides and len(component.provides) > 0)

    def _extract_config_template(self, components: List[SpecificationComponent]) -> Dict:
        """Extract common configuration template from component list"""
        if not components:
            return {}

        # Get the most common configuration
        configs = [comp.component_config for comp in components if comp.component_config]
        if not configs:
            return {}

        # Simple approach: return the first config as template
        # TODO: Implement more sophisticated pattern extraction
        return configs[0]

    def _extract_provides_template(self, components: List[SpecificationComponent]) -> List[Dict]:
        """Extract common provides template from component list"""
        provides_list = []
        for comp in components:
            if comp.provides_config:
                provides_list.extend(comp.provides_config)

        # Return unique provides patterns
        unique_provides = []
        seen = set()
        for provides in provides_list:
            provides_str = json.dumps(provides, sort_keys=True)
            if provides_str not in seen:
                seen.add(provides_str)
                unique_provides.append(provides)

        return unique_provides


class SpecificationResearchService:
    """Research tools for the agent builder planning phase"""

    def __init__(self, storage_service: SpecificationStorageService):
        self.storage = storage_service

    async def research_similar_agents(self, requirements: AgentRequirements) -> ResearchResults:
        """Find existing agents matching requirements"""

        # Build search query from requirements
        query = SpecificationQuery(
            text_query=requirements.use_case,
            domains=[requirements.domain],
            limit=10
        )

        similar_agents = await self.storage.search_specifications(query)

        # Get component patterns for the domain
        patterns = await self.analyze_reusable_patterns(requirements.domain)

        # Create research results
        return ResearchResults(
            similar_agents=similar_agents,
            available_tools=[],  # TODO: Integrate with MCP catalog
            flow_patterns=[],    # TODO: Implement flow pattern detection
            healthcare_patterns=patterns,
            reusable_components=[]  # TODO: Extract from similar agents
        )

    async def analyze_reusable_patterns(self, domain: str) -> List[ComponentPattern]:
        """Identify common patterns in domain-specific agents"""

        # Get all specifications in domain
        query = SpecificationQuery(
            domains=[domain],
            limit=100
        )

        domain_specs = await self.storage.search_specifications(query)

        # Extract component patterns
        component_usage = {}

        for spec_summary in domain_specs:
            # Get full specification
            from sqlalchemy import select
            stmt = select(AgentSpecification).where(AgentSpecification.id == spec_summary.id)
            result = await self.storage.session.execute(stmt)
            spec = result.scalar_one_or_none()

            if spec and spec.spec_json:
                components = spec.spec_json.get("components", [])
                for comp in components:
                    comp_type = comp.get("type", "unknown")
                    if comp_type not in component_usage:
                        component_usage[comp_type] = {
                            "count": 0,
                            "configs": [],
                            "provides": []
                        }
                    component_usage[comp_type]["count"] += 1
                    if comp.get("config"):
                        component_usage[comp_type]["configs"].append(comp["config"])
                    if comp.get("provides"):
                        component_usage[comp_type]["provides"].extend(comp["provides"])

        # Convert to ComponentPattern objects
        patterns = []
        for comp_type, usage_data in component_usage.items():
            if usage_data["count"] >= 2:  # Used in at least 2 specifications
                pattern = ComponentPattern(
                    component_type=comp_type,
                    usage_frequency=usage_data["count"],
                    common_configs=self._extract_common_config(usage_data["configs"]),
                    typical_provides=usage_data["provides"][:5],  # Top 5 provides patterns
                    description=f"Common {comp_type} component used in {domain} domain",
                    domains=[domain]
                )
                patterns.append(pattern)

        return patterns

    def _extract_common_config(self, configs: List[Dict]) -> Dict:
        """Extract common configuration from list of configs"""
        if not configs:
            return {}

        # Simple approach: find keys that appear in most configs
        key_counts = {}
        for config in configs:
            for key in config.keys():
                key_counts[key] = key_counts.get(key, 0) + 1

        # Return keys that appear in at least half the configs
        threshold = len(configs) / 2
        common_config = {}
        for key, count in key_counts.items():
            if count >= threshold:
                # Get the most common value for this key
                values = [config.get(key) for config in configs if key in config]
                # Use the first non-None value as example
                for value in values:
                    if value is not None:
                        common_config[key] = value
                        break

        return common_config