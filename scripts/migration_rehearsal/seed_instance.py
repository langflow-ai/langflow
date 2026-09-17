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

DIM = 8  # vector width; the transport does not care what it is
CHROMA_UPSERT_BATCH = 5000
LOGICAL_FILE_BYTES = b"fixture-bytes"  # the logical file row's size is taken from this


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
KB_MEMORY = uid(4, "f")
MB_ONE = uid(1, "9")
JOB_PAUSED = uid(1, "8")
JOB_INGEST = uid(2, "8")
RUN_INGEST = uid(3, "8")
EMBEDDING = {"provider": "OpenAI", "name": "text-embedding-3-small"}  # the key the app reads is "name"
# MemoryBaseService names its backing knowledge base "<sanitized name>_<8 hex>".
MB_KB_NAME = f"fixture_memory_{MB_ONE.hex[:8]}"
MB_VECTORS = 2  # one per ingested message


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
    # Taken after the schema exists, so seeded rows are not older than the rows
    # alembic seeds (the system roles, policy bundle revision 1).
    now = datetime.now(timezone.utc)

    import sqlalchemy as sa
    from langflow.services.auth.utils import encrypt_api_key, get_password_hash
    from langflow.services.database.models.api_key.crud import hash_api_key
    from langflow.services.database.models.auth.sso_secret import encrypt_sso_client_secret
    from langflow.services.deps import get_settings_service, session_scope
    from sqlalchemy import bindparam, text

    enc = encrypt_api_key

    password_hash = get_password_hash("fixture-password")  # pragma: allowlist secret

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
            typed = [bindparam(k, type_=sa.Uuid()) for k, v in p.items() if isinstance(v, UUID)]
            # Same for timestamps: bound raw, SQLite stores "...+00:00", a spelling the
            # ORM never writes, and those rows read back tz-aware beside naive ones.
            typed += [bindparam(k, type_=sa.DateTime(timezone=True)) for k, v in p.items() if isinstance(v, datetime)]
            if typed:
                stmt = stmt.bindparams(*typed)
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
                # A real hash: Langflow's startup verifies the default superuser's
                # password, and a non-hash value crashes it.
                p=password_hash,
                a=True,
                s=su,
                c=now,
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
            c=now,
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
            c=now,
        )

        # Assignments on both a system role and a custom one.
        for aid, uid_, rid in ((uid(1, "7"), U_ALICE, admin_id), (uid(2, "7"), U_BOB, R_CUSTOM)):
            await ex(
                "insert into authz_role_assignment(id,user_id,role_id,domain_type,assigned_at)"
                " values (:i,:u,:r,'global',:c)",
                i=aid,
                u=uid_,
                r=rid,
                c=now,
            )
        await ex(
            "insert into authz_team(id,team_name,adom_name,is_active,created_at,updated_at)"
            " values (:i,:n,:a,:act,:c,:c)",
            i=T_TEAM,
            n="platform",
            a="default",
            act=True,
            c=now,
        )
        await ex(
            "insert into authz_team_member(id,team_id,user_id,source,created_at) values (:i,:t,:u,'manual',:c)",
            i=uid(1, "6"),
            t=T_TEAM,
            u=U_BOB,
            c=now,
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
                c=now,
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
            c=now,
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
                c=now,
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
            c=now,
        )
        await ex(
            "insert into apikey(id,name,api_key,api_key_hash,user_id,total_uses,is_active,created_at)"
            " values (:i,:n,:k,:h,:u,0,:a,:c)",
            i=uid(2, "3"),
            n="ci-key",
            k=enc("lf-fixture-apikey"),
            # The real hash, so the key authenticates: lookup is by hash, and the
            # decrypt-and-compare fallback only considers rows whose hash is null.
            h=hash_api_key("lf-fixture-apikey"),
            u=U_SUPER,
            a=True,
            c=now,
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
            c=now,
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
            c=now,
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
            s=len(LOGICAL_FILE_BYTES),
            c=now,
        )
        await ex(
            "insert into file(id,user_id,name,path,size,provider,created_at,updated_at)"
            " values (:i,:u,:n,:p,:s,null,:c,:c)",
            i=uid(2, "2"),
            u=U_SUPER,
            n="absolute.txt",
            p=f"/var/lib/langflow/{U_SUPER}/absolute.txt",
            s=12,
            c=now,
        )

        # --- knowledge bases, three awkward shapes plus a memory base's own ----
        kbs = (
            # normal: local Chroma, model recorded. The copy path.
            (KB_OK, "kb-ok", "chroma", EMBEDDING, args.chunks, []),
            # empty model_selection, with vectors that match its chunk count, so the
            # empty selection is the only thing wrong with it. Catches:
            # resolve_embedding_selection silently falling back to a default model,
            # so the row claims a model it may never have used.
            (KB_NOMODEL, "kb-no-model", "chroma", {}, 5, []),
            # a backend that parses but cannot be instantiated. Catches: BackendType
            # still carries astra/mongodb while create_backend refuses them.
            (KB_STUB, "kb-stubbed-backend", "astra", {**EMBEDDING, "name": "x"}, 0, []),
            # the memory base's backing knowledge base, in the shape MemoryBaseService writes.
            (KB_MEMORY, MB_KB_NAME, "chroma", EMBEDDING, MB_VECTORS, ["memory"]),
        )
        for kid, nm, backend, sel, chunks, source_types in kbs:
            await ex(
                "insert into knowledge_base(id,name,user_id,model_selection,chunk_size,chunk_overlap,"
                "column_config,backend_type,backend_config,chunks,words,characters,size_bytes,"
                "source_types,status,created_at,updated_at)"
                " values (:i,:n,:u,:sel,1000,200,'[]',:bt,'{}',:ch,0,0,0,:st,'ready',:c,:c)",
                i=kid,
                n=nm,
                u=U_SUPER,
                sel=json.dumps(sel),
                bt=backend,
                ch=chunks,
                st=json.dumps(source_types),
                c=now,
            )

        # An ingestion run for kb-ok. Runs now live on the job row's job_metadata,
        # linked to the knowledge base through asset_id, which is what the app reads.
        # The legacy ingestion_run row is what an older instance still holds.
        # Catches: kb_id's ON DELETE SET NULL FK, the kb_name pointer, and job_id,
        # which has no FK at all.
        run = {
            "kind": "kb_ingestion",
            "kb_name": "kb-ok",
            "kb_id": str(KB_OK),
            "source_type": "file_upload",
            "source_config": {},
            "user_metadata": {},
            "status": "succeeded",
            "error_message": None,
            "total_items": 1,
            "succeeded": 1,
            "failed": 0,
            "skipped": 0,
            "total_bytes": len(LOGICAL_FILE_BYTES),
            "chunks_created": args.chunks,
            "items": [
                {
                    "item_id": "fixture.txt",
                    "display_name": "fixture.txt",
                    "status": "succeeded",
                    "chunks_created": args.chunks,
                    "error_message": None,
                }
            ],
            "started_at": now.isoformat(),
            "ingestion_run_id": str(JOB_INGEST),
        }
        await ex(
            # An ingestion job's flow_id is its own job_id.
            "insert into job(job_id,flow_id,status,created_timestamp,finished_timestamp,type,user_id,"
            "asset_id,asset_type,job_metadata) values (:i,:i,'completed',:c,:c,'ingestion',:u,:a,"
            "'knowledge_base',:m)",
            i=JOB_INGEST,
            c=now,
            u=U_SUPER,
            a=KB_OK,
            m=json.dumps(run),
        )
        await ex(
            "insert into ingestion_run(id,job_id,kb_name,kb_id,user_id,source_type,source_config,status,"
            "total_items,succeeded,failed,skipped,total_bytes,chunks_created,items,user_metadata,"
            "started_at,finished_at) values (:i,:j,'kb-ok',:k,:u,'file_upload','{}','succeeded',1,1,0,0,"
            ":b,:ch,:it,'{}',:c,:c)",
            i=RUN_INGEST,
            j=JOB_INGEST,
            k=KB_OK,
            u=U_SUPER,
            b=len(LOGICAL_FILE_BYTES),
            ch=args.chunks,
            it=json.dumps(run["items"]),
            c=now,
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
            kb=MB_KB_NAME,
            c=now,
        )
        await ex(
            "insert into memory_base_session(id,session_id,cursor_id,total_processed,memory_base_id)"
            " values (:i,:s,:cur,2,:m)",
            i=uid(1, "1"),
            s="session-fixture",
            # The cursor sits on the last ingested message. It has no foreign key.
            cur=uid(11, "1"),
            m=MB_ONE,
        )
        for n in range(2):
            mid = uid(10 + n, "1")
            await ex(
                "insert into message(id,timestamp,sender,sender_name,session_id,flow_id,text,error,edit,is_output,"
                "category) values (:i,:t,'User','alice','session-fixture',:f,:tx,:e,:e,:e,'message')",
                i=mid,
                # Ingestion only reads non-error messages from the memory base's own flow,
                # and a NULL category fails its category != 'error' filter.
                f=FL_MAIN,
                t=now,
                tx=f"fixture message {n}",
                e=False,
            )
            await ex(
                "insert into message_ingestion_record(id,message_id,memory_base_id,session_id,ingested_at)"
                " values (:i,:m,:mb,'session-fixture',:c)",
                i=uid(20 + n, "1"),
                m=mid,
                mb=MB_ONE,
                c=now,
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
            c=now,
            u=U_SUPER,
        )
        await ex(
            "insert into job_checkpoints(id,job_id,kind,blob,created_at,updated_at) values (:i,:j,'graph',:b,:c,:c)",
            i=uid(1, "0"),
            j=JOB_PAUSED,
            b='{"resume":"state"}',
            c=now,
        )
        # These keys are string columns. Bound as UUID, SQLite stores the undashed form
        # and Postgres the dashed one, and the app looks rows up by the dashed string.
        a2a_task_id = str(uid(2, "0"))
        await ex(
            "insert into a2a_tasks(id,owner,task) values (:i,:o,:t)",
            i=a2a_task_id,
            # DurableTaskStore scopes a mounted flow's task to "<flow_id>:<principal>".
            o=f"{FL_MAIN}:{U_SUPER}",
            t='{"state":"input-required"}',
        )
        await ex(
            "insert into a2a_checkpoints(run_id,checkpoint) values (:i,:c)",
            # run_id is the A2A task id.
            i=a2a_task_id,
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
            c=now,
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
        from langflow.api.utils.kb_helpers import KBStorageHelper
        from lfx.base.knowledge_bases.backends import ChromaLocalBackend

        kb_root = KBStorageHelper.get_root_path() / "langflow"
        # Every local Chroma row gets as many vectors as it records.
        for _, nm, backend_type, _, chunks, _ in kbs:
            if backend_type != "chroma" or not chunks:
                continue
            kb_dir = kb_root / nm
            kb_dir.mkdir(parents=True, exist_ok=True)
            # No embedding model is involved. The copy path moves opaque float
            # arrays, so deterministic values exercise it exactly as real ones do.
            backend = ChromaLocalBackend(kb_name=nm, kb_path=kb_dir)
            await backend.ensure_ready()
            # Chroma rejects a single upsert above its max batch size (5461 locally).
            for start in range(0, chunks, CHROMA_UPSERT_BATCH):
                batch = range(start, min(start + CHROMA_UPSERT_BATCH, chunks))
                backend.vector_store._collection.upsert(  # noqa: SLF001
                    ids=[f"chunk-{i:05d}" for i in batch],
                    embeddings=[[round(((i * 7 + j * 13) % 100) / 100, 4) for j in range(DIM)] for i in batch],
                    documents=[f"fixture chunk {i}" for i in batch],
                    metadatas=[{"source": "fixture.txt", "chunk_index": i} for i in batch],
                )
            await backend.teardown()

        # Bytes for the logical-path file row. The absolute-path row is left
        # dangling on purpose, so there is one passing case and one failing one.
        storage_root = Path(get_settings_service().settings.config_dir) / str(U_SUPER)
        storage_root.mkdir(parents=True, exist_ok=True)
        (storage_root / "logical.txt").write_bytes(LOGICAL_FILE_BYTES)

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
                "memory_base": str(KB_MEMORY),
            },
            "vectors": {nm: chunks for _, nm, bt, _, chunks, _ in kbs if bt == "chroma"},
            "vector_store_root": str(kb_root),
            "memory_base": {"id": str(MB_ONE), "kb_name": MB_KB_NAME},
            "kb_ingestion": {"job": str(JOB_INGEST), "legacy_ingestion_run": str(RUN_INGEST)},
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
