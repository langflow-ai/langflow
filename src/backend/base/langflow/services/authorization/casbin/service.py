"""The fork's default policy engine over canonical Langflow transactions."""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.authorization.base import (
    AuthorizationAccessSource,
    AuthorizationMutation,
    AuthorizationMutationKind,
    BaseAuthorizationService,
    PublicAuthorizationRequest,
    PublicResourceAction,
    ResourcePolicyMutation,
    ResourceVisibilityScope,
    ShareRuleSnapshot,
)
from lfx.services.authorization.context import authorization_session, current_authorization_session
from sqlmodel import col, select

from langflow.services.authorization.access_ceiling import external_access_allows
from langflow.services.authorization.audit import defer_admission_audits
from langflow.services.authorization.casbin import store
from langflow.services.authorization.casbin.compiler import (
    AssignmentSnapshot,
    AssignmentSource,
    PolicySnapshot,
    RoleSnapshot,
    canonical_domains,
    role_rules,
    share_rules,
)
from langflow.services.authorization.casbin.grammar import (
    PolicyFormatError,
    Rule,
    normalize_request,
    policy_actions,
    validate_domain,
)
from langflow.services.authorization.policy import project_flow_actions
from langflow.services.authorization.repository import (
    ResourceRecord,
    invalid_team_ids,
    load_active_user,
    load_resource,
    resolve_resources,
    resource_id_batches,
    supported_actions,
)
from langflow.services.database.lock_retry import run_with_lock_retry
from langflow.services.database.models.auth import (
    AuthzRole,
    AuthzRoleAssignment,
    AuthzRoleAssignmentGrant,
    AuthzShare,
    AuthzTeam,
    CasbinRule,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    import casbin
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User


class CasbinAuthorizationService(BaseAuthorizationService):
    """Enforce scoped roles, team operations and shares using fresh derived snapshots."""

    SUPPORTS_CROSS_USER_FETCH = True
    HANDLES_CANONICAL_OWNERSHIP = True
    SUPPORTS_PUBLIC_PRINCIPALS = True

    def __init__(self, settings_service: SettingsService) -> None:
        super().__init__()
        self.settings_service = settings_service
        # Validate the installed resource/dependency now; policy readiness follows
        # initialization's committed reconciliation, never constructor optimism.
        store.enforcer_for(())

    async def is_enabled(self) -> bool:
        return bool(self.settings_service.auth_settings.AUTHZ_ENABLED)

    def _superuser_bypass(self) -> bool:
        return bool(getattr(self.settings_service.auth_settings, "AUTHZ_SUPERUSER_BYPASS", True))

    async def supports_team_roles(self) -> bool:
        return True

    async def supports_user_team_sharing(self) -> bool:
        return True

    async def supports_conditional_writes(self) -> bool:
        return True

    @asynccontextmanager
    async def admission_context(self, *, session: Any = None) -> AsyncIterator[AsyncSession]:
        current = current_authorization_session()
        candidate = session if session is not None else (current.session if current else None)
        if candidate is not None and not await self.is_enabled():
            yield candidate
        elif current is not None and current.admission and (session is None or session is current.session):
            yield current.session
        elif candidate is not None and store.owns_writer_lock(candidate):
            with authorization_session(candidate, admission=True, mutation=True):
                yield candidate
        else:
            if not self.ready:
                msg = "Authorization projection has not completed initialization."
                raise RuntimeError(msg)
            async with defer_admission_audits(), store.read_snapshot() as snapshot:
                with authorization_session(snapshot, admission=True):
                    yield snapshot

    async def initialize_authorization(self) -> None:
        """The startup caller owns this transaction; store code never commits."""
        from lfx.services.deps import session_scope

        if not await self.is_enabled():
            return

        async with session_scope() as session:

            async def initialize(_attempt: int) -> None:
                await store.acquire_writer_lock(session)
                wanted = store.compile_policy(await store.canonical_snapshot(session, validate_teams=True))
                stored = (await session.exec(select(CasbinRule))).all()
                # A prior provider's projection cannot be silently erased by
                # selecting this class. Explicit operator repair owns replacement.
                if {store.semantic_rule(row) for row in stored} - set(wanted):
                    msg = "Unrecognized authorization projection; run the authorized policy rebuild before startup."
                    raise RuntimeError(msg)
                await store.reconcile_rules(session, wanted)
                store.enforcer_for(wanted)

            await run_with_lock_retry(initialize, session=session, description="initialize authorization policy")
        self.set_ready()

    async def collaboration_ready(self) -> bool:
        if not self.ready:
            return False
        try:
            async with self.admission_context() as session:
                if await invalid_team_ids(session):
                    return False
                # Touch the required schema and validate any loaded row. All
                # admission rows undergo the same strict grammar validation.
                rows = (await session.exec(select(CasbinRule).limit(1))).all()
                for row in rows:
                    store.semantic_rule(row)
        except Exception:  # noqa: BLE001 - discovery must fail closed
            await logger.aexception("Authorization projection readiness failed")
            return False
        return True

    async def acquire_identity_mutation_lock(
        self,
        *,
        session: Any,
        kind: AuthorizationMutationKind,
        entity_id: UUID | None = None,
        affected_user_ids: tuple[UUID, ...] = (),
    ) -> None:
        _ = (kind, entity_id, affected_user_ids)  # Advisory hints cannot narrow the global writer order.
        if await self.is_enabled():
            await store.acquire_writer_lock(session)

    async def acquire_share_mutation_lock(self, *, session: Any) -> None:
        if await self.is_enabled():
            await store.acquire_writer_lock(session)

    async def acquire_resource_mutation_lock(self, *, session: Any) -> None:
        if await self.is_enabled():
            await store.acquire_writer_lock(session)

    async def stage_identity_mutation(self, *, session: Any, event: AuthorizationMutation) -> None:
        if not await self.is_enabled():
            return
        if event.kind in {AuthorizationMutationKind.API_KEY_CREATED, AuthorizationMutationKind.API_KEY_DELETED}:
            return
        if event.kind is AuthorizationMutationKind.TEAM_UPDATED and not event.policy_relevant_fields:
            return
        await store.reconcile_policy(session)

    async def stage_share_mutation(self, *, session: Any, snapshot: ShareRuleSnapshot) -> None:
        if await self.is_enabled() and snapshot.scope in {"user", "team"}:
            await store.reconcile_policy(session)

    async def stage_resource_mutation(self, *, session: Any, event: ResourcePolicyMutation) -> None:
        if await self.is_enabled() and (
            event.deleted or set(event.changed_fields) & {"folder_id", "project_id", "workspace_id"}
        ):
            await store.reconcile_policy(session)

    async def enforce(
        self, *, user_id: UUID, domain: str, obj: str, act: str, context: dict[str, Any] | None = None
    ) -> bool:
        return (await self.batch_enforce(user_id=user_id, domain=domain, requests=((obj, act),), context=context))[0]

    @staticmethod
    def _policy_allows(
        enforcer: casbin.Enforcer,
        *,
        user_id: UUID,
        domains: Sequence[str],
        obj: str,
        act: str,
        collection: bool = False,
    ) -> bool:
        return any(
            enforcer.enforce(*normalize_request(user_id, domain, obj, act, collection_operation=collection))
            for domain in domains
        )

    def _resource_allows(
        self,
        enforcer: casbin.Enforcer,
        *,
        user: User,
        resource: ResourceRecord,
        projects: dict[UUID, ResourceRecord],
        act: str,
        obj: str,
    ) -> bool:
        domains = canonical_domains(resource, projects)
        if not external_access_allows(act) or act not in supported_actions(resource.resource_type):
            return False
        if (user.is_superuser is True and self._superuser_bypass()) or resource.owner_id == user.id:
            return True
        parent = projects.get(resource.project_id) if resource.project_id is not None else None
        if (
            resource.resource_type == "flow"
            and parent is not None
            and parent.owner_id == user.id
            and act in project_flow_actions("admin")
        ):
            return True
        return self._policy_allows(
            enforcer, user_id=user.id, domains=domains, obj=obj, act=act, collection=obj.endswith(":*")
        )

    async def batch_enforce(
        self, *, user_id: UUID, domain: str, requests: Sequence[tuple[str, str]], context: dict[str, Any] | None = None
    ) -> list[bool]:
        if not requests:
            return []
        if not await self.is_enabled():
            return [True] * len(requests)
        try:
            validate_domain(domain)
        except (ValueError, TypeError):
            return [False] * len(requests)
        async with self.admission_context() as session:
            return await self._batch_in_session(
                session, user_id=user_id, requests=requests, context=dict(context or {})
            )

    async def _batch_in_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        requests: Sequence[tuple[str, str]],
        context: dict[str, Any],
        enforcer: casbin.Enforcer | None = None,
    ) -> list[bool]:
        user = await load_active_user(session, user_id)
        if user is None:
            return [False] * len(requests)
        parsed = [self._parse_object(obj) for obj, _ in requests]
        ids_by_type: dict[str, list[UUID]] = {}
        for item in parsed:
            if item is not None and item[1] is not None and item[0] not in {"share", "team"}:
                ids_by_type.setdefault(item[0], []).append(item[1])
        canonical: dict[tuple[str, UUID | None], ResourceRecord] = {}
        for resource_type, ids in ids_by_type.items():
            canonical.update(
                ((resource_type, rid), row)
                for rid, row in (
                    await resolve_resources(session, resource_type=resource_type, resource_ids=ids)
                ).items()
            )
        for item in set(parsed):
            if item is not None and item[1] is None and item[0] not in {"share", "team", "voice"}:
                resource = await self._virtual_creation_resource(
                    session, user_id=user_id, resource_type=item[0], context=context
                )
                if resource is not None:
                    canonical[item] = resource
        share_resource = None
        if any(item is not None and item[0] == "share" for item in parsed):
            with suppress(KeyError, ValueError, TypeError):
                share_resource = await load_resource(
                    session, resource_type=context["resource_type"], resource_id=UUID(str(context["resource_id"]))
                )
        resources = list(canonical.values()) + ([share_resource] if share_resource is not None else [])
        project_ids = {r.project_id for r in resources if r.project_id is not None}
        projects = await resolve_resources(session, resource_type="project", resource_ids=tuple(project_ids))
        projects.update((r.resource_id, r) for r in resources if r.resource_type == "project")
        domains = {"*"}
        for resource in resources:
            try:
                domains.update(canonical_domains(resource, projects))
            except ValueError:
                continue
        objects = {obj.replace(":", "/", 1) for obj, _ in requests}
        objects.update(f"{item[0]}/*" for item in parsed if item is not None and item[0] != "team")
        if share_resource is not None:
            objects.update(
                (f"{share_resource.resource_type}/{share_resource.resource_id}", f"{share_resource.resource_type}/*")
            )
        if enforcer is None:
            enforcer = store.enforcer_for(
                await store.load_rules(session, user_id=user_id, domains=tuple(domains), objects=tuple(objects))
            )
        team_ids = {item[1] for item in parsed if item is not None and item[0] == "team" and item[1] is not None}
        existing_teams = (
            set((await session.exec(select(AuthzTeam.id).where(col(AuthzTeam.id).in_(team_ids)))).all())
            if team_ids
            else set()
        )
        decisions: list[bool] = []
        for item, (obj, act) in zip(parsed, requests, strict=True):
            try:
                normalize_request(user_id, "*", obj, act, collection_operation=True)
                if item is None:
                    decisions.append(False)
                    continue
                resource_type, resource_id = item
                if resource_type == "team":
                    allowed = resource_id in existing_teams and external_access_allows(
                        "read" if act == "read" else "write"
                    )
                    decisions.append(
                        allowed
                        and (
                            (user.is_superuser is True and self._superuser_bypass() and external_access_allows("admin"))
                            or self._policy_allows(enforcer, user_id=user_id, domains=("*",), obj=obj, act=act)
                        )
                    )
                elif resource_type == "share":
                    decisions.append(
                        share_resource is not None
                        and self._share_allows(
                            enforcer, user=user, resource=share_resource, projects=projects, act=act, context=context
                        )
                    )
                elif resource_type == "voice":
                    owner = self._canonical_voice_owner(context)
                    decisions.append(
                        owner is not None
                        and external_access_allows(act)
                        and act == "read"
                        and ((user.is_superuser is True and self._superuser_bypass()) or owner == user_id)
                    )
                else:
                    resource = canonical.get(item)
                    decisions.append(
                        resource is not None
                        and self._resource_allows(
                            enforcer, user=user, resource=resource, projects=projects, act=act, obj=obj
                        )
                    )
            except (PolicyFormatError, ValueError, TypeError):
                decisions.append(False)
        return decisions

    def _share_allows(
        self,
        enforcer: casbin.Enforcer,
        *,
        user: User,
        resource: ResourceRecord,
        projects: dict[UUID, ResourceRecord],
        act: str,
        context: dict[str, Any],
    ) -> bool:
        domains = canonical_domains(resource, projects)
        if not external_access_allows(act):
            return False
        if resource.owner_id == user.id or (user.is_superuser is True and self._superuser_bypass()):
            return True
        if self._policy_allows(enforcer, user_id=user.id, domains=domains, obj="share:*", act=act, collection=True):
            return True
        subject = context.get("subject_user_id")
        return (
            act == "read"
            and not context.get("share_management_only")
            and (subject is None or str(subject) == str(user.id))
            and self._resource_allows(
                enforcer,
                user=user,
                resource=resource,
                projects=projects,
                obj=f"{resource.resource_type}:{resource.resource_id}",
                act="read",
            )
        )

    async def list_visible_resource_ids(
        self,
        *,
        user_id: UUID,
        resource_type: str,
        domain: str = "*",
        act: str = "read",
        context: dict[str, Any] | None = None,
    ) -> list[UUID] | None:
        if not await self.is_enabled():
            return None
        try:
            validate_domain(domain)
        except (ValueError, TypeError):
            return []
        async with self.admission_context() as session:
            if not external_access_allows(act) or act not in supported_actions(resource_type):
                return []
            enforcer = store.enforcer_for(await store.load_rules(session, user_id=user_id))
            allowed: list[UUID] = []
            async for batch in resource_id_batches(session, resource_type=resource_type):
                decisions = await self._batch_in_session(
                    session,
                    user_id=user_id,
                    requests=tuple((f"{resource_type}:{rid}", act) for rid in batch),
                    context=dict(context or {}),
                    enforcer=enforcer,
                )
                allowed.extend(rid for rid, decision in zip(batch, decisions, strict=True) if decision)
            return allowed

    async def get_resource_visibility(
        self,
        *,
        user_id: UUID,
        resource_type: str,
        domain: str = "*",
        act: str = "read",
        context: dict[str, Any] | None = None,
    ) -> ResourceVisibilityScope | None:
        if not await self.is_enabled():
            return None
        if not external_access_allows(act) or act not in policy_actions(resource_type):
            return ResourceVisibilityScope(require_canonical_context=True)
        try:
            validate_domain(domain)
        except (ValueError, TypeError):
            return ResourceVisibilityScope(require_canonical_context=True)
        async with self.admission_context() as session:
            user = await load_active_user(session, user_id)
            if user is None:
                return ResourceVisibilityScope(require_canonical_context=True)
            if user.is_superuser is True and self._superuser_bypass():
                return ResourceVisibilityScope(all_resources=True, require_canonical_context=True)
            rules = await store.load_rules(session, user_id=user_id)
            enforcer = store.enforcer_for(rules)
            # Project only this model's finite, exact-domain policies. Every
            # scope below is proven by the same engine used for direct checks;
            # there is no canonical grant union acting as a second evaluator.
            workspaces: set[UUID] = set()
            projects: set[UUID] = set()
            exact_ids: set[UUID] = set()
            all_resources = False
            for rule in rules:
                if (
                    rule.ptype != "p"
                    or rule.v3 != act
                    or rule.v2 is None
                    or not rule.v2.startswith(f"{resource_type}/")
                ):
                    continue
                identifier = rule.v2.split("/", 1)[1]
                probe = f"{resource_type}/{UUID(int=0)}" if identifier == "*" else rule.v2
                if not enforcer.enforce(f"user:{user_id}", rule.v1, probe, act):
                    continue
                if identifier != "*":
                    exact_ids.add(UUID(identifier))
                elif rule.v1 == "*":
                    all_resources = True
                elif rule.v1.startswith("workspace:"):
                    workspaces.add(UUID(rule.v1[10:]))
                else:
                    projects.add(UUID(rule.v1[8:]))
            if resource_type == "share":
                return ResourceVisibilityScope(
                    all_resources=all_resources,
                    workspace_ids=tuple(sorted(workspaces)),
                    project_ids=tuple(sorted(projects)),
                )
            # Concrete grants remain valid only for current canonical objects.
            candidates = sorted(exact_ids)
            allowed_ids: list[UUID] = []
            for offset in range(0, len(candidates), 200):
                batch = candidates[offset : offset + 200]
                decisions = await self._batch_in_session(
                    session,
                    user_id=user_id,
                    requests=tuple((f"{resource_type}:{rid}", act) for rid in batch),
                    context=dict(context or {}),
                    enforcer=enforcer,
                )
                allowed_ids.extend(rid for rid, allowed in zip(batch, decisions, strict=True) if allowed)
            return ResourceVisibilityScope(
                all_resources=all_resources,
                resource_ids=tuple(allowed_ids),
                workspace_ids=tuple(sorted(workspaces)),
                project_ids=tuple(sorted(projects)),
                owner_id=user_id,
                project_owner_id=(
                    user_id if resource_type == "flow" and act in project_flow_actions("admin") else None
                ),
                require_canonical_context=True,
            )

    async def get_access_sources(
        self, *, user_id: UUID, resource_type: str, resource_id: UUID
    ) -> tuple[AuthorizationAccessSource, ...]:
        """Explain existing engine decisions with bounded canonical provenance.

        The compiler supplies source tuples; only tuples present in the loaded
        projection and allowed by its enforcer contribute an explanation.
        """
        async with self.admission_context() as session:
            user = await load_active_user(session, user_id)
            resource = await load_resource(session, resource_type=resource_type, resource_id=resource_id)
            if user is None or resource is None:
                return ()
            projects = await resolve_resources(
                session, resource_type="project", resource_ids=(resource.project_id,) if resource.project_id else ()
            )
            if resource_type == "project":
                projects[resource_id] = resource
            domains = canonical_domains(resource, projects)
            rules = await store.load_rules(
                session,
                user_id=user_id,
                domains=domains,
                objects=(f"{resource_type}/{resource_id}", f"{resource_type}/*"),
            )
            enforcer = store.enforcer_for(rules)
            actions = tuple(sorted(supported_actions(resource_type)))
            decisions = await self._batch_in_session(
                session,
                user_id=user_id,
                requests=tuple((f"{resource_type}:{resource_id}", act) for act in actions),
                context={},
                enforcer=enforcer,
            )
            allowed = {act for act, decision in zip(actions, decisions, strict=True) if decision}
            if not allowed:
                return ()
            sources: list[AuthorizationAccessSource] = []
            if user.is_superuser is True and self._superuser_bypass():
                sources.append(AuthorizationAccessSource("platform_admin", tuple(sorted(allowed))))
            if resource.owner_id == user_id:
                sources.append(AuthorizationAccessSource("owner", tuple(sorted(allowed)), resource_id))
            parent = projects.get(resource.project_id) if resource.project_id is not None else None
            if resource_type == "flow" and parent is not None and parent.owner_id == user_id:
                sources.append(
                    AuthorizationAccessSource(
                        "project_owner",
                        tuple(sorted(allowed & project_flow_actions("admin"))),
                        parent.resource_id,
                        parent.display_name,
                    )
                )
            present = set(rules)

            def proven(source_rules: set[Rule]) -> tuple[str, ...]:
                return tuple(
                    sorted(
                        {
                            rule.v3
                            for rule in source_rules & present
                            if rule.v3 is not None
                            and rule.v3 in allowed
                            and rule.v1 in domains
                            and rule.v2 in {f"{resource_type}/{resource_id}", f"{resource_type}/*"}
                            and enforcer.enforce(f"user:{user_id}", rule.v1, f"{resource_type}/{resource_id}", rule.v3)
                        }
                    )
                )

            principals = {f"user:{user_id}", *(rule.v1 for rule in rules if rule.ptype == "g")}
            from sqlalchemy import and_, or_

            resource_clauses = [and_(AuthzShare.resource_type == resource_type, AuthzShare.resource_id == resource_id)]
            if resource_type == "flow" and resource.project_id is not None:
                resource_clauses.append(
                    and_(AuthzShare.resource_type == "project", AuthzShare.resource_id == resource.project_id)
                )
            # Only the subject's direct and eligible team sources, at most one
            # resource and its immediate project. No graph or sibling metadata.
            team_ids = [UUID(principal[5:]) for principal in principals if principal.startswith("team/")]
            target_clauses = [and_(AuthzShare.scope == "user", AuthzShare.target_id == user_id)]
            if team_ids:
                target_clauses.append(and_(AuthzShare.scope == "team", col(AuthzShare.target_id).in_(team_ids)))
            shares = (
                await session.exec(
                    select(AuthzShare)
                    .where(or_(*resource_clauses), or_(*target_clauses))
                    .order_by(AuthzShare.id)
                    .limit(50)
                )
            ).all()
            for share in shares:
                principal = f"user:{share.target_id}" if share.scope == "user" else f"team/{share.target_id}"
                snapshot = ShareRuleSnapshot(
                    share.id,
                    share.resource_type,
                    share.resource_id,
                    share.scope,
                    share.target_id,
                    share.permission_level,
                )
                source_actions = proven(share_rules(snapshot, principal=principal))
                if source_actions:
                    inherited = share.resource_type == "project" and resource_type == "flow"
                    kind = f"inherited_{share.scope}_share" if inherited else f"{share.scope}_share"
                    sources.append(AuthorizationAccessSource(kind, source_actions, share.id))
            assignments = (
                await session.exec(
                    select(AuthzRoleAssignment)
                    .where(AuthzRoleAssignment.user_id == user_id)
                    .order_by(AuthzRoleAssignment.id)
                    .limit(50)
                )
            ).all()
            role_ids = {row.role_id for row in assignments}
            roles: dict[UUID, AuthzRole] = {}
            for _ in range(32):
                missing = role_ids - roles.keys()
                if not missing:
                    break
                parents = (await session.exec(select(AuthzRole).where(col(AuthzRole.id).in_(missing)))).all()
                roles.update((row.id, row) for row in parents)
                role_ids.update(row.parent_role_id for row in parents if row.parent_role_id is not None)
                if not parents:
                    break
            grants = (
                (
                    await session.exec(
                        select(AuthzRoleAssignmentGrant).where(
                            col(AuthzRoleAssignmentGrant.assignment_id).in_([row.id for row in assignments])
                        )
                    )
                ).all()
                if assignments
                else ()
            )
            for assignment in assignments:
                role = roles.get(assignment.role_id)
                if role is None:
                    continue
                assignment_sources = tuple(
                    AssignmentSource(row.source_kind, row.provider_id, row.external_group)
                    for row in grants
                    if row.assignment_id == assignment.id
                )
                assignment_snapshot = PolicySnapshot(
                    active_user_ids=frozenset({user_id}),
                    roles=tuple(
                        RoleSnapshot(row.id, tuple(row.permissions), row.parent_role_id, row.workspace_id)
                        for row in roles.values()
                    ),
                    assignments=(
                        AssignmentSnapshot(
                            assignment.id,
                            user_id,
                            assignment.role_id,
                            assignment.domain_type,
                            assignment.domain_id,
                            assignment_sources,
                        ),
                    ),
                )
                source_actions = proven(role_rules(assignment_snapshot, projects))
                if source_actions:
                    sources.append(AuthorizationAccessSource("role", source_actions, assignment.id, role.name))
            return tuple(sources[:50])

    @staticmethod
    def _parse_object(obj: str) -> tuple[str, UUID | None] | None:
        if not isinstance(obj, str):
            return None
        resource_type, separator, raw_id = obj.partition(":")
        if not separator or not resource_type:
            return None
        if raw_id == "*":
            return resource_type, None
        try:
            return resource_type, UUID(raw_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _canonical_voice_owner(context: dict[str, Any]) -> UUID | None:
        """Validate the server-resolved owner used for provider-backed voices."""
        raw_owner_id = context.get("voice_user_id")
        if raw_owner_id is None:
            return None
        try:
            return UUID(str(raw_owner_id))
        except (TypeError, ValueError):
            return None

    async def _virtual_creation_resource(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        resource_type: str,
        context: dict[str, Any],
    ) -> ResourceRecord | None:
        # Model settings use the existing server-classified personal variable
        # collection. The caller was loaded as active in this same snapshot.
        if (
            resource_type == "variable"
            and context.get("resource_type") == "variable"
            and context.get("resource_id") is None
            and context.get("variable_user_id") == user_id
        ):
            return ResourceRecord(resource_type, UUID(int=0), user_id)
        if context.get("intrinsic_creation") is not True:
            return None

        if resource_type in {"flow", "deployment"}:
            raw_project_id = context.get("folder_id") or context.get("project_id")
            if raw_project_id is None:
                return None
            try:
                project_id = UUID(str(raw_project_id))
            except (TypeError, ValueError):
                return None
            project = await load_resource(session, resource_type="project", resource_id=project_id)
            if project is None:
                return None
            return ResourceRecord(
                resource_type=resource_type,
                resource_id=UUID(int=0),
                owner_id=None,
                project_id=project.resource_id,
                workspace_id=project.workspace_id,
            )

        # These are personal create operations: the route has already selected
        # the canonical current identity and has no existing row to inspect.
        if resource_type in {
            "project",
            "knowledge_base",
            "variable",
            "file",
            "provider_account",
        }:
            return ResourceRecord(resource_type, UUID(int=0), user_id)
        return None

    async def resolve_public_tenant(self, request: PublicAuthorizationRequest) -> str | None:
        """Use only the already server-resolved domain hint as a local tenant."""
        return request.domain_hint if request.domain_hint else None

    async def enforce_public(self, request: PublicAuthorizationRequest, *, tenant: str) -> bool:
        if not await self.is_enabled() or tenant != request.domain_hint:
            return False
        if request.resource_type != "flow" or request.action not in {
            PublicResourceAction.READ,
            PublicResourceAction.EXECUTE,
        }:
            return False
        if request.grant_source != "authz_share":
            # Compatibility grants were resolved from the current Flow row by
            # public_access immediately before this hook.
            return request.grant_source in {"legacy_access_type", "a2a_auth_none"}

        async with self.admission_context() as session:
            statement = select(AuthzShare.permission_level).where(
                AuthzShare.resource_type == "flow",
                AuthzShare.resource_id == request.resource_id,
                AuthzShare.scope == "public",
            )
            permission = (await session.exec(statement)).first()
        if request.action is PublicResourceAction.READ:
            return permission in {"read", "execute", "write", "admin"}
        return permission in {"execute", "write", "admin"}
