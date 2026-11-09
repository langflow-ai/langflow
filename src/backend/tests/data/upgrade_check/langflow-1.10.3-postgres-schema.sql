--
-- PostgreSQL database dump
--


-- Dumped from database version 18.6 (Homebrew)
-- Dumped by pg_dump version 18.6 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: access_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.access_type_enum AS ENUM (
    'PRIVATE',
    'PUBLIC'
);


--
-- Name: deployment_provider_key_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.deployment_provider_key_enum AS ENUM (
    'watsonx-orchestrate'
);


--
-- Name: deployment_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.deployment_type_enum AS ENUM (
    'agent'
);


--
-- Name: job_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.job_status_enum AS ENUM (
    'queued',
    'in_progress',
    'completed',
    'failed',
    'cancelled',
    'timed_out'
);


--
-- Name: job_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.job_type_enum AS ENUM (
    'workflow',
    'ingestion',
    'evaluation'
);


--
-- Name: spankind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.spankind AS ENUM (
    'INTERNAL',
    'CLIENT',
    'SERVER',
    'PRODUCER',
    'CONSUMER'
);


--
-- Name: spanstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.spanstatus AS ENUM (
    'unset',
    'ok',
    'error'
);


--
-- Name: spantype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.spantype AS ENUM (
    'chain',
    'llm',
    'tool',
    'retriever',
    'embedding',
    'parser',
    'agent'
);


SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: apikey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.apikey (
    name character varying,
    created_at timestamp with time zone NOT NULL,
    last_used_at timestamp without time zone,
    total_uses integer NOT NULL,
    is_active boolean NOT NULL,
    id uuid NOT NULL,
    api_key character varying NOT NULL,
    user_id uuid NOT NULL,
    api_key_hash character varying,
    expires_at timestamp with time zone
);


--
-- Name: authz_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_audit_log (
    id uuid NOT NULL,
    user_id uuid,
    action character varying NOT NULL,
    resource_type character varying,
    resource_id uuid,
    result character varying NOT NULL,
    details json,
    "timestamp" timestamp with time zone NOT NULL,
    CONSTRAINT ck_authz_audit_log_ck_authz_audit_log_result_enum CHECK (((result)::text = ANY ((ARRAY['allow'::character varying, 'deny'::character varying, 'owner_override'::character varying])::text[])))
);


