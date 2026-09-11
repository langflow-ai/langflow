"""Seed an adversarial OSS Langflow instance for migration rehearsal.

Not a large instance. A small one where every row exists to trip a specific failure
mode a whole-instance migration can hit. Each fixture below names what it catches.

See README.md in this directory for how to run it, the full fixture list, and the
engine differences it accommodates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

NOW = datetime.now(timezone.utc)
DIM = 8  # vector width; the transport does not care what it is


def uid(n: int, tag: str = "0") -> UUID:
    """Deterministic id, stable across runs so assertions can name rows directly.

    Returns a real ``UUID``. Binding these as strings through ``text()`` writes the
    dashed 36-char form on SQLite, where ``sa.Uuid`` stores 32-char undashed hex, so
    seeded rows and ORM-written rows land in the same column under two spellings and
    no typed lookup matches. Postgres normalizes both, which hides it there.
    """
    return UUID(f"{n:08x}-{tag * 4}-4000-8000-{'0' * 12}")


# Stable ids, so the manifest and any assertion can name rows directly.
U_SUPER = uid(1, "a")  # owns everything, the auto-login shape
U_ALICE = uid(2, "a")
U_BOB = uid(3, "a")
T_TEAM = uid(1, "b")
R_CUSTOM = uid(1, "c")
R_CHILD = uid(2, "c")
F_ROOT = uid(1, "d")
F_CHILD = uid(2, "d")
FL_MAIN = uid(1, "e")
FL_SHARED = uid(2, "e")
KB_OK = uid(1, "f")
KB_NOMODEL = uid(2, "f")
KB_STUB = uid(3, "f")
MB_ONE = uid(1, "9")
JOB_PAUSED = uid(1, "8")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=300, help="vectors to seed into the bulk knowledge base (0 or more)")
    ap.add_argument("--manifest", default="manifest.json")
    args = ap.parse_args()
    if args.chunks < 0:
        ap.error("--chunks must be 0 or more")

    # Real startup path, so alembic stamps the schema and seeds its own rows.
    from langflow.services.database.utils import initialize_database

    await initialize_database()

    import sqlalchemy as sa
    from langflow.services.auth.utils import encrypt_api_key
    from langflow.services.database.models.auth.sso_secret import encrypt_sso_client_secret
    from langflow.services.deps import get_settings_service, session_scope
    from sqlalchemy import bindparam, text

    enc = encrypt_api_key

    async with session_scope() as s:
        already = (
            await s.exec(text('select count(*) from "user" where username = :n'), params={"n": "langflow"})
        ).all()
        if already and already[0][0]:
            print("already seeded: this database has the fixture superuser. Point at an empty database.")
            return

        async def ex(sql: str, **p):
            # Type the UUID params. Without this the raw string is stored verbatim
            # and SQLite ends up with a spelling the ORM cannot match.
            stmt = text(sql)
            uuid_binds = [bindparam(k, type_=sa.Uuid()) for k, v in p.items() if isinstance(v, UUID)]
            if uuid_binds:
                stmt = stmt.bindparams(*uuid_binds)
            await s.exec(stmt, params=p)

        # --- identity -------------------------------------------------------
        # The superuser owns everything, which is what an auto-login install
        # looks like. Catches: teardown_superuser deleting credentials, files
        # and folders on SQLite while orphaning flows (LE-2516).
        for u, name, su in ((U_SUPER, "langflow", True), (U_ALICE, "alice", False), (U_BOB, "bob", False)):
            await ex(
                'insert into "user"(id,username,password,is_active,is_superuser,create_at,updated_at)'
                " values (:i,:n,:p,:a,:s,:c,:c)",
                i=u,
                n=name,
                p="x",
                a=True,
                s=su,
                c=NOW,
            )

        # --- authz ----------------------------------------------------------
        # A custom role parented on a system role. Catches: the role-id
        # alignment failing, because parent_role_id has no ON UPDATE CASCADE.
        admin_id = (await s.exec(text("select id from authz_role where name='admin'"))).first()[0]
        await ex(
            "insert into authz_role(id,name,description,is_system,permissions,parent_role_id,created_at,updated_at)"
            " values (:i,:n,:d,:sys,:perm,:par,:c,:c)",
            i=R_CUSTOM,
            n="team-lead",
            d="custom role parented on admin",
            sys=False,
            perm="[]",
            par=admin_id,
            c=NOW,
        )
        # A second custom role under the first, so remapping a chain is exercised
        # rather than only a single custom-to-system link.
        await ex(
            "insert into authz_role(id,name,description,is_system,permissions,parent_role_id,created_at,updated_at)"
            " values (:i,:n,:d,:sys,:perm,:par,:c,:c)",
            i=R_CHILD,
            n="team-lead-junior",
            d="custom role parented on another custom role",
            sys=False,
            perm="[]",
            par=R_CUSTOM,
            c=NOW,
        )

        # Assignments on both a system role and a custom one.
        for aid, uid_, rid in ((uid(1, "7"), U_ALICE, admin_id), (uid(2, "7"), U_BOB, R_CUSTOM)):
            await ex(
                "insert into authz_role_assignment(id,user_id,role_id,domain_type,assigned_at)"
                " values (:i,:u,:r,'global',:c)",
                i=aid,
                u=uid_,
                r=rid,
                c=NOW,
            )
        await ex(
            "insert into authz_team(id,team_name,adom_name,is_active,created_at,updated_at)"
            " values (:i,:n,:a,:act,:c,:c)",
            i=T_TEAM,
            n="platform",
            a="default",
            act=True,
            c=NOW,
        )
        await ex(
            "insert into authz_team_member(id,team_id,user_id,source,created_at) values (:i,:t,:u,'manual',:c)",
            i=uid(1, "6"),
            t=T_TEAM,
            u=U_BOB,
            c=NOW,
        )
        # Shares to a user and to a team. Catches: resource_id and target_id are
        # polymorphic with no foreign key, so stale values insert cleanly and
        # grant nothing.
        for sid, scope, target in ((uid(1, "5"), "user", U_BOB), (uid(2, "5"), "team", T_TEAM)):
            await ex(
                "insert into authz_share(id,resource_type,resource_id,scope,target_id,"
                "permission_level,created_by,created_at) values (:i,'flow',:res,:sc,:tg,'read',:cb,:c)",
                i=sid,
                res=FL_SHARED,
                sc=scope,
                tg=target,
                cb=U_ALICE,
                c=NOW,
            )

        # --- content --------------------------------------------------------
        # Nested folders. Catches: the self-referential FK, which forces parents
        # before children in the carry order.
        await ex(
            "insert into folder(id,name,description,user_id) values (:i,:n,:d,:u)",
            i=F_ROOT,
            n="root-project",
            d="parent",
            u=U_SUPER,
        )
        await ex(
            "insert into folder(id,name,description,parent_id,user_id) values (:i,:n,:d,:p,:u)",
            i=F_CHILD,
            n="nested-project",
            d="child",
            p=F_ROOT,
            u=U_SUPER,
        )
        for fid, nm, fold in ((FL_MAIN, "main-flow", F_ROOT), (FL_SHARED, "shared-flow", F_CHILD)):
            await ex(
                "insert into flow(id,name,data,user_id,folder_id,access_type,flow_type,is_component)"
                " values (:i,:n,:d,:u,:f,'PRIVATE','workflow',:c)",
                i=fid,
                n=nm,
                d="{}",
                u=U_SUPER,
                f=fold,
                c=False,
            )
        await ex(
            "insert into flow_version(id,flow_id,user_id,version_number,data,created_at) values (:i,:f,:u,1,:d,:c)",
            i=uid(1, "4"),
            f=FL_MAIN,
            u=U_SUPER,
            d="{}",
            c=NOW,
        )
        # A two-version chain on the flow both shares point at, so version ordering
        # has something to carry.
        for vnum, vid in ((1, uid(2, "4")), (2, uid(3, "4"))):
            await ex(
                "insert into flow_version(id,flow_id,user_id,version_number,data,created_at)"
                " values (:i,:f,:u,:v,:d,:c)",
                i=vid,
                f=FL_SHARED,
                u=U_SUPER,
                v=vnum,
                d="{}",
                c=NOW,
            )

        # --- secret-bearing rows, four different mechanisms -----------------
        # Catches: re-encryption. A wrong key returns "" rather than raising,
        # with a warning below the default log level (LE-2519).
        await ex(
            "insert into variable(id,name,value,type,user_id,created_at,updated_at)"
            " values (:i,:n,:v,'Credential',:u,:c,:c)",
            i=uid(1, "3"),
            n="OPENAI_API_KEY",
            v=enc("sk-fixture-secret-123"),
            u=U_SUPER,
            c=NOW,
        )
        await ex(
            "insert into apikey(id,name,api_key,api_key_hash,user_id,total_uses,is_active,created_at)"
            " values (:i,:n,:k,:h,:u,0,:a,:c)",
            i=uid(2, "3"),
            n="ci-key",
            k=enc("lf-fixture-apikey"),
            h="0" * 64,
            u=U_SUPER,
            a=True,
            c=NOW,
        )
        await ex(
            # config is where this model keeps secrets. MCP_SECRET_CONFIG_MAPS names
            # env and headers as the sub-maps whose values are encrypted at rest.
            "insert into mcp_server(id,user_id,name,transport,config,enabled,version,created_at,updated_at)"
            " values (:i,:u,:n,'stdio',:cfg,:e,1,:c,:c)",
            i=uid(3, "3"),
            u=U_SUPER,
            n="fixture-mcp",
            cfg=json.dumps({"command": "uvx", "env": {"API_TOKEN": enc("mcp-fixture-token")}}),
            e=True,
            c=NOW,
        )
        # scripts/migrate_secret_key.py enumerates the secret-key-derived columns.
        # Seed the two that sit on rows this fixture already creates, plus an SSO config.
        await ex('update "user" set store_api_key=:k where id=:i', k=enc("store-fixture-key"), i=U_SUPER)
        await ex(
            "update folder set auth_settings=:a where id=:i",
            a=json.dumps({"api_key": enc("folder-fixture-key")}),
            i=F_ROOT,
        )
        await ex(
            "insert into sso_config(id,slug,display_name,protocol,enabled,sort_order,provider_settings,"
            "client_secret_encrypted,email_claim,username_claim,user_id_claim,created_by,created_at,updated_at)"
            " values (:i,'fixture-idp','Fixture IdP','oidc',:e,1,:ps,:cs,'email','preferred_username','sub',:u,:c,:c)",
            i=uid(4, "3"),
            e=False,
            # ck_sso_config_protocol_consistency requires provider_settings.protocol
            # to match the column. enabled=False keeps the stricter oidc check off.
            ps=json.dumps({"protocol": "oidc", "issuer": "https://idp.example"}),
            # This column has its own at-rest contract: an AES-256-GCM envelope
            # keyed by HKDF off LANGFLOW_SECRET_KEY, not Fernet. A CHECK constraint
            # rejects anything else, so enc() is the wrong encryptor here.
            cs=encrypt_sso_client_secret("sso-fixture-secret"),
            u=U_SUPER,
            c=NOW,
        )

        # --- files, both path shapes ----------------------------------------
        # Catches: file.path holds absolute and logical forms in practice, since
        # parse_file_path accepts either. An absolute local path is meaningless
        # against a bucket.
        await ex(
            "insert into file(id,user_id,name,path,size,provider,created_at,updated_at)"
            " values (:i,:u,:n,:p,:s,null,:c,:c)",
            i=uid(1, "2"),
            u=U_SUPER,
            n="logical.txt",
            p=f"{U_SUPER}/logical.txt",
            s=11,
            c=NOW,
        )
        await ex(
            "insert into file(id,user_id,name,path,size,provider,created_at,updated_at)"
            " values (:i,:u,:n,:p,:s,null,:c,:c)",
            i=uid(2, "2"),
            u=U_SUPER,
            n="absolute.txt",
            p=f"/var/lib/langflow/{U_SUPER}/absolute.txt",
            s=12,
            c=NOW,
        )

        # --- knowledge bases, three awkward shapes --------------------------
        kbs = (
            # normal: local Chroma, model recorded. The copy path.
            (KB_OK, "kb-ok", "chroma", {"provider": "OpenAI", "model": "text-embedding-3-small"}, args.chunks),
            # empty model_selection. Catches: resolve_embedding_selection silently
            # falling back to OpenAI, so the row claims a model it may never have used.
            (KB_NOMODEL, "kb-no-model", "chroma", {}, 5),
            # a backend that parses but cannot be instantiated. Catches: BackendType
            # still carries astra/mongodb while create_backend refuses them.
            (KB_STUB, "kb-stubbed-backend", "astra", {"provider": "OpenAI", "model": "x"}, 0),
        )
        for kid, nm, backend, sel, chunks in kbs:
            await ex(
                "insert into knowledge_base(id,name,user_id,model_selection,chunk_size,chunk_overlap,"
                "column_config,backend_type,backend_config,chunks,words,characters,size_bytes,"
                "source_types,status,created_at,updated_at)"
                " values (:i,:n,:u,:sel,1000,200,'[]',:bt,'{}',:ch,0,0,0,'[]','ready',:c,:c)",
                i=kid,
                n=nm,
                u=U_SUPER,
                sel=json.dumps(sel),
                bt=backend,
                ch=chunks,
                c=NOW,
            )

        # --- memory base ----------------------------------------------------
        # Catches: message_ingestion_record cursors advance only after a confirmed
        # vector write, so records marked ingested are never re-processed.
        await ex(
            "insert into memory_base(id,name,flow_id,user_id,threshold,auto_capture,embedding_model,"
            "preprocessing,kb_name,created_at) values (:i,:n,:f,:u,5,:ac,:em,:pp,:kb,:c)",
            i=MB_ONE,
            n="fixture-memory",
            f=FL_MAIN,
            u=U_SUPER,
            ac=True,
            em="text-embedding-3-small",
            pp=False,
            kb="kb-ok",
            c=NOW,
        )
        await ex(
            "insert into memory_base_session(id,session_id,total_processed,memory_base_id) values (:i,:s,2,:m)",
            i=uid(1, "1"),
            s="session-fixture",
            m=MB_ONE,
        )
        for n in range(2):
            mid = uid(10 + n, "1")
            await ex(
                "insert into message(id,timestamp,sender,sender_name,session_id,text,error,edit,is_output)"
                " values (:i,:t,'User','alice','session-fixture',:tx,:e,:e,:e)",
                i=mid,
                t=NOW,
                tx=f"fixture message {n}",
                e=False,
            )
            await ex(
                "insert into message_ingestion_record(id,message_id,memory_base_id,session_id,ingested_at)"
                " values (:i,:m,:mb,'session-fixture',:c)",
                i=uid(20 + n, "1"),
                m=mid,
                mb=MB_ONE,
                c=NOW,
            )

        # --- live state that looks like history -----------------------------
        # Catches: job_checkpoints and a2a_checkpoints are resume state, not logs.
        # Dropping them makes every paused run unresumable.
        await ex(
            # 'suspended' is the paused state in job_status_enum. Postgres enforces
            # the enum; SQLite does not, so an invalid value only fails on conversion.
            "insert into job(job_id,flow_id,status,created_timestamp,user_id) values (:i,:f,'suspended',:c,:u)",
            i=JOB_PAUSED,
            f=FL_MAIN,
            c=NOW,
            u=U_SUPER,
        )
        await ex(
            "insert into job_checkpoints(id,job_id,kind,blob,created_at,updated_at) values (:i,:j,'graph',:b,:c,:c)",
            i=uid(1, "0"),
            j=JOB_PAUSED,
            b='{"resume":"state"}',
            c=NOW,
        )
        await ex(
            "insert into a2a_tasks(id,owner,task) values (:i,:o,:t)",
            i=uid(2, "0"),
            o=U_SUPER,
            t='{"state":"input-required"}',
        )
        await ex(
            "insert into a2a_checkpoints(run_id,checkpoint) values (:i,:c)",
            i=uid(3, "0"),
            c='{"graph":"paused"}',
        )

        # --- rows both sides seed, which must be upserted not skipped -------
        # Catches: skipping silently resets the provider allowlist, enforce_sso,
        # and the whole governance revision history.
        await ex(
            "update model_provider_policy set approved_provider_ids=:p, version=7 where id=1",
            p='["openai","anthropic"]',
        )
        await ex("update sso_settings set enforce_sso=:e where id=1", e=True)
        await ex(
            "insert into policy_bundle_revision(revision,initialized,approved_provider_ids,"
            "blocked_component_keys,blocked_template_keys,content_hash,source,created_at,reason)"
            " values (2,:i,:p,'[]','[]',:h,'admin',:c,:r)",
            i=True,
            p='["openai"]',
            h="f" * 64,
            c=NOW,
            r="fixture second revision",
        )
        # The real writer sets revision and initialized together. Setting revision alone
        # leaves a state production cannot produce, which
        # bootstrap_policy_bundle_if_pristine reads as pristine and overwrites.
        await ex("update policy_bundle_active set revision=2, initialized=:i where id=1", i=True)

        # --- vectors and bytes, the state that lives outside the database -----
        # A knowledge base row without vectors is worse than no fixture: the
        # reconciliation compares backend count() against the row's cached
        # `chunks`, so an empty store under a row claiming N reports an N-row
        # shortfall, which is exactly the signature of a silently truncated read.
        kb_dir = None
        if args.chunks:
            from langflow.api.utils.kb_helpers import KBStorageHelper
            from lfx.base.knowledge_bases.backends import ChromaLocalBackend

            kb_dir = KBStorageHelper.get_root_path() / "langflow" / "kb-ok"
            kb_dir.mkdir(parents=True, exist_ok=True)
            # No embedding model is involved. The copy path moves opaque float
            # arrays, so deterministic values exercise it exactly as real ones do.
            backend = ChromaLocalBackend(kb_name="kb-ok", kb_path=kb_dir)
            await backend.ensure_ready()
            backend.vector_store._collection.upsert(  # noqa: SLF001
                ids=[f"chunk-{i:05d}" for i in range(args.chunks)],
                embeddings=[[round(((i * 7 + j * 13) % 100) / 100, 4) for j in range(DIM)] for i in range(args.chunks)],
                documents=[f"fixture chunk {i}" for i in range(args.chunks)],
                metadatas=[{"source": "fixture.txt", "chunk_index": i} for i in range(args.chunks)],
            )
            await backend.teardown()

        # Bytes for the logical-path file row. The absolute-path row is left
        # dangling on purpose, so there is one passing case and one failing one.
        storage_root = Path(get_settings_service().settings.config_dir) / str(U_SUPER)
        storage_root.mkdir(parents=True, exist_ok=True)
        (storage_root / "logical.txt").write_text("fixture-bytes")

        seeded = {
            "users": 3,
            "superuser_owns_everything": str(U_SUPER),
            "custom_role_parented_on_admin": str(R_CUSTOM),
            "custom_role_child": str(R_CHILD),
            # SQLite returns a string from a text() select, Postgres a UUID object.
            # Round-tripping through UUID gives one spelling on both.
            "system_role_ids": {
                str(r[0]): str(UUID(str(r[1])))
                for r in (await s.exec(text("select name,id from authz_role where is_system"))).all()
            },
            "shares": {"user_target": str(U_BOB), "team_target": str(T_TEAM)},
            "knowledge_bases": {
                "normal": str(KB_OK),
                "empty_model_selection": str(KB_NOMODEL),
                "stubbed_backend": str(KB_STUB),
            },
            "bulk_kb_vectors": args.chunks,
            "vector_store_path": str(kb_dir) if kb_dir else None,
            "files": {
                "logical_path": f"{U_SUPER}/logical.txt",
                "absolute_path": f"/var/lib/langflow/{U_SUPER}/absolute.txt",
            },
            "paused_job": str(JOB_PAUSED),
            "policy_bundle_revisions": 2,
            "encrypted_rows": [
                "variable.value",
                "apikey.api_key",
                "user.store_api_key",
                "folder.auth_settings",
                "mcp_server.config",
                "sso_config.client_secret_encrypted",
            ],
            # Rows seeded to fail a check on purpose, so a rehearsal can tell an
            # intended negative from a real one.
            "expected_failures": {
                "knowledge_bases": {
                    str(KB_STUB): "backend_type 'astra' is not instantiable",
                    str(KB_NOMODEL): "model_selection empty, embedding model unknown",
                },
                "files": {
                    f"/var/lib/langflow/{U_SUPER}/absolute.txt": "absolute path, no bytes on disk",
                },
            },
        }

    Path(args.manifest).write_text(json.dumps(seeded, indent=2))
    print(f"seeded. manifest -> {args.manifest}")
    for k, v in seeded.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