--
-- Name: authz_edit_lock; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_edit_lock (
    id uuid NOT NULL,
    flow_id uuid NOT NULL,
    holder_user_id uuid NOT NULL,
    acquired_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: authz_role; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_role (
    id uuid NOT NULL,
    name character varying NOT NULL,
    description character varying,
    is_system boolean NOT NULL,
    permissions json NOT NULL,
    parent_role_id uuid,
    workspace_id uuid,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    created_by uuid
);


--
-- Name: authz_role_assignment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_role_assignment (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    domain_type character varying NOT NULL,
    domain_id uuid,
    assigned_at timestamp with time zone NOT NULL,
    assigned_by uuid
);


--
-- Name: authz_share; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_share (
    id uuid NOT NULL,
    resource_type character varying NOT NULL,
    resource_id uuid NOT NULL,
    scope character varying NOT NULL,
    target_id uuid,
    permission_level character varying NOT NULL,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_authz_share_ck_authz_share_permission_enum CHECK (((permission_level)::text = ANY ((ARRAY['read'::character varying, 'write'::character varying, 'execute'::character varying, 'admin'::character varying])::text[]))),
    CONSTRAINT ck_authz_share_ck_authz_share_scope_enum CHECK (((scope)::text = ANY ((ARRAY['private'::character varying, 'team'::character varying, 'user'::character varying, 'public'::character varying])::text[]))),
    CONSTRAINT ck_authz_share_ck_authz_share_scope_target_consistency CHECK (((((scope)::text = ANY ((ARRAY['team'::character varying, 'user'::character varying])::text[])) AND (target_id IS NOT NULL)) OR (((scope)::text = ANY ((ARRAY['private'::character varying, 'public'::character varying])::text[])) AND (target_id IS NULL))))
);


--
-- Name: authz_team; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_team (
    id uuid NOT NULL,
    team_name character varying NOT NULL,
    adom_name character varying NOT NULL,
    description character varying,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: authz_team_member; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.authz_team_member (
    id uuid NOT NULL,
    team_id uuid NOT NULL,
    user_id uuid NOT NULL,
    source character varying NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: casbin_rule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.casbin_rule (
    id integer NOT NULL,
    ptype character varying(255) NOT NULL,
    v0 character varying(255),
    v1 character varying(255),
    v2 character varying(255),
    v3 character varying(255),
    v4 character varying(255),
    v5 character varying(255)
);


--
-- Name: casbin_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.casbin_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: casbin_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.casbin_rule_id_seq OWNED BY public.casbin_rule.id;


--
-- Name: deployment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deployment (
    id uuid NOT NULL,
    resource_key character varying NOT NULL,
    user_id uuid NOT NULL,
    project_id uuid NOT NULL,
    deployment_provider_account_id uuid NOT NULL,
    display_name character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    description text,
    deployment_type public.deployment_type_enum,
    workspace_id uuid
);


--
-- Name: deployment_provider_account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deployment_provider_account (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    provider_tenant_id character varying,
    provider_url character varying NOT NULL,
    api_key character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    provider_key public.deployment_provider_key_enum CONSTRAINT deployment_provider_account_provider_key_v2_not_null NOT NULL,
    name character varying NOT NULL
);


--
-- Name: file; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.file (
    id uuid CONSTRAINT _alembic_tmp_file_id_not_null NOT NULL,
    user_id uuid CONSTRAINT _alembic_tmp_file_user_id_not_null NOT NULL,
    name character varying CONSTRAINT _alembic_tmp_file_name_not_null NOT NULL,
    path character varying CONSTRAINT _alembic_tmp_file_path_not_null NOT NULL,
    size integer CONSTRAINT _alembic_tmp_file_size_not_null NOT NULL,
    provider character varying,
    created_at timestamp without time zone CONSTRAINT _alembic_tmp_file_created_at_not_null NOT NULL,
    updated_at timestamp without time zone CONSTRAINT _alembic_tmp_file_updated_at_not_null NOT NULL
);


--
-- Name: flow; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flow (
    data json,
    name character varying NOT NULL,
    description text,
    id uuid NOT NULL,
    user_id uuid,
    is_component boolean,
    updated_at timestamp without time zone,
    icon character varying,
    icon_bg_color character varying,
    folder_id uuid,
    endpoint_name character varying,
    webhook boolean,
    gradient character varying,
    tags json,
    locked boolean,
    fs_path character varying,
    access_type public.access_type_enum DEFAULT 'PRIVATE'::public.access_type_enum NOT NULL,
    mcp_enabled boolean,
    action_name character varying,
    action_description text,
    workspace_id uuid
);


--
-- Name: flow_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flow_version (
    id uuid NOT NULL,
    flow_id uuid NOT NULL,
    user_id uuid,
    data json,
    version_number integer NOT NULL,
    description character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_flow_version_check_version_number_positive CHECK ((version_number >= 1))
);


--
-- Name: flow_version_deployment_attachment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flow_version_deployment_attachment (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    flow_version_id uuid NOT NULL,
    deployment_id uuid NOT NULL,
    provider_snapshot_id character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: folder; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folder (
    name character varying NOT NULL,
    description text,
    id uuid NOT NULL,
    parent_id uuid,
    user_id uuid,
    auth_settings json,
    workspace_id uuid
);


--
-- Name: ingestion_run; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingestion_run (
    id uuid NOT NULL,
    job_id uuid,
    kb_name character varying NOT NULL,
    kb_id uuid,
    user_id uuid,
    source_type character varying NOT NULL,
    source_config jsonb NOT NULL,
    status character varying DEFAULT 'pending'::character varying NOT NULL,
    error_message character varying,
    total_items integer DEFAULT 0 NOT NULL,
    succeeded integer DEFAULT 0 NOT NULL,
    failed integer DEFAULT 0 NOT NULL,
    skipped integer DEFAULT 0 NOT NULL,
    total_bytes bigint DEFAULT '0'::bigint NOT NULL,
    chunks_created integer DEFAULT 0 NOT NULL,
    items jsonb NOT NULL,
    user_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    CONSTRAINT ck_ingestion_run_ck_ingestion_run_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'succeeded'::character varying, 'partial'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: job; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job (
    job_id uuid NOT NULL,
    flow_id uuid NOT NULL,
    status public.job_status_enum NOT NULL,
    created_timestamp timestamp with time zone NOT NULL,
    finished_timestamp timestamp with time zone,
    type public.job_type_enum,
    user_id uuid,
    asset_id uuid,
    asset_type character varying,
    dedupe_key character varying,
    job_metadata jsonb
);


--
-- Name: knowledge_base; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.knowledge_base (
    id uuid NOT NULL,
    name character varying NOT NULL,
    user_id uuid NOT NULL,
    model_selection jsonb NOT NULL,
    chunk_size integer DEFAULT 1000 NOT NULL,
    chunk_overlap integer DEFAULT 200 NOT NULL,
    separator character varying,
    column_config jsonb NOT NULL,
    backend_type character varying DEFAULT 'chroma'::character varying NOT NULL,
    backend_config jsonb NOT NULL,
    chunks integer DEFAULT 0 NOT NULL,
    words integer DEFAULT 0 NOT NULL,
    characters integer DEFAULT 0 NOT NULL,
    size_bytes bigint DEFAULT '0'::bigint NOT NULL,
    source_types jsonb NOT NULL,
    status character varying DEFAULT 'ready'::character varying NOT NULL,
    failure_reason character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_knowledge_base_ck_knowledge_base_status CHECK (((status)::text = ANY ((ARRAY['creating'::character varying, 'ready'::character varying, 'ingesting'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: memory_base; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_base (
    id uuid NOT NULL,
    name character varying NOT NULL,
    flow_id uuid NOT NULL,
    user_id uuid NOT NULL,
    threshold integer DEFAULT 50 NOT NULL,
    auto_capture boolean DEFAULT true NOT NULL,
    embedding_model character varying DEFAULT ''::character varying NOT NULL,
    preprocessing boolean DEFAULT false NOT NULL,
    preproc_model character varying,
    preproc_instructions character varying,
    kb_name character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    preproc_kill_phrase character varying
);


--
-- Name: memory_base_preprocessing_output; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_base_preprocessing_output (
    id uuid NOT NULL,
    memory_base_id uuid NOT NULL,
    session_id character varying NOT NULL,
    job_id uuid,
    status character varying NOT NULL,
    output_text text,
    source_message_ids json NOT NULL,
    model_used character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: memory_base_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_base_session (
    id uuid NOT NULL,
    memory_base_id uuid NOT NULL,
    session_id character varying NOT NULL,
    cursor_id uuid,
    total_processed integer DEFAULT 0 NOT NULL,
    last_sync_at timestamp with time zone
);


--
-- Name: memory_base_workflow_run; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_base_workflow_run (
    id uuid NOT NULL,
    memory_base_id uuid NOT NULL,
    session_id character varying NOT NULL,
    workflow_job_id uuid,
    ingestion_job_id uuid,
    recorded_at timestamp with time zone NOT NULL
);


--
-- Name: message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message (
    "timestamp" timestamp without time zone CONSTRAINT temp_message_timestamp_not_null NOT NULL,
    sender character varying CONSTRAINT temp_message_sender_not_null NOT NULL,
    sender_name character varying CONSTRAINT temp_message_sender_name_not_null NOT NULL,
    session_id character varying CONSTRAINT temp_message_session_id_not_null NOT NULL,
    text text,
    id uuid CONSTRAINT temp_message_id_not_null NOT NULL,
    flow_id uuid,
    files json,
    error boolean DEFAULT false CONSTRAINT temp_message_error_not_null NOT NULL,
    edit boolean DEFAULT false CONSTRAINT temp_message_edit_not_null NOT NULL,
    properties json,
    category text,
    content_blocks json,
    context_id character varying,
    session_metadata json,
    run_id uuid,
    is_output boolean DEFAULT false NOT NULL,
    user_id uuid
);


--
-- Name: message_ingestion_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_ingestion_record (
    id uuid NOT NULL,
    message_id uuid NOT NULL,
    memory_base_id uuid NOT NULL,
    job_id uuid,
    session_id character varying NOT NULL,
    ingested_at timestamp with time zone NOT NULL
);


--
-- Name: span; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.span (
    name character varying NOT NULL,
    span_type public.spantype NOT NULL,
    status public.spanstatus NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    latency_ms integer NOT NULL,
    inputs json,
    outputs json,
    error text,
    span_kind public.spankind NOT NULL,
    attributes json,
    id uuid NOT NULL,
    trace_id uuid NOT NULL,
    parent_span_id uuid
);


--
-- Name: sso_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sso_config (
    id uuid NOT NULL,
    provider character varying NOT NULL,
    provider_name character varying NOT NULL,
    enabled boolean NOT NULL,
    enforce_sso boolean NOT NULL,
    client_id character varying,
    client_secret_encrypted character varying,
    discovery_url character varying,
    redirect_uri character varying,
    scopes character varying,
    email_claim character varying NOT NULL,
    username_claim character varying NOT NULL,
    user_id_claim character varying NOT NULL,
    token_endpoint character varying,
    authorization_endpoint character varying,
    jwks_uri character varying,
    issuer character varying,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    created_by uuid
);


--
-- Name: sso_user_profile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sso_user_profile (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    sso_provider character varying NOT NULL,
    sso_user_id character varying NOT NULL,
    email character varying,
    sso_last_login_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: trace; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trace (
    name character varying NOT NULL,
    status public.spanstatus NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    total_latency_ms integer NOT NULL,
    total_tokens integer NOT NULL,
    flow_id uuid NOT NULL,
    session_id character varying,
    id uuid NOT NULL
);


--
-- Name: transaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction (
    "timestamp" timestamp without time zone CONSTRAINT temp_transaction_timestamp_not_null NOT NULL,
    vertex_id character varying CONSTRAINT temp_transaction_vertex_id_not_null NOT NULL,
    target_id character varying,
    inputs json,
    outputs json,
    status character varying CONSTRAINT temp_transaction_status_not_null NOT NULL,
    id uuid CONSTRAINT temp_transaction_id_not_null NOT NULL,
    flow_id uuid CONSTRAINT temp_transaction_flow_id_not_null NOT NULL,
    error character varying
);


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id uuid NOT NULL,
    username character varying NOT NULL,
    password character varying NOT NULL,
    is_active boolean NOT NULL,
    is_superuser boolean NOT NULL,
    create_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    last_login_at timestamp without time zone,
    profile_image character varying,
    store_api_key character varying,
    optins json
);


--
-- Name: variable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.variable (
    name character varying NOT NULL,
    value character varying NOT NULL,
    type character varying,
    id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    user_id uuid NOT NULL,
    default_fields json
);


--
-- Name: vertex_build; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vertex_build (
    "timestamp" timestamp without time zone CONSTRAINT temp_vertex_build_timestamp_not_null NOT NULL,
    id character varying CONSTRAINT temp_vertex_build_id_not_null NOT NULL,
    data json,
    artifacts json,
    params text,
    build_id uuid CONSTRAINT temp_vertex_build_build_id_not_null NOT NULL,
    flow_id uuid CONSTRAINT temp_vertex_build_flow_id_not_null NOT NULL,
    valid boolean CONSTRAINT temp_vertex_build_valid_not_null NOT NULL,
    job_id uuid
);


--
-- Name: casbin_rule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.casbin_rule ALTER COLUMN id SET DEFAULT nextval('public.casbin_rule_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: file file_name_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file
    ADD CONSTRAINT file_name_user_id_key UNIQUE (name, user_id);


--
-- Name: apikey pk_apikey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apikey
    ADD CONSTRAINT pk_apikey PRIMARY KEY (id);


--
-- Name: authz_audit_log pk_authz_audit_log; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_audit_log
    ADD CONSTRAINT pk_authz_audit_log PRIMARY KEY (id);


--
-- Name: authz_edit_lock pk_authz_edit_lock; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_edit_lock
    ADD CONSTRAINT pk_authz_edit_lock PRIMARY KEY (id);


--
-- Name: authz_role pk_authz_role; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role
    ADD CONSTRAINT pk_authz_role PRIMARY KEY (id);


--
-- Name: authz_role_assignment pk_authz_role_assignment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role_assignment
    ADD CONSTRAINT pk_authz_role_assignment PRIMARY KEY (id);


--
-- Name: authz_share pk_authz_share; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_share
    ADD CONSTRAINT pk_authz_share PRIMARY KEY (id);


--
-- Name: authz_team pk_authz_team; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_team
    ADD CONSTRAINT pk_authz_team PRIMARY KEY (id);


--
-- Name: authz_team_member pk_authz_team_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_team_member
    ADD CONSTRAINT pk_authz_team_member PRIMARY KEY (id);


--
-- Name: casbin_rule pk_casbin_rule; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.casbin_rule
    ADD CONSTRAINT pk_casbin_rule PRIMARY KEY (id);


--
-- Name: deployment pk_deployment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment
    ADD CONSTRAINT pk_deployment PRIMARY KEY (id);


--
-- Name: deployment_provider_account pk_deployment_provider_account; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment_provider_account
    ADD CONSTRAINT pk_deployment_provider_account PRIMARY KEY (id);


--
-- Name: file pk_file; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file
    ADD CONSTRAINT pk_file PRIMARY KEY (id);


--
-- Name: flow pk_flow; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT pk_flow PRIMARY KEY (id);


--
-- Name: flow_version pk_flow_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version
    ADD CONSTRAINT pk_flow_version PRIMARY KEY (id);


--
-- Name: flow_version_deployment_attachment pk_flow_version_deployment_attachment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version_deployment_attachment
    ADD CONSTRAINT pk_flow_version_deployment_attachment PRIMARY KEY (id);


--
-- Name: folder pk_folder; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT pk_folder PRIMARY KEY (id);


--
-- Name: ingestion_run pk_ingestion_run; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingestion_run
    ADD CONSTRAINT pk_ingestion_run PRIMARY KEY (id);


--
-- Name: job pk_job; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT pk_job PRIMARY KEY (job_id);


--
-- Name: knowledge_base pk_knowledge_base; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT pk_knowledge_base PRIMARY KEY (id);


--
-- Name: memory_base pk_memory_base; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base
    ADD CONSTRAINT pk_memory_base PRIMARY KEY (id);


--
-- Name: memory_base_preprocessing_output pk_memory_base_preprocessing_output; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_preprocessing_output
    ADD CONSTRAINT pk_memory_base_preprocessing_output PRIMARY KEY (id);


--
-- Name: memory_base_session pk_memory_base_session; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_session
    ADD CONSTRAINT pk_memory_base_session PRIMARY KEY (id);


--
-- Name: memory_base_workflow_run pk_memory_base_workflow_run; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_workflow_run
    ADD CONSTRAINT pk_memory_base_workflow_run PRIMARY KEY (id);


--
-- Name: message_ingestion_record pk_message_ingestion_record; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_ingestion_record
    ADD CONSTRAINT pk_message_ingestion_record PRIMARY KEY (id);


--
-- Name: span pk_span; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.span
    ADD CONSTRAINT pk_span PRIMARY KEY (id);


--
-- Name: sso_config pk_sso_config; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_config
    ADD CONSTRAINT pk_sso_config PRIMARY KEY (id);


--
-- Name: sso_user_profile pk_sso_user_profile; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_user_profile
    ADD CONSTRAINT pk_sso_user_profile PRIMARY KEY (id);


--
-- Name: message pk_temp_message; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT pk_temp_message PRIMARY KEY (id);


--
-- Name: transaction pk_temp_transaction; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction
    ADD CONSTRAINT pk_temp_transaction PRIMARY KEY (id);


--
-- Name: vertex_build pk_temp_vertex_build; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vertex_build
    ADD CONSTRAINT pk_temp_vertex_build PRIMARY KEY (build_id);


--
-- Name: trace pk_trace; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trace
    ADD CONSTRAINT pk_trace PRIMARY KEY (id);


--
-- Name: user pk_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT pk_user PRIMARY KEY (id);


--
-- Name: variable pk_variable; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variable
    ADD CONSTRAINT pk_variable PRIMARY KEY (id);


--
-- Name: flow unique_flow_endpoint_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT unique_flow_endpoint_name UNIQUE (user_id, endpoint_name);


--
-- Name: flow unique_flow_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT unique_flow_name UNIQUE (user_id, name);


--
-- Name: flow_version unique_flow_version_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version
    ADD CONSTRAINT unique_flow_version_number UNIQUE (flow_id, version_number);


--
-- Name: folder unique_folder_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT unique_folder_name UNIQUE (user_id, name);


--
-- Name: apikey uq_apikey_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apikey
    ADD CONSTRAINT uq_apikey_id UNIQUE (id);


--
-- Name: authz_team_member uq_authz_team_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_team_member
    ADD CONSTRAINT uq_authz_team_member UNIQUE (team_id, user_id);


--
-- Name: deployment_provider_account uq_deployment_provider_account_provider_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment_provider_account
    ADD CONSTRAINT uq_deployment_provider_account_provider_name UNIQUE (user_id, provider_key, name);


--
-- Name: deployment_provider_account uq_deployment_provider_account_user_url_tenant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment_provider_account
    ADD CONSTRAINT uq_deployment_provider_account_user_url_tenant UNIQUE (user_id, provider_url, provider_tenant_id);


--
-- Name: deployment uq_deployment_resource_key_in_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment
    ADD CONSTRAINT uq_deployment_resource_key_in_provider UNIQUE (deployment_provider_account_id, resource_key);


--
-- Name: flow uq_flow_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT uq_flow_id UNIQUE (id);


--
-- Name: flow_version_deployment_attachment uq_flow_version_deployment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version_deployment_attachment
    ADD CONSTRAINT uq_flow_version_deployment UNIQUE (flow_version_id, deployment_id);


--
-- Name: knowledge_base uq_knowledge_base_user_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT uq_knowledge_base_user_name UNIQUE (user_id, name);


--
-- Name: memory_base_workflow_run uq_mbwr_mb_session_wf_job; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_workflow_run
    ADD CONSTRAINT uq_mbwr_mb_session_wf_job UNIQUE (memory_base_id, session_id, workflow_job_id);


--
-- Name: memory_base_session uq_memory_base_session; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_session
    ADD CONSTRAINT uq_memory_base_session UNIQUE (memory_base_id, session_id);


--
-- Name: memory_base uq_memory_base_user_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base
    ADD CONSTRAINT uq_memory_base_user_name UNIQUE (user_id, name);


--
-- Name: message_ingestion_record uq_mir_message_session_mb; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_ingestion_record
    ADD CONSTRAINT uq_mir_message_session_mb UNIQUE (message_id, session_id, memory_base_id);


--
-- Name: user uq_user_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT uq_user_id UNIQUE (id);


--
-- Name: ix_apikey_api_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_apikey_api_key ON public.apikey USING btree (api_key);


--
-- Name: ix_apikey_api_key_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apikey_api_key_hash ON public.apikey USING btree (api_key_hash);


--
-- Name: ix_apikey_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apikey_name ON public.apikey USING btree (name);


--
-- Name: ix_apikey_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_apikey_user_id ON public.apikey USING btree (user_id);


--
-- Name: ix_authz_audit_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_audit_log_action ON public.authz_audit_log USING btree (action);


--
-- Name: ix_authz_audit_log_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_audit_log_resource ON public.authz_audit_log USING btree (resource_type, resource_id);


--
-- Name: ix_authz_audit_log_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_audit_log_timestamp ON public.authz_audit_log USING btree ("timestamp");


--
-- Name: ix_authz_audit_log_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_audit_log_user_id ON public.authz_audit_log USING btree (user_id);


--
-- Name: ix_authz_audit_log_user_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_audit_log_user_timestamp ON public.authz_audit_log USING btree (user_id, "timestamp");


--
-- Name: ix_authz_edit_lock_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_edit_lock_expires_at ON public.authz_edit_lock USING btree (expires_at);


--
-- Name: ix_authz_edit_lock_flow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_authz_edit_lock_flow_id ON public.authz_edit_lock USING btree (flow_id);


--
-- Name: ix_authz_role_assignment_domain_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_role_assignment_domain_id ON public.authz_role_assignment USING btree (domain_id);


--
-- Name: ix_authz_role_assignment_role_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_role_assignment_role_id ON public.authz_role_assignment USING btree (role_id);


--
-- Name: ix_authz_role_assignment_user_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_role_assignment_user_domain ON public.authz_role_assignment USING btree (user_id, domain_type, domain_id);


--
-- Name: ix_authz_role_assignment_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_role_assignment_user_id ON public.authz_role_assignment USING btree (user_id);


--
-- Name: ix_authz_role_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_authz_role_name ON public.authz_role USING btree (name);


--
-- Name: ix_authz_role_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_role_workspace_id ON public.authz_role USING btree (workspace_id);


--
-- Name: ix_authz_share_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_share_resource ON public.authz_share USING btree (resource_type, resource_id);


--
-- Name: ix_authz_share_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_share_resource_id ON public.authz_share USING btree (resource_id);


--
-- Name: ix_authz_share_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_share_resource_type ON public.authz_share USING btree (resource_type);


--
-- Name: ix_authz_share_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_share_scope ON public.authz_share USING btree (scope);


--
-- Name: ix_authz_share_target_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_share_target_id ON public.authz_share USING btree (target_id);


--
-- Name: ix_authz_team_adom_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_authz_team_adom_name ON public.authz_team USING btree (adom_name);


--
-- Name: ix_authz_team_member_team_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_team_member_team_id ON public.authz_team_member USING btree (team_id);


--
-- Name: ix_authz_team_member_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_team_member_user_id ON public.authz_team_member USING btree (user_id);


--
-- Name: ix_authz_team_team_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_authz_team_team_name ON public.authz_team USING btree (team_name);


--
-- Name: ix_casbin_rule_ptype; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_casbin_rule_ptype ON public.casbin_rule USING btree (ptype);


--
-- Name: ix_deployment_deployment_provider_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_deployment_provider_account_id ON public.deployment USING btree (deployment_provider_account_id);


--
-- Name: ix_deployment_deployment_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_deployment_type ON public.deployment USING btree (deployment_type);


--
-- Name: ix_deployment_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_project_id ON public.deployment USING btree (project_id);


--
-- Name: ix_deployment_provider_account_provider_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_provider_account_provider_key ON public.deployment_provider_account USING btree (provider_key);


--
-- Name: ix_deployment_provider_account_provider_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_provider_account_provider_tenant_id ON public.deployment_provider_account USING btree (provider_tenant_id);


--
-- Name: ix_deployment_provider_account_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_provider_account_user_id ON public.deployment_provider_account USING btree (user_id);


--
-- Name: ix_deployment_resource_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_resource_key ON public.deployment USING btree (resource_key);


--
-- Name: ix_deployment_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_user_id ON public.deployment USING btree (user_id);


--
-- Name: ix_deployment_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deployment_workspace_id ON public.deployment USING btree (workspace_id);


--
-- Name: ix_flow_description; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_description ON public.flow USING btree (description);


--
-- Name: ix_flow_endpoint_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_endpoint_name ON public.flow USING btree (endpoint_name);


--
-- Name: ix_flow_folder_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_folder_id ON public.flow USING btree (folder_id);


--
-- Name: ix_flow_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_name ON public.flow USING btree (name);


--
-- Name: ix_flow_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_user_id ON public.flow USING btree (user_id);


--
-- Name: ix_flow_version_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_created_at ON public.flow_version USING btree (created_at);


--
-- Name: ix_flow_version_deployment_attachment_deployment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_deployment_attachment_deployment_id ON public.flow_version_deployment_attachment USING btree (deployment_id);


--
-- Name: ix_flow_version_deployment_attachment_flow_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_deployment_attachment_flow_version_id ON public.flow_version_deployment_attachment USING btree (flow_version_id);


--
-- Name: ix_flow_version_deployment_attachment_provider_snapshot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_deployment_attachment_provider_snapshot_id ON public.flow_version_deployment_attachment USING btree (provider_snapshot_id);


--
-- Name: ix_flow_version_deployment_attachment_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_deployment_attachment_user_id ON public.flow_version_deployment_attachment USING btree (user_id);


--
-- Name: ix_flow_version_flow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_flow_id ON public.flow_version USING btree (flow_id);


--
-- Name: ix_flow_version_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_version_user_id ON public.flow_version USING btree (user_id);


--
-- Name: ix_flow_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flow_workspace_id ON public.flow USING btree (workspace_id);


--
-- Name: ix_folder_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folder_name ON public.folder USING btree (name);


--
-- Name: ix_folder_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_folder_workspace_id ON public.folder USING btree (workspace_id);


--
-- Name: ix_ingestion_run_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_job_id ON public.ingestion_run USING btree (job_id);


--
-- Name: ix_ingestion_run_kb_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_kb_id ON public.ingestion_run USING btree (kb_id);


--
-- Name: ix_ingestion_run_kb_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_kb_name ON public.ingestion_run USING btree (kb_name);


--
-- Name: ix_ingestion_run_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_source_type ON public.ingestion_run USING btree (source_type);


--
-- Name: ix_ingestion_run_started_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_started_at ON public.ingestion_run USING btree (started_at);


--
-- Name: ix_ingestion_run_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_status ON public.ingestion_run USING btree (status);


--
-- Name: ix_ingestion_run_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingestion_run_user_id ON public.ingestion_run USING btree (user_id);


--
-- Name: ix_job_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_asset_id ON public.job USING btree (asset_id);


--
-- Name: ix_job_dedupe_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_dedupe_key ON public.job USING btree (dedupe_key);


--
-- Name: ix_job_flow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_flow_id ON public.job USING btree (flow_id);


--
-- Name: ix_job_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_job_id ON public.job USING btree (job_id);


--
-- Name: ix_job_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_type ON public.job USING btree (type);


--
-- Name: ix_job_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_user_id ON public.job USING btree (user_id);


--
-- Name: ix_knowledge_base_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_knowledge_base_name ON public.knowledge_base USING btree (name);


--
-- Name: ix_knowledge_base_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_knowledge_base_status ON public.knowledge_base USING btree (status);


--
-- Name: ix_knowledge_base_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_knowledge_base_user_id ON public.knowledge_base USING btree (user_id);


--
-- Name: ix_mbpo_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mbpo_job_id ON public.memory_base_preprocessing_output USING btree (job_id);


--
-- Name: ix_mbpo_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mbpo_listing ON public.memory_base_preprocessing_output USING btree (memory_base_id, session_id, created_at);


--
-- Name: ix_mbpo_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mbpo_pending ON public.memory_base_preprocessing_output USING btree (memory_base_id, session_id, status, created_at);


--
-- Name: ix_mbwr_ingestion_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mbwr_ingestion_job_id ON public.memory_base_workflow_run USING btree (ingestion_job_id);


--
-- Name: ix_mbwr_mb_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mbwr_mb_session ON public.memory_base_workflow_run USING btree (memory_base_id, session_id);


--
-- Name: ix_memory_base_flow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memory_base_flow_id ON public.memory_base USING btree (flow_id);


--
-- Name: ix_memory_base_session_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memory_base_session_lookup ON public.memory_base_session USING btree (memory_base_id, session_id);


--
-- Name: ix_memory_base_session_memory_base_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memory_base_session_memory_base_id ON public.memory_base_session USING btree (memory_base_id);


--
-- Name: ix_memory_base_session_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memory_base_session_session_id ON public.memory_base_session USING btree (session_id);


--
-- Name: ix_memory_base_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memory_base_user_id ON public.memory_base USING btree (user_id);


--
-- Name: ix_message_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_run_id ON public.message USING btree (run_id);


--
-- Name: ix_message_session_metadata_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_session_metadata_tenant ON public.message USING btree (((session_metadata ->> 'tenant_id'::text)));


--
-- Name: ix_message_session_metadata_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_session_metadata_user ON public.message USING btree (((session_metadata ->> 'user_id'::text)));


--
-- Name: ix_message_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_user_id ON public.message USING btree (user_id);


--
-- Name: ix_mir_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mir_job_id ON public.message_ingestion_record USING btree (job_id);


--
-- Name: ix_mir_memory_base_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mir_memory_base_session ON public.message_ingestion_record USING btree (memory_base_id, session_id);


--
-- Name: ix_mir_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mir_message_id ON public.message_ingestion_record USING btree (message_id);


--
-- Name: ix_span_parent_span_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_span_parent_span_id ON public.span USING btree (parent_span_id);


--
-- Name: ix_span_trace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_span_trace_id ON public.span USING btree (trace_id);


--
-- Name: ix_sso_user_profile_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sso_user_profile_email ON public.sso_user_profile USING btree (email);


--
-- Name: ix_sso_user_profile_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_sso_user_profile_user_id ON public.sso_user_profile USING btree (user_id);


--
-- Name: ix_trace_flow_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trace_flow_id ON public.trace USING btree (flow_id);


--
-- Name: ix_trace_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trace_session_id ON public.trace USING btree (session_id);


--
-- Name: ix_user_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_username ON public."user" USING btree (username);


--
-- Name: ix_vertex_build_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vertex_build_job_id ON public.vertex_build USING btree (job_id);


--
-- Name: uq_authz_role_assignment_scoped; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_authz_role_assignment_scoped ON public.authz_role_assignment USING btree (user_id, role_id, domain_type, domain_id) WHERE (domain_id IS NOT NULL);


--
-- Name: uq_authz_role_assignment_unscoped; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_authz_role_assignment_unscoped ON public.authz_role_assignment USING btree (user_id, role_id, domain_type) WHERE (domain_id IS NULL);


--
-- Name: uq_authz_share_targeted; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_authz_share_targeted ON public.authz_share USING btree (resource_type, resource_id, scope, target_id) WHERE (target_id IS NOT NULL);


--
-- Name: uq_authz_share_untargeted; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_authz_share_untargeted ON public.authz_share USING btree (resource_type, resource_id, scope) WHERE (target_id IS NULL);


--
-- Name: uq_sso_user_profile_provider_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_sso_user_profile_provider_user ON public.sso_user_profile USING btree (sso_provider, sso_user_id);


--
-- Name: apikey fk_apikey_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.apikey
    ADD CONSTRAINT fk_apikey_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: authz_audit_log fk_authz_audit_log_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_audit_log
    ADD CONSTRAINT fk_authz_audit_log_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: authz_edit_lock fk_authz_edit_lock_flow_id_flow; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_edit_lock
    ADD CONSTRAINT fk_authz_edit_lock_flow_id_flow FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;


--
-- Name: authz_edit_lock fk_authz_edit_lock_holder_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_edit_lock
    ADD CONSTRAINT fk_authz_edit_lock_holder_user_id_user FOREIGN KEY (holder_user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: authz_role_assignment fk_authz_role_assignment_assigned_by_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role_assignment
    ADD CONSTRAINT fk_authz_role_assignment_assigned_by_user FOREIGN KEY (assigned_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: authz_role_assignment fk_authz_role_assignment_role_id_authz_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role_assignment
    ADD CONSTRAINT fk_authz_role_assignment_role_id_authz_role FOREIGN KEY (role_id) REFERENCES public.authz_role(id) ON DELETE CASCADE;


--
-- Name: authz_role_assignment fk_authz_role_assignment_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role_assignment
    ADD CONSTRAINT fk_authz_role_assignment_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: authz_role fk_authz_role_created_by_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role
    ADD CONSTRAINT fk_authz_role_created_by_user FOREIGN KEY (created_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: authz_role fk_authz_role_parent_role_id_authz_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_role
    ADD CONSTRAINT fk_authz_role_parent_role_id_authz_role FOREIGN KEY (parent_role_id) REFERENCES public.authz_role(id) ON DELETE SET NULL;


--
-- Name: authz_share fk_authz_share_created_by_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_share
    ADD CONSTRAINT fk_authz_share_created_by_user FOREIGN KEY (created_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: authz_team_member fk_authz_team_member_team_id_authz_team; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_team_member
    ADD CONSTRAINT fk_authz_team_member_team_id_authz_team FOREIGN KEY (team_id) REFERENCES public.authz_team(id) ON DELETE CASCADE;


--
-- Name: authz_team_member fk_authz_team_member_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.authz_team_member
    ADD CONSTRAINT fk_authz_team_member_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: deployment fk_deployment_deployment_provider_account_id_deployment_f28c; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment
    ADD CONSTRAINT fk_deployment_deployment_provider_account_id_deployment_f28c FOREIGN KEY (deployment_provider_account_id) REFERENCES public.deployment_provider_account(id) ON DELETE CASCADE;


--
-- Name: deployment fk_deployment_project_id_folder; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment
    ADD CONSTRAINT fk_deployment_project_id_folder FOREIGN KEY (project_id) REFERENCES public.folder(id) ON DELETE CASCADE;


--
-- Name: deployment_provider_account fk_deployment_provider_account_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment_provider_account
    ADD CONSTRAINT fk_deployment_provider_account_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: deployment fk_deployment_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deployment
    ADD CONSTRAINT fk_deployment_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: file fk_file_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.file
    ADD CONSTRAINT fk_file_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: flow fk_flow_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT fk_flow_user_id FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: flow fk_flow_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT fk_flow_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: flow_version_deployment_attachment fk_flow_version_deployment_attachment_deployment_id_deployment; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version_deployment_attachment
    ADD CONSTRAINT fk_flow_version_deployment_attachment_deployment_id_deployment FOREIGN KEY (deployment_id) REFERENCES public.deployment(id) ON DELETE CASCADE;


--
-- Name: flow_version_deployment_attachment fk_flow_version_deployment_attachment_flow_version_id_f_828f; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version_deployment_attachment
    ADD CONSTRAINT fk_flow_version_deployment_attachment_flow_version_id_f_828f FOREIGN KEY (flow_version_id) REFERENCES public.flow_version(id) ON DELETE CASCADE;


--
-- Name: flow_version_deployment_attachment fk_flow_version_deployment_attachment_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version_deployment_attachment
    ADD CONSTRAINT fk_flow_version_deployment_attachment_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: flow_version fk_flow_version_flow_id_flow; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version
    ADD CONSTRAINT fk_flow_version_flow_id_flow FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;


--
-- Name: flow_version fk_flow_version_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow_version
    ADD CONSTRAINT fk_flow_version_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: folder fk_folder_parent_id_folder; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT fk_folder_parent_id_folder FOREIGN KEY (parent_id) REFERENCES public.folder(id);


--
-- Name: folder fk_folder_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder
    ADD CONSTRAINT fk_folder_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: ingestion_run fk_ingestion_run_kb_id_knowledge_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingestion_run
    ADD CONSTRAINT fk_ingestion_run_kb_id_knowledge_base FOREIGN KEY (kb_id) REFERENCES public.knowledge_base(id) ON DELETE SET NULL;


--
-- Name: knowledge_base fk_knowledge_base_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_base
    ADD CONSTRAINT fk_knowledge_base_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: memory_base_preprocessing_output fk_memory_base_preprocessing_output_job_id_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_preprocessing_output
    ADD CONSTRAINT fk_memory_base_preprocessing_output_job_id_job FOREIGN KEY (job_id) REFERENCES public.job(job_id) ON DELETE SET NULL;


--
-- Name: memory_base_preprocessing_output fk_memory_base_preprocessing_output_memory_base_id_memory_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_preprocessing_output
    ADD CONSTRAINT fk_memory_base_preprocessing_output_memory_base_id_memory_base FOREIGN KEY (memory_base_id) REFERENCES public.memory_base(id) ON DELETE CASCADE;


--
-- Name: memory_base_session fk_memory_base_session_memory_base_id_memory_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_session
    ADD CONSTRAINT fk_memory_base_session_memory_base_id_memory_base FOREIGN KEY (memory_base_id) REFERENCES public.memory_base(id) ON DELETE CASCADE;


--
-- Name: memory_base_workflow_run fk_memory_base_workflow_run_ingestion_job_id_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_workflow_run
    ADD CONSTRAINT fk_memory_base_workflow_run_ingestion_job_id_job FOREIGN KEY (ingestion_job_id) REFERENCES public.job(job_id) ON DELETE SET NULL;


--
-- Name: memory_base_workflow_run fk_memory_base_workflow_run_memory_base_id_memory_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_workflow_run
    ADD CONSTRAINT fk_memory_base_workflow_run_memory_base_id_memory_base FOREIGN KEY (memory_base_id) REFERENCES public.memory_base(id) ON DELETE CASCADE;


--
-- Name: memory_base_workflow_run fk_memory_base_workflow_run_workflow_job_id_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_base_workflow_run
    ADD CONSTRAINT fk_memory_base_workflow_run_workflow_job_id_job FOREIGN KEY (workflow_job_id) REFERENCES public.job(job_id) ON DELETE SET NULL;


--
-- Name: message_ingestion_record fk_message_ingestion_record_job_id_job; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_ingestion_record
    ADD CONSTRAINT fk_message_ingestion_record_job_id_job FOREIGN KEY (job_id) REFERENCES public.job(job_id) ON DELETE SET NULL;


--
-- Name: message_ingestion_record fk_message_ingestion_record_memory_base_id_memory_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_ingestion_record
    ADD CONSTRAINT fk_message_ingestion_record_memory_base_id_memory_base FOREIGN KEY (memory_base_id) REFERENCES public.memory_base(id) ON DELETE CASCADE;


--
-- Name: message_ingestion_record fk_message_ingestion_record_message_id_message; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_ingestion_record
    ADD CONSTRAINT fk_message_ingestion_record_message_id_message FOREIGN KEY (message_id) REFERENCES public.message(id) ON DELETE CASCADE;


--
-- Name: span fk_span_parent_span_id_span; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.span
    ADD CONSTRAINT fk_span_parent_span_id_span FOREIGN KEY (parent_span_id) REFERENCES public.span(id);


--
-- Name: span fk_span_trace_id_trace; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.span
    ADD CONSTRAINT fk_span_trace_id_trace FOREIGN KEY (trace_id) REFERENCES public.trace(id) ON DELETE CASCADE;


--
-- Name: sso_config fk_sso_config_created_by_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_config
    ADD CONSTRAINT fk_sso_config_created_by_user FOREIGN KEY (created_by) REFERENCES public."user"(id) ON DELETE SET NULL;


--
-- Name: sso_user_profile fk_sso_user_profile_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sso_user_profile
    ADD CONSTRAINT fk_sso_user_profile_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- Name: trace fk_trace_flow_id_flow; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trace
    ADD CONSTRAINT fk_trace_flow_id_flow FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;


--
-- Name: variable fk_variable_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.variable
    ADD CONSTRAINT fk_variable_user_id FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: flow flow_folder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folder(id);


--
-- Name: flow flow_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--
