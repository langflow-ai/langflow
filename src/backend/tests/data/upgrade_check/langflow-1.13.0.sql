PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE a2a_checkpoints (
	run_id VARCHAR NOT NULL,
	checkpoint JSON NOT NULL,
	PRIMARY KEY (run_id)
);
CREATE TABLE a2a_tasks (
	id VARCHAR NOT NULL,
	owner VARCHAR NOT NULL,
	task JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id, owner)
);
CREATE TABLE audit_events (
	id CHAR(32) NOT NULL,
	resource_type VARCHAR(64) NOT NULL,
	resource_id CHAR(32) NOT NULL,
	resource_name VARCHAR(255),
	user_id CHAR(32),
	actor_type VARCHAR(32) NOT NULL,
	actor_id CHAR(32),
	acting_issuer VARCHAR(2048),
	acting_subject VARCHAR(512),
	action VARCHAR(128) NOT NULL,
	operation VARCHAR(64) NOT NULL,
	event_type VARCHAR(16) NOT NULL,
	result VARCHAR(16) NOT NULL,
	error_code VARCHAR(64),
	timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW') || '000') NOT NULL,
	request_id CHAR(32) NOT NULL,
	details JSON NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_audit_events_event_type_result CHECK ((event_type = 'authz' AND result IN ('allow', 'deny')) OR (event_type = 'action' AND result IN ('succeeded', 'failed'))),
	CONSTRAINT ck_audit_events_acting_pair CHECK ((acting_issuer IS NULL AND acting_subject IS NULL) OR (acting_issuer IS NOT NULL AND acting_subject IS NOT NULL))
);
CREATE TABLE authz_team (
	id CHAR(32) NOT NULL,
	team_name VARCHAR NOT NULL,
	adom_name VARCHAR NOT NULL,
	description VARCHAR,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE background_job_metric_totals (
	id INTEGER NOT NULL,
	started BIGINT DEFAULT 0 NOT NULL,
	completed BIGINT DEFAULT 0 NOT NULL,
	failed_error BIGINT DEFAULT 0 NOT NULL,
	failed_worker_lost BIGINT DEFAULT 0 NOT NULL,
	failed_input_timeout BIGINT DEFAULT 0 NOT NULL,
	timed_out BIGINT DEFAULT 0 NOT NULL,
	cancelled BIGINT DEFAULT 0 NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE casbin_rule (
	id INTEGER NOT NULL,
	ptype VARCHAR(255) NOT NULL,
	v0 VARCHAR(255),
	v1 VARCHAR(255),
	v2 VARCHAR(255),
	v3 VARCHAR(255),
	v4 VARCHAR(255),
	v5 VARCHAR(255),
	PRIMARY KEY (id)
);
CREATE TABLE data_subject_request (
	id CHAR(32) NOT NULL,
	subject_type VARCHAR(16) NOT NULL,
	subject_user_id CHAR(32) NOT NULL,
	subject_end_user_id VARCHAR(255),
	subject_label VARCHAR(255),
	scope_flow_ids JSON,
	source VARCHAR(16) NOT NULL,
	requested_by CHAR(32),
	decided_by CHAR(32),
	status VARCHAR(16) NOT NULL,
	phase VARCHAR(32),
	cursor JSON,
	pending_paths JSON,
	counts JSON,
	error JSON,
	refusal_note TEXT,
	requested_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	due_at DATETIME NOT NULL,
	decided_at DATETIME,
	finished_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT ck_dsr_subject_type CHECK (subject_type IN ('builder', 'end_user')),
	CONSTRAINT ck_dsr_status CHECK (status IN ('requested', 'approved', 'erasing', 'done', 'refused', 'withdrawn')),
	CONSTRAINT ck_dsr_source CHECK (source IN ('self', 'admin', 'api'))
);
CREATE TABLE job (
	job_id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	status VARCHAR(11) NOT NULL,
	created_timestamp DATETIME NOT NULL,
	finished_timestamp DATETIME,
	type VARCHAR(10),
	user_id CHAR(32),
	asset_id CHAR(32),
	asset_type VARCHAR,
	dedupe_key VARCHAR,
	job_metadata JSON,
	result JSON,
	error JSON,
	PRIMARY KEY (job_id)
);
CREATE TABLE job_checkpoints (
	id CHAR(32) NOT NULL,
	job_id CHAR(32) NOT NULL,
	kind VARCHAR NOT NULL,
	blob TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_job_checkpoints_job_id_kind UNIQUE (job_id, kind)
);
CREATE TABLE job_events (
	id CHAR(32) NOT NULL,
	job_id CHAR(32) NOT NULL,
	seq INTEGER NOT NULL,
	event_type VARCHAR NOT NULL,
	payload JSON,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_job_events_job_id_seq UNIQUE (job_id, seq)
);
CREATE TABLE knowledge_base_storage_migration (
	id CHAR(32) NOT NULL,
	kb_id CHAR(32) NOT NULL,
	source_backend VARCHAR NOT NULL,
	source_generation INTEGER NOT NULL,
	target_generation INTEGER NOT NULL,
	source_fingerprint VARCHAR,
	source_identity VARCHAR,
	source_version VARCHAR,
	phase VARCHAR NOT NULL,
	attempts INTEGER NOT NULL,
	error_code VARCHAR,
	coordinator VARCHAR,
	validation JSON NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE memory_base (
	name VARCHAR NOT NULL,
	flow_id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	threshold INTEGER NOT NULL,
	auto_capture BOOLEAN NOT NULL,
	embedding_model VARCHAR NOT NULL,
	preprocessing BOOLEAN NOT NULL,
	preproc_model VARCHAR,
	preproc_instructions VARCHAR,
	preproc_kill_phrase VARCHAR,
	id CHAR(32) NOT NULL,
	kb_name VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_memory_base_user_name UNIQUE (user_id, name)
);
CREATE TABLE model_provider_policy (
	id INTEGER NOT NULL,
	approved_provider_ids JSON NOT NULL,
	version INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_model_provider_policy_singleton CHECK (id = 1),
	CONSTRAINT ck_model_provider_policy_version CHECK (version >= 0)
);
INSERT INTO model_provider_policy VALUES(1,'[]',0);
CREATE TABLE policy_bundle_active (
	id INTEGER NOT NULL,
	revision INTEGER NOT NULL,
	initialized BOOLEAN DEFAULT 0 NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_policy_bundle_active_singleton CHECK (id = 1),
	CONSTRAINT ck_policy_bundle_active_revision_positive CHECK (revision >= 1)
);
INSERT INTO policy_bundle_active VALUES(1,1,0,'2026-10-27 18:14:46');
CREATE TABLE policy_bundle_revision (
	revision INTEGER NOT NULL,
	initialized BOOLEAN NOT NULL,
	approved_provider_ids JSON NOT NULL,
	blocked_component_keys JSON NOT NULL,
	blocked_template_keys JSON NOT NULL,
	blocked_model_keys JSON DEFAULT '[]',
	approved_integration_provider_ids JSON DEFAULT '[]',
	blocked_integration_action_keys JSON DEFAULT '[]',
	content_hash VARCHAR(64) NOT NULL,
	source VARCHAR(32) NOT NULL,
	created_by CHAR(32),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	reason VARCHAR(1024),
	rollback_of_revision INTEGER,
	PRIMARY KEY (revision),
	CONSTRAINT ck_policy_bundle_revision_positive CHECK (revision >= 1),
	CONSTRAINT ck_policy_bundle_revision_hash_length CHECK (length(content_hash) = 64),
	FOREIGN KEY(rollback_of_revision) REFERENCES policy_bundle_revision (revision) ON DELETE SET NULL
);
INSERT INTO policy_bundle_revision VALUES(1,0,'[]','[]','[]','[]','[]','[]','ef74cccb21593ac02fc514e669c911768e740b1135d7a91d3fb15f72837ab762','migration',NULL,'2026-10-27 18:14:46','Migrated existing provider and catalog policy',NULL);
CREATE TABLE project_replacement_operation (
	project_id CHAR(32) NOT NULL,
	operation_id CHAR(32) NOT NULL,
	request_digest VARCHAR(64) NOT NULL,
	result JSON,
	project_user_id CHAR(32),
	workspace_id CHAR(32),
	created_at DATETIME NOT NULL,
	PRIMARY KEY (project_id, operation_id)
);
CREATE TABLE sso_settings (
	id INTEGER NOT NULL,
	enforce_sso BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_sso_settings_singleton CHECK (id = 1)
);
INSERT INTO sso_settings VALUES(1,0);
CREATE TABLE trigger_cleanup (
	id CHAR(32) NOT NULL,
	trigger_id CHAR(32) NOT NULL,
	connection_id CHAR(32),
	user_id CHAR(32) NOT NULL,
	provider VARCHAR(64) NOT NULL,
	kind VARCHAR(64) NOT NULL,
	provider_subscription_id VARCHAR(255) NOT NULL,
	provider_state JSON NOT NULL,
	expires_at DATETIME,
	encrypted_credential TEXT,
	credential_expires_at DATETIME,
	available_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	attempt INTEGER DEFAULT '0' NOT NULL,
	last_error VARCHAR(128),
	PRIMARY KEY (id)
);
CREATE TABLE trigger_lease (
	name VARCHAR(64) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	heartbeat_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (name)
);
INSERT INTO trigger_lease VALUES('data_subject_eraser','dsr:42605:08694c25','2026-10-27 18:14:47.456367','2026-10-27 18:14:55.256358','2026-10-27 18:14:58.655251');
INSERT INTO trigger_lease VALUES('trigger-source-maintenance','dispatcher:42605:9a2c90ee:sources','2026-10-27 18:14:55.282106','2026-10-27 18:14:55.282106','2026-10-27 18:14:58.657381');
INSERT INTO trigger_lease VALUES('trigger_scheduler','dispatcher:42605:9a2c90ee','2026-10-27 18:14:55.281577','2026-10-27 18:14:55.281577','2026-10-27 18:15:25.281577');
INSERT INTO trigger_lease VALUES('trigger_subscription_renewal','dispatcher:42605:9a2c90ee:sources','2026-10-27 18:14:55.290002','2026-10-27 18:14:55.290002','2026-10-27 18:15:25.290002');
INSERT INTO trigger_lease VALUES('trigger_dispatcher','dispatcher:42605:9a2c90ee','2026-10-27 18:14:55.293542','2026-10-27 18:14:55.293542','2026-10-27 18:14:58.656834');
CREATE TABLE user (
	id CHAR(32) NOT NULL,
	username VARCHAR NOT NULL,
	password VARCHAR NOT NULL,
	profile_image VARCHAR,
	is_active BOOLEAN NOT NULL,
	is_superuser BOOLEAN NOT NULL,
	create_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	last_login_at DATETIME,
	retired_at DATETIME,
	store_api_key VARCHAR,
	optins JSON,
	PRIMARY KEY (id),
	UNIQUE (id)
);
INSERT INTO user VALUES('807bc5eb65aa47528d014d42975104e9','langflow','$2b$12$T9of600BsAViYWZgHRkhw.9Re1tkPFZ7KToUwVrwIPXNkNdDJzjSi',NULL,1,1,'2026-10-27 18:14:47.440327','2026-10-27 18:14:58.644846','2026-10-27 18:14:58.644158',NULL,'','{"github_starred": false, "dialog_dismissed": false, "discord_clicked": false}');
INSERT INTO user VALUES('0583c473a0a4428e863699acc6d57a9e','fixture-user','$2b$12$kolLmflqyljQMRSaawCtNe6XAhMX0kzfuZpEpAMAcf9eEdUDaplAW',NULL,0,0,'2026-10-27 18:14:58.782761','2026-10-27 18:14:58.782763',NULL,NULL,NULL,'{"github_starred": false, "dialog_dismissed": false, "discord_clicked": false}');
CREATE TABLE authz_access_exception (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	resource_type VARCHAR NOT NULL,
	resource_id CHAR(32) NOT NULL,
	created_by CHAR(32),
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_authz_access_exception_target UNIQUE (user_id, resource_type, resource_id),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(created_by) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE authz_audit_log (
	id CHAR(32) NOT NULL,
	user_id CHAR(32),
	actor_type VARCHAR,
	actor_id CHAR(32),
	action VARCHAR NOT NULL,
	resource_type VARCHAR,
	resource_id CHAR(32),
	result VARCHAR NOT NULL,
	details JSON,
	timestamp DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_authz_audit_log_result_enum CHECK (result IN ('allow', 'deny', 'owner_override', 'skip')),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE authz_role (
	id CHAR(32) NOT NULL,
	name VARCHAR NOT NULL,
	description VARCHAR,
	is_system BOOLEAN NOT NULL,
	permissions JSON NOT NULL,
	parent_role_id CHAR(32),
	workspace_id CHAR(32),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	created_by CHAR(32),
	PRIMARY KEY (id),
	FOREIGN KEY(parent_role_id) REFERENCES authz_role (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by) REFERENCES user (id) ON DELETE SET NULL
);
INSERT INTO authz_role VALUES('2c29cc0ede4b440fa0668f41056174f3','viewer','Read-only access to flows, deployments, projects, and supporting resources.',1,'["flow:read", "flow:execute", "deployment:read", "project:read", "knowledge_base:read", "variable:read", "file:read"]',NULL,NULL,'2026-10-27 18:14:46.514553','2026-10-27 18:14:46.514553',NULL);
INSERT INTO authz_role VALUES('d337eacab1774237a5c38138cd3e3675','developer','Author and execute flows; manage variables, knowledge bases, and files.',1,'["flow:read", "flow:execute", "deployment:read", "project:read", "knowledge_base:read", "variable:read", "file:read", "flow:write", "flow:create", "deployment:write", "deployment:create", "deployment:execute", "project:write", "project:create", "knowledge_base:write", "knowledge_base:create", "knowledge_base:ingest", "variable:write", "variable:create", "file:write", "file:create"]',NULL,NULL,'2026-10-27 18:14:46.514553','2026-10-27 18:14:46.514553',NULL);
INSERT INTO authz_role VALUES('16393cdf822348559c4aad7b995dbcbf','admin','Full management of resources and shares within the workspace.',1,'["flow:read", "flow:execute", "deployment:read", "project:read", "knowledge_base:read", "variable:read", "file:read", "flow:write", "flow:create", "deployment:write", "deployment:create", "deployment:execute", "project:write", "project:create", "knowledge_base:write", "knowledge_base:create", "knowledge_base:ingest", "variable:write", "variable:create", "file:write", "file:create", "flow:delete", "flow:deploy", "deployment:delete", "project:delete", "knowledge_base:delete", "variable:delete", "file:delete", "share:read", "share:create", "share:update", "share:delete"]',NULL,NULL,'2026-10-27 18:14:46.514553','2026-10-27 18:14:46.514553',NULL);
CREATE TABLE authz_share (
	id CHAR(32) NOT NULL,
	resource_type VARCHAR NOT NULL,
	resource_id CHAR(32) NOT NULL,
	scope VARCHAR NOT NULL,
	target_id CHAR(32),
	permission_level VARCHAR NOT NULL,
	created_by CHAR(32),
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_authz_share_scope_enum CHECK (scope IN ('private', 'team', 'user', 'public')),
	CONSTRAINT ck_authz_share_permission_enum CHECK (permission_level IN ('read', 'write', 'execute', 'admin')),
	CONSTRAINT ck_authz_share_scope_target_consistency CHECK ((scope IN ('team', 'user') AND target_id IS NOT NULL) OR (scope IN ('private', 'public') AND target_id IS NULL)),
	FOREIGN KEY(created_by) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE authz_team_member (
	id CHAR(32) NOT NULL,
	team_id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	source VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_authz_team_member UNIQUE (team_id, user_id),
	FOREIGN KEY(team_id) REFERENCES authz_team (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE catalog_policy_rule (
	id CHAR(32) NOT NULL,
	resource_kind VARCHAR NOT NULL,
	resource_key VARCHAR NOT NULL,
	mode VARCHAR DEFAULT 'block' NOT NULL,
	scope VARCHAR DEFAULT 'global' NOT NULL,
	domain_id CHAR(32),
	created_by CHAR(32),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_catalog_policy_rule_resource_kind CHECK (resource_kind IN ('component', 'template')),
	CONSTRAINT ck_catalog_policy_rule_mode CHECK (mode IN ('block', 'allow')),
	CONSTRAINT ck_catalog_policy_rule_scope CHECK (scope IN ('global', 'org', 'workspace')),
	CONSTRAINT ck_catalog_policy_rule_scope_domain_consistency CHECK ((scope = 'global' AND domain_id IS NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NOT NULL)),
	FOREIGN KEY(created_by) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE connection (
	provider_key VARCHAR(120) NOT NULL,
	name VARCHAR(64) NOT NULL,
	display_name VARCHAR(255) NOT NULL,
	ownership_mode VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	status_reason VARCHAR(32),
	health VARCHAR(16) NOT NULL,
	granted_scopes JSON NOT NULL,
	executing_identity JSON NOT NULL,
	allow_non_interactive BOOLEAN NOT NULL,
	id CHAR(32) NOT NULL,
	owner_id CHAR(32),
	health_checked_at DATETIME,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_connection_owner_mode CHECK ((ownership_mode = 'user' AND owner_id IS NOT NULL) OR (ownership_mode = 'instance' AND owner_id IS NULL)),
	CONSTRAINT ck_connection_status CHECK (status IN ('pending', 'ready', 'expired', 'revoked', 'error')),
	CONSTRAINT ck_connection_health CHECK (health IN ('unknown', 'healthy', 'unhealthy')),
	FOREIGN KEY(owner_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE folder (
	name VARCHAR NOT NULL,
	description TEXT,
	auth_settings JSON,
	id CHAR(32) NOT NULL,
	parent_id CHAR(32),
	user_id CHAR(32),
	workspace_id CHAR(32),
	is_personal BOOLEAN DEFAULT 0 NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT unique_folder_name UNIQUE (user_id, name),
	FOREIGN KEY(parent_id) REFERENCES folder (id),
	FOREIGN KEY(user_id) REFERENCES user (id)
);
INSERT INTO folder VALUES('Starter Project','Manage your own flows. Download and upload projects.','null','cc861ec4e0a040458afcc6b2b24dc04a',NULL,'807bc5eb65aa47528d014d42975104e9',NULL,1);
INSERT INTO folder VALUES('Starter Project','Manage your own flows. Download and upload projects.','null','50047369537941efa7705f7e9f86e996',NULL,'0583c473a0a4428e863699acc6d57a9e',NULL,1);
INSERT INTO folder VALUES('Fixture project','Upgrade check fixture','null','610039a62609486984f06f8617d255ba',NULL,'807bc5eb65aa47528d014d42975104e9',NULL,0);
CREATE TABLE knowledge_base (
	id CHAR(32) NOT NULL,
	name VARCHAR NOT NULL,
	user_id CHAR(32) NOT NULL,
	model_selection JSON NOT NULL,
	chunk_size INTEGER NOT NULL,
	chunk_overlap INTEGER NOT NULL,
	separator VARCHAR,
	column_config JSON NOT NULL,
	backend_type VARCHAR NOT NULL,
	backend_config JSON NOT NULL,
	storage_generation INTEGER NOT NULL,
	storage_state VARCHAR NOT NULL,
	active_migration_id CHAR(32),
	chunks INTEGER NOT NULL,
	words INTEGER NOT NULL,
	characters INTEGER NOT NULL,
	size_bytes BIGINT DEFAULT '0' NOT NULL,
	source_types JSON NOT NULL,
	status VARCHAR NOT NULL,
	failure_reason VARCHAR,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_knowledge_base_user_name UNIQUE (user_id, name),
	CONSTRAINT ck_knowledge_base_status CHECK (status IN ('creating', 'ready', 'ingesting', 'failed')),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE mcp_server (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	name VARCHAR NOT NULL,
	transport VARCHAR,
	config JSON,
	enabled BOOLEAN NOT NULL,
	version INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_mcp_server_name_user UNIQUE (user_id, name),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE
);
INSERT INTO mcp_server VALUES('e98d3806cff24f1ca9ad281a630358e4','807bc5eb65aa47528d014d42975104e9','lf-fixture_project','stdio','{"command": "uvx", "args": ["--with", "mcp~=1.28", "mcp-proxy", "--transport", "streamablehttp", "http://127.0.0.1:17895/api/v1/mcp/project/610039a6-2609-4869-84f0-6f8617d255ba/streamable"]}',1,1,'2026-10-27 18:14:58.980324','2026-10-27 18:14:58.980331');
CREATE TABLE memory_base_preprocessing_output (
	id CHAR(32) NOT NULL,
	memory_base_id CHAR(32) NOT NULL,
	session_id VARCHAR NOT NULL,
	job_id CHAR(32),
	status VARCHAR NOT NULL,
	output_text TEXT,
	source_message_ids JSON NOT NULL,
	model_used VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(memory_base_id) REFERENCES memory_base (id) ON DELETE CASCADE,
	FOREIGN KEY(job_id) REFERENCES job (job_id) ON DELETE SET NULL
);
CREATE TABLE memory_base_session (
	session_id VARCHAR NOT NULL,
	cursor_id CHAR(32),
	total_processed INTEGER NOT NULL,
	last_sync_at DATETIME,
	id CHAR(32) NOT NULL,
	purge_pending BOOLEAN DEFAULT 0 NOT NULL,
	memory_base_id CHAR(32) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_memory_base_session UNIQUE (memory_base_id, session_id),
	FOREIGN KEY(memory_base_id) REFERENCES memory_base (id) ON DELETE CASCADE
);
CREATE TABLE memory_base_workflow_run (
	id CHAR(32) NOT NULL,
	memory_base_id CHAR(32) NOT NULL,
	session_id VARCHAR NOT NULL,
	workflow_job_id CHAR(32),
	ingestion_job_id CHAR(32),
	recorded_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_mbwr_mb_session_wf_job UNIQUE (memory_base_id, session_id, workflow_job_id),
	FOREIGN KEY(memory_base_id) REFERENCES memory_base (id) ON DELETE CASCADE,
	FOREIGN KEY(workflow_job_id) REFERENCES job (job_id) ON DELETE SET NULL,
	FOREIGN KEY(ingestion_job_id) REFERENCES job (job_id) ON DELETE SET NULL
);
CREATE TABLE message_ingestion_record (
	id CHAR(32) NOT NULL,
	message_id CHAR(32) NOT NULL,
	memory_base_id CHAR(32) NOT NULL,
	job_id CHAR(32),
	session_id VARCHAR NOT NULL,
	ingested_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_mir_message_session_mb UNIQUE (message_id, session_id, memory_base_id),
	FOREIGN KEY(message_id) REFERENCES message (id) ON DELETE CASCADE,
	FOREIGN KEY(memory_base_id) REFERENCES memory_base (id) ON DELETE CASCADE,
	FOREIGN KEY(job_id) REFERENCES job (job_id) ON DELETE SET NULL
);
CREATE TABLE sso_user_profile (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	sso_provider VARCHAR NOT NULL,
	sso_user_id VARCHAR NOT NULL,
	email VARCHAR,
	first_name VARCHAR,
	last_name VARCHAR,
	picture VARCHAR,
	sso_last_login_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE variable (
	name VARCHAR NOT NULL,
	value VARCHAR NOT NULL,
	type VARCHAR,
	id CHAR(32) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME,
	is_environment_managed BOOLEAN,
	default_fields JSON,
	user_id CHAR(32) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES user (id)
);
INSERT INTO variable VALUES('FLOW_ID','','Generic','b4fc5715953e44ac807d749463a02f01','2026-10-27 18:14:55.266413',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('COMPONENT_ID','','Generic','130c621696014204a3b88198c7460f4c','2026-10-27 18:14:55.268802',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('FIELD_NAME','','Generic','a2e98179d11f4dcba997c2eebc0cb1f4','2026-10-27 18:14:55.270350',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('FLOW_ID','gAAAAABq4OoiCJ-aF8_x_plFDeCzkAnXbhisOlYOL0yCf95-nsRYMfaD4NnkNKFdbH5Wq-LVlsL0STEICm06MCfxmKYio9rmMQ==','Credential','afecdda56efb4b99901a84ae8cf58fbb','2026-10-27 18:14:58.647999',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('COMPONENT_ID','gAAAAABq4OoisWB6oOEnrzZeRf1gyKvc-Ods6HGNnhaofP9xPbY7r4LEyLlES0UFBPRkfwPCTYKu0VIFme0K89eGKoFXAnm5jw==','Credential','dd701317f32047a3be62670fe1808b2c','2026-10-27 18:14:58.649026',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('FIELD_NAME','gAAAAABq4OoihBajaIEOQg-jeQoSjHJMZye8rerKd10GKPLdR17pVzw3cBo64MohZTO5oGlfB0_UYvsazOgWgu_qEH5GRRm2fg==','Credential','22bb3e92938c4ab592b0943a9c6988ba','2026-10-27 18:14:58.649724',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
INSERT INTO variable VALUES('ASTRA_TOKEN','gAAAAABq4OoiDx9QA8ba4m6QqKuk0PxkIxyHJbpy-AwMr9zwhT_bqvEYbAMLnh6tyk4JvcAggCNxLzKwkm8golLsq9ViDSuBRw==','Credential','ce3aa67c3ab546fb9e719d2c238dc886','2026-10-27 18:14:58.650408',NULL,0,'[]','807bc5eb65aa47528d014d42975104e9');
CREATE TABLE authz_role_assignment (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	role_id CHAR(32) NOT NULL,
	domain_type VARCHAR NOT NULL,
	domain_id CHAR(32),
	assigned_at DATETIME NOT NULL,
	assigned_by CHAR(32),
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(role_id) REFERENCES authz_role (id) ON DELETE CASCADE,
	FOREIGN KEY(assigned_by) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE authz_team_member_grant (
	id CHAR(32) NOT NULL,
	membership_id CHAR(32) NOT NULL,
	source_kind VARCHAR(16) NOT NULL,
	provider_id VARCHAR(256),
	external_group_id VARCHAR(512),
	legacy_source VARCHAR(512),
	administrative_actor CHAR(32),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_authz_team_member_grant_source CHECK ((source_kind = 'manual' AND provider_id IS NULL AND external_group_id IS NULL AND legacy_source IS NULL) OR (source_kind = 'directory' AND provider_id IS NOT NULL AND external_group_id IS NOT NULL AND legacy_source IS NULL) OR (source_kind = 'legacy' AND provider_id IS NULL AND external_group_id IS NULL AND legacy_source IS NOT NULL)),
	FOREIGN KEY(membership_id) REFERENCES authz_team_member (id) ON DELETE CASCADE,
	FOREIGN KEY(administrative_actor) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE connection_oauth (
	connection_id CHAR(32) NOT NULL,
	generation CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	registration_id VARCHAR(120) NOT NULL,
	config_digest VARCHAR(64) NOT NULL,
	state_digest VARCHAR(64),
	browser_digest VARCHAR(64),
	encrypted_verifier TEXT,
	scopes JSON NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (connection_id),
	FOREIGN KEY(connection_id) REFERENCES connection (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	UNIQUE (state_digest)
);
CREATE TABLE connection_secret (
	connection_id CHAR(32) NOT NULL,
	encrypted_payload TEXT NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (connection_id),
	FOREIGN KEY(connection_id) REFERENCES connection (id) ON DELETE CASCADE
);
CREATE TABLE ingestion_run (
	id CHAR(32) NOT NULL,
	job_id CHAR(32),
	kb_name VARCHAR NOT NULL,
	kb_id CHAR(32),
	user_id CHAR(32),
	source_type VARCHAR NOT NULL,
	source_config JSON NOT NULL,
	status VARCHAR NOT NULL,
	error_message VARCHAR,
	total_items INTEGER NOT NULL,
	succeeded INTEGER NOT NULL,
	failed INTEGER NOT NULL,
	skipped INTEGER NOT NULL,
	total_bytes BIGINT DEFAULT '0' NOT NULL,
	chunks_created INTEGER NOT NULL,
	items JSON NOT NULL,
	user_metadata JSON DEFAULT '{}' NOT NULL,
	started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	finished_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT ck_ingestion_run_status CHECK (status IN ('pending', 'running', 'succeeded', 'partial', 'failed', 'cancelled')),
	FOREIGN KEY(kb_id) REFERENCES knowledge_base (id) ON DELETE SET NULL
);
CREATE TABLE trigger_listener_lease (
	connection_id CHAR(32) NOT NULL,
	holder VARCHAR(128) NOT NULL,
	acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	heartbeat_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (connection_id),
	FOREIGN KEY(connection_id) REFERENCES connection (id) ON DELETE CASCADE
);
CREATE TABLE authz_edit_lock (
	id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	holder_user_id CHAR(32) NOT NULL,
	acquired_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE,
	FOREIGN KEY(holder_user_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE authz_role_assignment_grant (
	id CHAR(32) NOT NULL,
	assignment_id CHAR(32) NOT NULL,
	source_kind VARCHAR NOT NULL,
	provider_id VARCHAR(256),
	external_group VARCHAR(256),
	administrative_actor CHAR(32),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_authz_role_assignment_grant_source CHECK ((source_kind = 'manual' AND provider_id IS NULL AND external_group IS NULL) OR (source_kind = 'idp' AND provider_id IS NOT NULL AND external_group IS NOT NULL)),
	FOREIGN KEY(assignment_id) REFERENCES authz_role_assignment (id) ON DELETE CASCADE,
	FOREIGN KEY(administrative_actor) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TABLE flow_version (
	id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	user_id CHAR(32),
	data JSON,
	version_number INTEGER NOT NULL,
	description VARCHAR(500),
	retained BOOLEAN DEFAULT 0 NOT NULL,
	retained_reason VARCHAR(255),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT unique_flow_version_number UNIQUE (flow_id, version_number),
	CONSTRAINT ck_flow_version_version_number_positive CHECK (version_number >= 1),
	FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE SET NULL
);
INSERT INTO flow_version VALUES('7c38caf19a3e4e0caeff9c164133407b','8fc277947ee842ca903c632e7739462d','807bc5eb65aa47528d014d42975104e9','{"nodes": [{"id": "groupComponent-4cobG", "type": "genericNode", "position": {"x": 0, "y": 0.0}, "data": {"id": "groupComponent-4cobG", "type": "GroupNode", "node": {"display_name": "Group", "documentation": "", "description": "", "template": {"code_ChatInput-mFoZc": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.inputs.inputs import BoolInput\nfrom lfx.io import (\n    DropdownInput,\n    FileInput,\n    MessageTextInput,\n    MultilineInput,\n    Output,\n)\nfrom lfx.schema.image import get_file_paths\nfrom lfx.schema.message import Message\nfrom lfx.services.deps import get_settings_service\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_USER,\n    MESSAGE_SENDER_USER,\n)\nfrom lfx.utils.file_path_security import (\n    component_file_access_scopes,\n    enforce_local_file_access,\n    is_local_file_access_restricted,\n)\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatInput\"\n    minimized = True\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Input Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n            input_types=[],\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n            temp_file=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Chat Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    async def message_response(self) -> Message:\n        # Ensure files is a list and filter out empty/None values\n        files = self.files if self.files else []\n        if files and not isinstance(files, list):\n            files = [files]\n        # Filter out None/empty values\n        files = [f for f in files if f is not None and f != \"\"]\n\n        # Build endpoints inject caller-controlled file references directly into\n        # ChatInput. Resolve and validate local references before the Message can\n        # later read them while constructing model attachment content.\n        if files:\n            settings_service = get_settings_service()\n            storage_type = getattr(getattr(settings_service, \"settings\", None), \"storage_type\", \"local\")\n            # The storage factory falls back to local storage for unsupported\n            # values, so only the explicitly configured S3 backend may bypass\n            # filesystem containment.\n            if str(storage_type).lower() != \"s3\" and is_local_file_access_restricted():\n                scope_ids = list(component_file_access_scopes(self))\n                # Public executions replace graph.flow_id with a per-visitor\n                # virtual ID. Only the server-populated source provenance may\n                # restore the already-validated public attachment namespace.\n                source_flow_id = getattr(self.graph, \"source_flow_id\", None)\n                if source_flow_id:\n                    scope_ids.append(source_flow_id)\n                for file_path in get_file_paths(files):\n                    enforce_local_file_access(file_path, scope_ids=scope_ids)\n\n        session_id = self.session_id or self.graph.session_id or \"\"\n        message = await Message.create(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=session_id,\n            context_id=self.context_id,\n            files=files,\n        )\n        if session_id and isinstance(message, Message) and self.should_store_message:\n            stored_message = await self.send_message(\n                message,\n            )\n            self.message.value = stored_message\n            message = stored_message\n\n        self.status = message\n        return message\n", "proxy": {"id": "ChatInput-mFoZc", "field": "code"}, "display_name": "Code"}, "context_id_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "context_id"}}, "files_ChatInput-mFoZc": {"_input_type": "FileInput", "advanced": true, "api_editable": false, "display_name": "Files", "dynamic": false, "fileTypes": ["csv", "json", "pdf", "txt", "md", "mdx", "yaml", "yml", "xml", "html", "htm", "docx", "py", "sh", "sql", "js", "ts", "tsx", "jpg", "jpeg", "png", "bmp", "image"], "file_path": "", "info": "Files to be sent with the message.", "list": true, "list_add_label": "Add More", "name": "files", "override_skip": false, "placeholder": "", "required": false, "show": true, "temp_file": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "file", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "files"}}, "input_value_ChatInput-mFoZc": {"_input_type": "MultilineInput", "advanced": true, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Input Text", "dynamic": false, "info": "Message to be passed as input.", "input_types": [], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "input_value"}}, "sender_ChatInput-mFoZc": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "User", "proxy": {"id": "ChatInput-mFoZc", "field": "sender"}}, "sender_name_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "User", "proxy": {"id": "ChatInput-mFoZc", "field": "sender_name"}}, "session_id_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "session_id"}}, "should_store_message_ChatInput-mFoZc": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatInput-mFoZc", "field": "should_store_message"}}, "code_TextInput-dW7qt_groupComponent-1KKIA": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n", "proxy": {"id": "groupComponent-1KKIA", "field": "code_TextInput-dW7qt"}, "display_name": "Inner group - code"}, "use_global_variable_TextInput-dW7qt_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - use_global_variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false, "proxy": {"id": "groupComponent-1KKIA", "field": "use_global_variable_TextInput-dW7qt"}}, "clean_data_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - clean_data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "groupComponent-1KKIA", "field": "clean_data_ChatOutput-TwOup"}}, "code_ChatOutput-TwOup_groupComponent-1KKIA": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n", "proxy": {"id": "groupComponent-1KKIA", "field": "code_ChatOutput-TwOup"}, "display_name": "Inner group - code"}, "context_id_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - context_id", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "groupComponent-1KKIA", "field": "context_id_ChatOutput-TwOup"}}, "data_template_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - data_template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}", "proxy": {"id": "groupComponent-1KKIA", "field": "data_template_ChatOutput-TwOup"}}, "sender_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Inner group - sender", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine", "proxy": {"id": "groupComponent-1KKIA", "field": "sender_ChatOutput-TwOup"}}, "sender_name_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - sender_name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI", "proxy": {"id": "groupComponent-1KKIA", "field": "sender_name_ChatOutput-TwOup"}}, "session_id_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - session_id", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "groupComponent-1KKIA", "field": "session_id_ChatOutput-TwOup"}}, "should_store_message_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - should_store_message", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "groupComponent-1KKIA", "field": "should_store_message_ChatOutput-TwOup"}}}, "flow": {"data": {"nodes": [{"id": "ChatInput-mFoZc", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "ChatInput-mFoZc", "type": "ChatInput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Get chat inputs from the Playground.", "display_name": "Chat Input", "documentation": "https://docs.langflow.org/chat-input-and-output", "edited": false, "field_order": ["input_value", "should_store_message", "sender", "sender_name", "session_id", "context_id", "files"], "frozen": false, "icon": "MessagesSquare", "legacy": false, "metadata": {"code_hash": "45974e6b1909", "component_class_name": "ChatInput", "dependencies": {"dependencies": [{"name": "lfx", "version": null}], "total_dependencies": 1}, "module": "lfx.components.input_output.chat.ChatInput"}, "minimized": true, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Chat Message", "group_outputs": false, "method": "message_response", "name": "message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "template": {"_type": "Component", "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.inputs.inputs import BoolInput\nfrom lfx.io import (\n    DropdownInput,\n    FileInput,\n    MessageTextInput,\n    MultilineInput,\n    Output,\n)\nfrom lfx.schema.image import get_file_paths\nfrom lfx.schema.message import Message\nfrom lfx.services.deps import get_settings_service\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_USER,\n    MESSAGE_SENDER_USER,\n)\nfrom lfx.utils.file_path_security import (\n    component_file_access_scopes,\n    enforce_local_file_access,\n    is_local_file_access_restricted,\n)\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatInput\"\n    minimized = True\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Input Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n            input_types=[],\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n            temp_file=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Chat Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    async def message_response(self) -> Message:\n        # Ensure files is a list and filter out empty/None values\n        files = self.files if self.files else []\n        if files and not isinstance(files, list):\n            files = [files]\n        # Filter out None/empty values\n        files = [f for f in files if f is not None and f != \"\"]\n\n        # Build endpoints inject caller-controlled file references directly into\n        # ChatInput. Resolve and validate local references before the Message can\n        # later read them while constructing model attachment content.\n        if files:\n            settings_service = get_settings_service()\n            storage_type = getattr(getattr(settings_service, \"settings\", None), \"storage_type\", \"local\")\n            # The storage factory falls back to local storage for unsupported\n            # values, so only the explicitly configured S3 backend may bypass\n            # filesystem containment.\n            if str(storage_type).lower() != \"s3\" and is_local_file_access_restricted():\n                scope_ids = list(component_file_access_scopes(self))\n                # Public executions replace graph.flow_id with a per-visitor\n                # virtual ID. Only the server-populated source provenance may\n                # restore the already-validated public attachment namespace.\n                source_flow_id = getattr(self.graph, \"source_flow_id\", None)\n                if source_flow_id:\n                    scope_ids.append(source_flow_id)\n                for file_path in get_file_paths(files):\n                    enforce_local_file_access(file_path, scope_ids=scope_ids)\n\n        session_id = self.session_id or self.graph.session_id or \"\"\n        message = await Message.create(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=session_id,\n            context_id=self.context_id,\n            files=files,\n        )\n        if session_id and isinstance(message, Message) and self.should_store_message:\n            stored_message = await self.send_message(\n                message,\n            )\n            self.message.value = stored_message\n            message = stored_message\n\n        self.status = message\n        return message\n"}, "context_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "files": {"_input_type": "FileInput", "advanced": true, "api_editable": false, "display_name": "Files", "dynamic": false, "fileTypes": ["csv", "json", "pdf", "txt", "md", "mdx", "yaml", "yml", "xml", "html", "htm", "docx", "py", "sh", "sql", "js", "ts", "tsx", "jpg", "jpeg", "png", "bmp", "image"], "file_path": "", "info": "Files to be sent with the message.", "list": true, "list_add_label": "Add More", "name": "files", "override_skip": false, "placeholder": "", "required": false, "show": true, "temp_file": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "file", "value": ""}, "input_value": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Input Text", "dynamic": false, "info": "Message to be passed as input.", "input_types": [], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "sender": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "User"}, "sender_name": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "User"}, "session_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "should_store_message": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}}, "tool_mode": false}, "showNode": true}}, {"id": "groupComponent-1KKIA", "type": "genericNode", "position": {"x": 0, "y": 0}, "data": {"id": "groupComponent-1KKIA", "type": "GroupNode", "node": {"display_name": "Group", "documentation": "", "description": "", "template": {"code_TextInput-dW7qt": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n", "proxy": {"id": "TextInput-dW7qt", "field": "code"}, "display_name": "Code"}, "input_value_TextInput-dW7qt": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Text", "dynamic": false, "info": "Text to be passed as input.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "TextInput-dW7qt", "field": "input_value"}}, "use_global_variable_TextInput-dW7qt": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Use Global Variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false, "proxy": {"id": "TextInput-dW7qt", "field": "use_global_variable"}}, "clean_data_ChatOutput-TwOup": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Basic Clean Data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatOutput-TwOup", "field": "clean_data"}}, "code_ChatOutput-TwOup": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n", "proxy": {"id": "ChatOutput-TwOup", "field": "code"}, "display_name": "Code"}, "context_id_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatOutput-TwOup", "field": "context_id"}}, "data_template_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Data Template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}", "proxy": {"id": "ChatOutput-TwOup", "field": "data_template"}}, "sender_ChatOutput-TwOup": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine", "proxy": {"id": "ChatOutput-TwOup", "field": "sender"}}, "sender_name_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI", "proxy": {"id": "ChatOutput-TwOup", "field": "sender_name"}}, "session_id_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatOutput-TwOup", "field": "session_id"}}, "should_store_message_ChatOutput-TwOup": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatOutput-TwOup", "field": "should_store_message"}}}, "flow": {"data": {"nodes": [{"id": "TextInput-dW7qt", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "TextInput-dW7qt", "type": "TextInput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Get user text inputs.", "display_name": "Text Input", "documentation": "https://docs.langflow.org/text-input-and-output", "edited": false, "field_order": ["input_value", "use_global_variable"], "frozen": false, "icon": "type", "legacy": true, "metadata": {"code_hash": "2811c0e0496f", "component_class_name": "TextInputComponent", "dependencies": {"dependencies": [{"name": "lfx", "version": null}], "total_dependencies": 1}, "module": "lfx.components.input_output.text.TextInputComponent"}, "minimized": false, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Text", "group_outputs": false, "method": "text_response", "name": "text", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "replacement": ["input_output.ChatInput"], "template": {"_type": "Component", "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n"}, "input_value": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Text", "dynamic": false, "info": "Text to be passed as input.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "use_global_variable": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Use Global Variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false}}, "tool_mode": false}, "showNode": true}}, {"id": "ChatOutput-TwOup", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "ChatOutput-TwOup", "type": "ChatOutput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Display a chat message in the Playground.", "display_name": "Chat Output", "documentation": "https://docs.langflow.org/chat-input-and-output", "edited": false, "field_order": ["input_value", "should_store_message", "sender", "sender_name", "session_id", "context_id", "data_template", "clean_data"], "frozen": false, "icon": "MessagesSquare", "legacy": false, "metadata": {"code_hash": "0aab1c78e1dc", "component_class_name": "ChatOutput", "dependencies": {"dependencies": [{"name": "orjson", "version": "3.11.9"}, {"name": "fastapi", "version": "0.139.2"}, {"name": "lfx", "version": null}], "total_dependencies": 3}, "module": "lfx.components.input_output.chat_output.ChatOutput"}, "minimized": true, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "template": {"_type": "Component", "clean_data": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Basic Clean Data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}, "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n"}, "context_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "data_template": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Data Template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}"}, "input_value": {"_input_type": "HandleInput", "advanced": false, "api_editable": false, "display_name": "Inputs", "dynamic": false, "info": "Message to be passed as output.", "input_types": ["Data", "JSON", "DataFrame", "Table", "Message"], "list": false, "list_add_label": "Add More", "name": "input_value", "override_skip": false, "placeholder": "", "required": true, "show": true, "title_case": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "other", "value": ""}, "sender": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine"}, "sender_name": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI"}, "session_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "should_store_message": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}}, "tool_mode": false}, "showNode": true}}], "edges": [{"animated": false, "className": "", "data": {"sourceHandle": {"dataType": "TextInput", "id": "TextInput-dW7qt", "name": "text", "output_types": ["Message"]}, "targetHandle": {"fieldName": "input_value", "id": "ChatOutput-TwOup", "inputTypes": ["Data", "JSON", "DataFrame", "Table", "Message"], "type": "other"}}, "id": "reactflow__edge-TextInput-dW7qt{\u0153dataType\u0153:\u0153TextInput\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153,\u0153name\u0153:\u0153text\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}-ChatOutput-TwOup{\u0153fieldName\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153ChatOutput-TwOup\u0153,\u0153inputTypes\u0153:[\u0153Data\u0153,\u0153JSON\u0153,\u0153DataFrame\u0153,\u0153Table\u0153,\u0153Message\u0153],\u0153type\u0153:\u0153other\u0153}", "selected": false, "source": "TextInput-dW7qt", "sourceHandle": "{\u0153dataType\u0153:\u0153TextInput\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153,\u0153name\u0153:\u0153text\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}", "target": "ChatOutput-TwOup", "targetHandle": "{\u0153fieldName\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153ChatOutput-TwOup\u0153,\u0153inputTypes\u0153:[\u0153Data\u0153,\u0153JSON\u0153,\u0153DataFrame\u0153,\u0153Table\u0153,\u0153Message\u0153],\u0153type\u0153:\u0153other\u0153}"}], "viewport": {"zoom": 1, "x": 0, "y": 0}}, "is_component": false, "name": "Inner group", "description": "", "id": "Nc1t8"}, "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "ChatOutput-TwOup_message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null, "proxy": {"id": "ChatOutput-TwOup", "name": "message", "nodeDisplayName": "Chat Output"}}]}}}], "edges": [{"animated": false, "className": "", "data": {"sourceHandle": {"dataType": "ChatInput", "id": "ChatInput-mFoZc", "name": "message", "output_types": ["Message"]}, "targetHandle": {"fieldName": "input_value_TextInput-dW7qt", "id": "groupComponent-1KKIA", "inputTypes": ["Message"], "type": "str", "proxy": {"id": "TextInput-dW7qt", "field": "input_value"}}}, "id": "reactflow__edge-ChatInput-mFoZc{\u0153dataType\u0153:\u0153ChatInput\u0153,\u0153id\u0153:\u0153ChatInput-mFoZc\u0153,\u0153name\u0153:\u0153message\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}-groupComponent-1KKIA{\u0153fieldName\u0153:\u0153input_value_TextInput-dW7qt\u0153,\u0153id\u0153:\u0153groupComponent-1KKIA\u0153,\u0153inputTypes\u0153:[\u0153Message\u0153],\u0153type\u0153:\u0153str\u0153}", "selected": false, "source": "ChatInput-mFoZc", "sourceHandle": "{\u0153dataType\u0153:\u0153ChatInput\u0153,\u0153id\u0153:\u0153ChatInput-mFoZc\u0153,\u0153name\u0153:\u0153message\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}", "target": "groupComponent-1KKIA", "targetHandle": "{\u0153fieldName\u0153:\u0153input_value_TextInput-dW7qt\u0153,\u0153id\u0153:\u0153groupComponent-1KKIA\u0153,\u0153inputTypes\u0153:[\u0153Message\u0153],\u0153proxy\u0153:{\u0153field\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153},\u0153type\u0153:\u0153str\u0153}"}], "viewport": {"zoom": 1, "x": 0, "y": 0}}, "is_component": false, "name": "Outer group", "description": "", "id": "h0a1a"}, "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "groupComponent-1KKIA_ChatOutput-TwOup_message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null, "proxy": {"id": "groupComponent-1KKIA", "name": "ChatOutput-TwOup_message", "nodeDisplayName": "Group"}}]}}}], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}',1,'Fixture version',0,NULL,'2026-10-27 18:14:59');
CREATE TABLE flow_version_deployment_attachment (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	flow_version_id CHAR(32) NOT NULL,
	deployment_id CHAR(32) NOT NULL,
	provider_snapshot_id VARCHAR,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_flow_version_deployment UNIQUE (flow_version_id, deployment_id),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(flow_version_id) REFERENCES flow_version (id) ON DELETE CASCADE,
	FOREIGN KEY(deployment_id) REFERENCES deployment (id) ON DELETE CASCADE
);
CREATE TABLE span (
	name VARCHAR NOT NULL,
	span_type VARCHAR(9) NOT NULL,
	status VARCHAR(5) NOT NULL,
	start_time DATETIME NOT NULL,
	end_time DATETIME,
	latency_ms INTEGER NOT NULL,
	inputs JSON,
	outputs JSON,
	error TEXT,
	span_kind VARCHAR(8) NOT NULL,
	attributes JSON,
	id CHAR(32) NOT NULL,
	trace_id CHAR(32) NOT NULL,
	parent_span_id CHAR(32),
	PRIMARY KEY (id),
	FOREIGN KEY(trace_id) REFERENCES trace (id) ON DELETE CASCADE,
	FOREIGN KEY(parent_span_id) REFERENCES span (id)
);
CREATE TABLE IF NOT EXISTS "trigger" (
	id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	name VARCHAR(255) NOT NULL,
	kind VARCHAR(64) NOT NULL,
	provider VARCHAR(64),
	node_id VARCHAR(255),
	connection_id CHAR(32),
	config JSON NOT NULL,
	provider_state JSON NOT NULL,
	state VARCHAR(24) DEFAULT 'pending' NOT NULL,
	binding_target VARCHAR(16) DEFAULT 'flow' NOT NULL,
	deployment_id CHAR(32),
	flow_version_id CHAR(32),
	session_policy VARCHAR(16) DEFAULT 'per_event' NOT NULL,
	concurrency_limit INTEGER DEFAULT '1' NOT NULL,
	max_attempts INTEGER DEFAULT '5' NOT NULL,
	public_id VARCHAR(64),
	signing_secret_encrypted TEXT,
	next_fire_at DATETIME,
	last_fired_at DATETIME,
	last_error TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_trigger_state CHECK (state IN ('pending', 'active', 'paused', 'expired', 'needs_reconnect', 'error', 'dead')),
	CONSTRAINT ck_trigger_binding_target CHECK (binding_target IN ('flow', 'deployment')),
	CONSTRAINT ck_trigger_session_policy CHECK (session_policy IN ('per_event', 'shared')),
	CONSTRAINT ck_trigger_concurrency_limit_positive CHECK (concurrency_limit >= 1),
	CONSTRAINT ck_trigger_max_attempts_positive CHECK (max_attempts >= 1),
	FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(connection_id) REFERENCES connection (id) ON DELETE SET NULL,
	FOREIGN KEY(deployment_id) REFERENCES deployment (id) ON DELETE SET NULL,
	FOREIGN KEY(flow_version_id) REFERENCES flow_version (id) ON DELETE NO ACTION
);
INSERT INTO "trigger" VALUES('9a1409eeb9a347d787c7377b5e176588','8fc277947ee842ca903c632e7739462d','807bc5eb65aa47528d014d42975104e9','Fixture pin','webhook',NULL,NULL,NULL,'{}','{}','pending','flow',NULL,'7c38caf19a3e4e0caeff9c164133407b','per_event',1,5,NULL,NULL,NULL,NULL,NULL,'2026-10-27 18:14:59','2026-10-27 18:14:59');
CREATE TABLE trigger_event (
	id CHAR(32) NOT NULL,
	trigger_id CHAR(32) NOT NULL,
	dedupe_key VARCHAR(255) NOT NULL,
	state VARCHAR(16) DEFAULT 'pending' NOT NULL,
	attempt INTEGER DEFAULT '0' NOT NULL,
	available_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	lease_owner VARCHAR(128),
	lease_expires_at DATETIME,
	payload JSON NOT NULL,
	session_id VARCHAR(255),
	job_id CHAR(32),
	replay_of_event_id CHAR(32),
	error TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_trigger_event_trigger_dedupe UNIQUE (trigger_id, dedupe_key),
	CONSTRAINT ck_trigger_event_state CHECK (state IN ('pending', 'claimed', 'dispatched', 'completed', 'failed', 'dead')),
	CONSTRAINT ck_trigger_event_attempt_non_negative CHECK (attempt >= 0),
	FOREIGN KEY(trigger_id) REFERENCES "trigger" (id) ON DELETE CASCADE,
	FOREIGN KEY(replay_of_event_id) REFERENCES trigger_event (id) ON DELETE SET NULL
);
CREATE TABLE trigger_source_version (
	trigger_id CHAR(32) NOT NULL,
	item_key VARCHAR(64) NOT NULL,
	provider VARCHAR(32) NOT NULL,
	resource VARCHAR(512) NOT NULL,
	provider_item_id VARCHAR(512) NOT NULL,
	version VARCHAR(255) NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (trigger_id, item_key),
	FOREIGN KEY(trigger_id) REFERENCES "trigger" (id) ON DELETE CASCADE
);
CREATE TABLE trigger_subscription (
	id CHAR(32) NOT NULL,
	trigger_id CHAR(32) NOT NULL,
	connection_id CHAR(32),
	provider VARCHAR(64) NOT NULL,
	provider_subscription_id VARCHAR(255) NOT NULL,
	client_state_digest VARCHAR(64),
	provider_state JSON NOT NULL,
	state VARCHAR(16) DEFAULT 'pending' NOT NULL,
	expires_at DATETIME,
	renew_after DATETIME,
	lease_owner VARCHAR(128),
	lease_until DATETIME,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_trigger_subscription_state CHECK (state IN ('pending', 'active', 'expired', 'error')),
	CONSTRAINT uq_trigger_subscription_provider_external_id UNIQUE (provider, provider_subscription_id),
	FOREIGN KEY(trigger_id) REFERENCES "trigger" (id) ON DELETE CASCADE,
	FOREIGN KEY(connection_id) REFERENCES connection (id) ON DELETE SET NULL
);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL,
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version VALUES('e5a7c9b1d3f2');
CREATE TABLE IF NOT EXISTS "apikey" (
	name VARCHAR,
	last_used_at DATETIME,
	total_uses INTEGER NOT NULL,
	is_active BOOLEAN NOT NULL,
	expires_at DATETIME,
	id CHAR(32) NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	api_key VARCHAR NOT NULL,
	api_key_hash VARCHAR,
	user_id CHAR(32) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (id),
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE TABLE IF NOT EXISTS "flow" (
	name VARCHAR NOT NULL,
	description TEXT,
	icon_bg_color VARCHAR,
	gradient VARCHAR,
	is_component BOOLEAN,
	updated_at DATETIME,
	webhook BOOLEAN,
	endpoint_name VARCHAR,
	data JSON,
	mcp_enabled BOOLEAN,
	action_name VARCHAR,
	action_description TEXT,
	access_type VARCHAR(7) DEFAULT 'PRIVATE' NOT NULL,
	flow_type VARCHAR(8) DEFAULT 'workflow' NOT NULL,
	a2a_enabled BOOLEAN DEFAULT 0,
	a2a_card_overrides JSON,
	id CHAR(32) NOT NULL,
	user_id CHAR(32),
	icon VARCHAR,
	tags JSON,
	locked BOOLEAN,
	folder_id CHAR(32),
	workspace_id CHAR(32),
	fs_path VARCHAR,
	version_token CHAR(32),
	last_modified_by CHAR(32),
	PRIMARY KEY (id),
	CONSTRAINT unique_flow_name UNIQUE (user_id, name),
	CONSTRAINT unique_flow_endpoint_name UNIQUE (user_id, endpoint_name),
	CONSTRAINT fk_flow_user_id_user FOREIGN KEY(user_id) REFERENCES user (id),
	UNIQUE (id),
	FOREIGN KEY(folder_id) REFERENCES folder (id)
);
INSERT INTO flow VALUES('Fixture nested groups','A group inside a group.',NULL,NULL,0,'2026-10-27 18:14:58.994984',0,NULL,'{"nodes": [{"id": "groupComponent-4cobG", "type": "genericNode", "position": {"x": 0, "y": 0.0}, "data": {"id": "groupComponent-4cobG", "type": "GroupNode", "node": {"display_name": "Group", "documentation": "", "description": "", "template": {"code_ChatInput-mFoZc": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.inputs.inputs import BoolInput\nfrom lfx.io import (\n    DropdownInput,\n    FileInput,\n    MessageTextInput,\n    MultilineInput,\n    Output,\n)\nfrom lfx.schema.image import get_file_paths\nfrom lfx.schema.message import Message\nfrom lfx.services.deps import get_settings_service\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_USER,\n    MESSAGE_SENDER_USER,\n)\nfrom lfx.utils.file_path_security import (\n    component_file_access_scopes,\n    enforce_local_file_access,\n    is_local_file_access_restricted,\n)\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatInput\"\n    minimized = True\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Input Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n            input_types=[],\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n            temp_file=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Chat Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    async def message_response(self) -> Message:\n        # Ensure files is a list and filter out empty/None values\n        files = self.files if self.files else []\n        if files and not isinstance(files, list):\n            files = [files]\n        # Filter out None/empty values\n        files = [f for f in files if f is not None and f != \"\"]\n\n        # Build endpoints inject caller-controlled file references directly into\n        # ChatInput. Resolve and validate local references before the Message can\n        # later read them while constructing model attachment content.\n        if files:\n            settings_service = get_settings_service()\n            storage_type = getattr(getattr(settings_service, \"settings\", None), \"storage_type\", \"local\")\n            # The storage factory falls back to local storage for unsupported\n            # values, so only the explicitly configured S3 backend may bypass\n            # filesystem containment.\n            if str(storage_type).lower() != \"s3\" and is_local_file_access_restricted():\n                scope_ids = list(component_file_access_scopes(self))\n                # Public executions replace graph.flow_id with a per-visitor\n                # virtual ID. Only the server-populated source provenance may\n                # restore the already-validated public attachment namespace.\n                source_flow_id = getattr(self.graph, \"source_flow_id\", None)\n                if source_flow_id:\n                    scope_ids.append(source_flow_id)\n                for file_path in get_file_paths(files):\n                    enforce_local_file_access(file_path, scope_ids=scope_ids)\n\n        session_id = self.session_id or self.graph.session_id or \"\"\n        message = await Message.create(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=session_id,\n            context_id=self.context_id,\n            files=files,\n        )\n        if session_id and isinstance(message, Message) and self.should_store_message:\n            stored_message = await self.send_message(\n                message,\n            )\n            self.message.value = stored_message\n            message = stored_message\n\n        self.status = message\n        return message\n", "proxy": {"id": "ChatInput-mFoZc", "field": "code"}, "display_name": "Code"}, "context_id_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "context_id"}}, "files_ChatInput-mFoZc": {"_input_type": "FileInput", "advanced": true, "api_editable": false, "display_name": "Files", "dynamic": false, "fileTypes": ["csv", "json", "pdf", "txt", "md", "mdx", "yaml", "yml", "xml", "html", "htm", "docx", "py", "sh", "sql", "js", "ts", "tsx", "jpg", "jpeg", "png", "bmp", "image"], "file_path": "", "info": "Files to be sent with the message.", "list": true, "list_add_label": "Add More", "name": "files", "override_skip": false, "placeholder": "", "required": false, "show": true, "temp_file": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "file", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "files"}}, "input_value_ChatInput-mFoZc": {"_input_type": "MultilineInput", "advanced": true, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Input Text", "dynamic": false, "info": "Message to be passed as input.", "input_types": [], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "input_value"}}, "sender_ChatInput-mFoZc": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "User", "proxy": {"id": "ChatInput-mFoZc", "field": "sender"}}, "sender_name_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "User", "proxy": {"id": "ChatInput-mFoZc", "field": "sender_name"}}, "session_id_ChatInput-mFoZc": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatInput-mFoZc", "field": "session_id"}}, "should_store_message_ChatInput-mFoZc": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatInput-mFoZc", "field": "should_store_message"}}, "code_TextInput-dW7qt_groupComponent-1KKIA": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n", "proxy": {"id": "groupComponent-1KKIA", "field": "code_TextInput-dW7qt"}, "display_name": "Inner group - code"}, "use_global_variable_TextInput-dW7qt_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - use_global_variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false, "proxy": {"id": "groupComponent-1KKIA", "field": "use_global_variable_TextInput-dW7qt"}}, "clean_data_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - clean_data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "groupComponent-1KKIA", "field": "clean_data_ChatOutput-TwOup"}}, "code_ChatOutput-TwOup_groupComponent-1KKIA": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n", "proxy": {"id": "groupComponent-1KKIA", "field": "code_ChatOutput-TwOup"}, "display_name": "Inner group - code"}, "context_id_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - context_id", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "groupComponent-1KKIA", "field": "context_id_ChatOutput-TwOup"}}, "data_template_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - data_template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}", "proxy": {"id": "groupComponent-1KKIA", "field": "data_template_ChatOutput-TwOup"}}, "sender_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Inner group - sender", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine", "proxy": {"id": "groupComponent-1KKIA", "field": "sender_ChatOutput-TwOup"}}, "sender_name_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - sender_name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI", "proxy": {"id": "groupComponent-1KKIA", "field": "sender_name_ChatOutput-TwOup"}}, "session_id_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Inner group - session_id", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "groupComponent-1KKIA", "field": "session_id_ChatOutput-TwOup"}}, "should_store_message_ChatOutput-TwOup_groupComponent-1KKIA": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Inner group - should_store_message", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "groupComponent-1KKIA", "field": "should_store_message_ChatOutput-TwOup"}}}, "flow": {"data": {"nodes": [{"id": "ChatInput-mFoZc", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "ChatInput-mFoZc", "type": "ChatInput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Get chat inputs from the Playground.", "display_name": "Chat Input", "documentation": "https://docs.langflow.org/chat-input-and-output", "edited": false, "field_order": ["input_value", "should_store_message", "sender", "sender_name", "session_id", "context_id", "files"], "frozen": false, "icon": "MessagesSquare", "legacy": false, "metadata": {"code_hash": "45974e6b1909", "component_class_name": "ChatInput", "dependencies": {"dependencies": [{"name": "lfx", "version": null}], "total_dependencies": 1}, "module": "lfx.components.input_output.chat.ChatInput"}, "minimized": true, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Chat Message", "group_outputs": false, "method": "message_response", "name": "message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "template": {"_type": "Component", "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.inputs.inputs import BoolInput\nfrom lfx.io import (\n    DropdownInput,\n    FileInput,\n    MessageTextInput,\n    MultilineInput,\n    Output,\n)\nfrom lfx.schema.image import get_file_paths\nfrom lfx.schema.message import Message\nfrom lfx.services.deps import get_settings_service\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_USER,\n    MESSAGE_SENDER_USER,\n)\nfrom lfx.utils.file_path_security import (\n    component_file_access_scopes,\n    enforce_local_file_access,\n    is_local_file_access_restricted,\n)\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatInput\"\n    minimized = True\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Input Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n            input_types=[],\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n            temp_file=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Chat Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    async def message_response(self) -> Message:\n        # Ensure files is a list and filter out empty/None values\n        files = self.files if self.files else []\n        if files and not isinstance(files, list):\n            files = [files]\n        # Filter out None/empty values\n        files = [f for f in files if f is not None and f != \"\"]\n\n        # Build endpoints inject caller-controlled file references directly into\n        # ChatInput. Resolve and validate local references before the Message can\n        # later read them while constructing model attachment content.\n        if files:\n            settings_service = get_settings_service()\n            storage_type = getattr(getattr(settings_service, \"settings\", None), \"storage_type\", \"local\")\n            # The storage factory falls back to local storage for unsupported\n            # values, so only the explicitly configured S3 backend may bypass\n            # filesystem containment.\n            if str(storage_type).lower() != \"s3\" and is_local_file_access_restricted():\n                scope_ids = list(component_file_access_scopes(self))\n                # Public executions replace graph.flow_id with a per-visitor\n                # virtual ID. Only the server-populated source provenance may\n                # restore the already-validated public attachment namespace.\n                source_flow_id = getattr(self.graph, \"source_flow_id\", None)\n                if source_flow_id:\n                    scope_ids.append(source_flow_id)\n                for file_path in get_file_paths(files):\n                    enforce_local_file_access(file_path, scope_ids=scope_ids)\n\n        session_id = self.session_id or self.graph.session_id or \"\"\n        message = await Message.create(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=session_id,\n            context_id=self.context_id,\n            files=files,\n        )\n        if session_id and isinstance(message, Message) and self.should_store_message:\n            stored_message = await self.send_message(\n                message,\n            )\n            self.message.value = stored_message\n            message = stored_message\n\n        self.status = message\n        return message\n"}, "context_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "files": {"_input_type": "FileInput", "advanced": true, "api_editable": false, "display_name": "Files", "dynamic": false, "fileTypes": ["csv", "json", "pdf", "txt", "md", "mdx", "yaml", "yml", "xml", "html", "htm", "docx", "py", "sh", "sql", "js", "ts", "tsx", "jpg", "jpeg", "png", "bmp", "image"], "file_path": "", "info": "Files to be sent with the message.", "list": true, "list_add_label": "Add More", "name": "files", "override_skip": false, "placeholder": "", "required": false, "show": true, "temp_file": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "file", "value": ""}, "input_value": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Input Text", "dynamic": false, "info": "Message to be passed as input.", "input_types": [], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "sender": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "User"}, "sender_name": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "User"}, "session_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "should_store_message": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}}, "tool_mode": false}, "showNode": true}}, {"id": "groupComponent-1KKIA", "type": "genericNode", "position": {"x": 0, "y": 0}, "data": {"id": "groupComponent-1KKIA", "type": "GroupNode", "node": {"display_name": "Group", "documentation": "", "description": "", "template": {"code_TextInput-dW7qt": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n", "proxy": {"id": "TextInput-dW7qt", "field": "code"}, "display_name": "Code"}, "input_value_TextInput-dW7qt": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Text", "dynamic": false, "info": "Text to be passed as input.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "TextInput-dW7qt", "field": "input_value"}}, "use_global_variable_TextInput-dW7qt": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Use Global Variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false, "proxy": {"id": "TextInput-dW7qt", "field": "use_global_variable"}}, "clean_data_ChatOutput-TwOup": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Basic Clean Data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatOutput-TwOup", "field": "clean_data"}}, "code_ChatOutput-TwOup": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": false, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n", "proxy": {"id": "ChatOutput-TwOup", "field": "code"}, "display_name": "Code"}, "context_id_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatOutput-TwOup", "field": "context_id"}}, "data_template_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Data Template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}", "proxy": {"id": "ChatOutput-TwOup", "field": "data_template"}}, "sender_ChatOutput-TwOup": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine", "proxy": {"id": "ChatOutput-TwOup", "field": "sender"}}, "sender_name_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI", "proxy": {"id": "ChatOutput-TwOup", "field": "sender_name"}}, "session_id_ChatOutput-TwOup": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "", "proxy": {"id": "ChatOutput-TwOup", "field": "session_id"}}, "should_store_message_ChatOutput-TwOup": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true, "proxy": {"id": "ChatOutput-TwOup", "field": "should_store_message"}}}, "flow": {"data": {"nodes": [{"id": "TextInput-dW7qt", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "TextInput-dW7qt", "type": "TextInput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Get user text inputs.", "display_name": "Text Input", "documentation": "https://docs.langflow.org/text-input-and-output", "edited": false, "field_order": ["input_value", "use_global_variable"], "frozen": false, "icon": "type", "legacy": true, "metadata": {"code_hash": "2811c0e0496f", "component_class_name": "TextInputComponent", "dependencies": {"dependencies": [{"name": "lfx", "version": null}], "total_dependencies": 1}, "module": "lfx.components.input_output.text.TextInputComponent"}, "minimized": false, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Text", "group_outputs": false, "method": "text_response", "name": "text", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "replacement": ["input_output.ChatInput"], "template": {"_type": "Component", "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from typing import Any\n\nfrom lfx.base.io.text import TextComponent\nfrom lfx.io import BoolInput, MultilineInput, Output\nfrom lfx.schema.message import Message\n\n\nclass TextInputComponent(TextComponent):\n    display_name = \"Text Input\"\n    description = \"Get user text inputs.\"\n    documentation: str = \"https://docs.langflow.org/text-input-and-output\"\n    icon = \"type\"\n    name = \"TextInput\"\n    legacy = True\n    replacement = [\"input_output.ChatInput\"]\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Text to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"use_global_variable\",\n            display_name=\"Use Global Variable\",\n            info=\"Enable to select from global variables (shows globe icon). Disables multiline editing.\",\n            value=False,\n            advanced=True,\n            real_time_refresh=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Output Text\", name=\"text\", method=\"text_response\"),\n    ]\n\n    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:\n        if field_name == \"use_global_variable\":\n            if field_value:\n                # Enable global variable mode: single-line with password masking and globe dropdown\n                build_config[\"input_value\"][\"multiline\"] = False\n                build_config[\"input_value\"][\"password\"] = True\n            else:\n                # Default mode: multiline text editing\n                build_config[\"input_value\"][\"multiline\"] = True\n                build_config[\"input_value\"][\"password\"] = False\n        return build_config\n\n    def text_response(self) -> Message:\n        return Message(\n            text=self.input_value,\n        )\n"}, "input_value": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Text", "dynamic": false, "info": "Text to be passed as input.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "use_global_variable": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Use Global Variable", "dynamic": false, "info": "Enable to select from global variables (shows globe icon). Disables multiline editing.", "list": false, "list_add_label": "Add More", "name": "use_global_variable", "override_skip": false, "placeholder": "", "real_time_refresh": true, "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": false}}, "tool_mode": false}, "showNode": true}}, {"id": "ChatOutput-TwOup", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "ChatOutput-TwOup", "type": "ChatOutput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Display a chat message in the Playground.", "display_name": "Chat Output", "documentation": "https://docs.langflow.org/chat-input-and-output", "edited": false, "field_order": ["input_value", "should_store_message", "sender", "sender_name", "session_id", "context_id", "data_template", "clean_data"], "frozen": false, "icon": "MessagesSquare", "legacy": false, "metadata": {"code_hash": "0aab1c78e1dc", "component_class_name": "ChatOutput", "dependencies": {"dependencies": [{"name": "orjson", "version": "3.11.9"}, {"name": "fastapi", "version": "0.139.2"}, {"name": "lfx", "version": null}], "total_dependencies": 3}, "module": "lfx.components.input_output.chat_output.ChatOutput"}, "minimized": true, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "template": {"_type": "Component", "clean_data": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Basic Clean Data", "dynamic": false, "info": "Whether to clean data before converting to string.", "list": false, "list_add_label": "Add More", "name": "clean_data", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}, "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from collections.abc import Generator\nfrom typing import Any\n\nimport orjson\nfrom fastapi.encoders import jsonable_encoder\n\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.helpers.data import safe_convert\nfrom lfx.inputs.inputs import BoolInput, DropdownInput, HandleInput, MessageTextInput\nfrom lfx.schema.data import Data\nfrom lfx.schema.dataframe import DataFrame\nfrom lfx.schema.message import Message\nfrom lfx.schema.properties import Source\nfrom lfx.template.field.base import Output\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_AI,\n    MESSAGE_SENDER_USER,\n)\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatOutput\"\n    minimized = True\n\n    inputs = [\n        HandleInput(\n            name=\"input_value\",\n            display_name=\"Inputs\",\n            info=\"Message to be passed as output.\",\n            input_types=[\"Data\", \"JSON\", \"DataFrame\", \"Table\", \"Message\"],\n            required=True,\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.\",\n        ),\n        BoolInput(\n            name=\"clean_data\",\n            display_name=\"Basic Clean Data\",\n            value=True,\n            advanced=True,\n            info=\"Whether to clean data before converting to string.\",\n        ),\n    ]\n    outputs = [\n        Output(\n            display_name=\"Output Message\",\n            name=\"message\",\n            method=\"message_response\",\n        ),\n    ]\n\n    def _build_source(self, id_: str | None, display_name: str | None, source: str | None) -> Source:\n        source_dict = {}\n        if id_:\n            source_dict[\"id\"] = id_\n        if display_name:\n            source_dict[\"display_name\"] = display_name\n        if source:\n            # Handle case where source is a ChatOpenAI object\n            if hasattr(source, \"model_name\"):\n                source_dict[\"source\"] = source.model_name\n            elif hasattr(source, \"model\"):\n                source_dict[\"source\"] = str(source.model)\n            else:\n                source_dict[\"source\"] = str(source)\n        return Source(**source_dict)\n\n    async def message_response(self) -> Message:\n        # First convert the input to string if needed\n        text = self.convert_to_string()\n\n        # Get source properties\n        source, _, display_name, source_id = self.get_properties_from_source_component()\n\n        # Create or use existing Message object\n        if isinstance(self.input_value, Message) and not self.is_connected_to_chat_input():\n            message = self.input_value\n            # Update message properties\n            message.text = text\n            # Preserve existing session_id from the incoming message if it exists\n            existing_session_id = message.session_id\n        else:\n            message = Message(text=text)\n            existing_session_id = None\n\n        # Set message properties\n        message.sender = self.sender\n        message.sender_name = self.sender_name\n        # Preserve session_id from incoming message, or use component/graph session_id\n        message.session_id = (\n            self.session_id or existing_session_id or (self.graph.session_id if hasattr(self, \"graph\") else None) or \"\"\n        )\n        message.context_id = self.context_id\n        message.flow_id = self.graph.flow_id if hasattr(self, \"graph\") else None\n        message.properties.source = self._build_source(source_id, display_name, source)\n\n        # Store message if needed\n        if message.session_id and self.should_store_message:\n            stored_message = await self.send_message(message)\n            self.message.value = stored_message\n            message = stored_message\n\n        # Set accumulated token usage from all upstream LLM vertices.\n        # This must happen AFTER send_message() because streaming captures\n        # usage from chunks and would overwrite accumulated totals.\n        if hasattr(self, \"_vertex\") and self._vertex is not None:\n            accumulated_usage = self._vertex._accumulate_upstream_token_usage()  # noqa: SLF001\n            if accumulated_usage:\n                message.properties.usage = accumulated_usage\n                if self.should_store_message and message.get_id():\n                    message = await self._update_stored_message(message)\n                    await self._send_message_event(message, id_=message.get_id())\n\n        self.status = message\n        return message\n\n    def _serialize_data(self, data: Data) -> str:\n        \"\"\"Serialize Data object to JSON string.\"\"\"\n        # Convert data.data to JSON-serializable format\n        serializable_data = jsonable_encoder(data.data)\n        # Serialize with orjson, enabling pretty printing with indentation\n        json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)\n        # Convert bytes to string and wrap in Markdown code blocks\n        return \"```json\\n\" + json_bytes.decode(\"utf-8\") + \"\\n```\"\n\n    def _validate_input(self) -> None:\n        \"\"\"Validate the input data and raise ValueError if invalid.\"\"\"\n        if self.input_value is None:\n            msg = \"Input data cannot be None\"\n            raise ValueError(msg)\n        if isinstance(self.input_value, list) and not all(\n            isinstance(item, Message | Data | DataFrame | str) for item in self.input_value\n        ):\n            invalid_types = [\n                type(item).__name__\n                for item in self.input_value\n                if not isinstance(item, Message | Data | DataFrame | str)\n            ]\n            msg = f\"Expected Data or DataFrame or Message or str, got {invalid_types}\"\n            raise TypeError(msg)\n        if not isinstance(\n            self.input_value,\n            Message | Data | DataFrame | str | list | Generator | type(None),\n        ):\n            type_name = type(self.input_value).__name__\n            msg = f\"Expected Data or DataFrame or Message or str, Generator or None, got {type_name}\"\n            raise TypeError(msg)\n\n    def convert_to_string(self) -> str | Generator[Any, None, None]:\n        \"\"\"Convert input data to string with proper error handling.\"\"\"\n        self._validate_input()\n        clean_data: bool = getattr(self, \"clean_data\", False)\n        if isinstance(self.input_value, list):\n            return \"\\n\".join([safe_convert(item, clean_data=clean_data) for item in self.input_value])\n        if isinstance(self.input_value, Generator):\n            return self.input_value\n        return safe_convert(self.input_value, clean_data=clean_data)\n"}, "context_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "data_template": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Data Template", "dynamic": false, "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data''s text key.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "data_template", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "{text}"}, "input_value": {"_input_type": "HandleInput", "advanced": false, "api_editable": false, "display_name": "Inputs", "dynamic": false, "info": "Message to be passed as output.", "input_types": ["Data", "JSON", "DataFrame", "Table", "Message"], "list": false, "list_add_label": "Add More", "name": "input_value", "override_skip": false, "placeholder": "", "required": true, "show": true, "title_case": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "other", "value": ""}, "sender": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "Machine"}, "sender_name": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "AI"}, "session_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "should_store_message": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}}, "tool_mode": false}, "showNode": true}}], "edges": [{"animated": false, "className": "", "data": {"sourceHandle": {"dataType": "TextInput", "id": "TextInput-dW7qt", "name": "text", "output_types": ["Message"]}, "targetHandle": {"fieldName": "input_value", "id": "ChatOutput-TwOup", "inputTypes": ["Data", "JSON", "DataFrame", "Table", "Message"], "type": "other"}}, "id": "reactflow__edge-TextInput-dW7qt{\u0153dataType\u0153:\u0153TextInput\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153,\u0153name\u0153:\u0153text\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}-ChatOutput-TwOup{\u0153fieldName\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153ChatOutput-TwOup\u0153,\u0153inputTypes\u0153:[\u0153Data\u0153,\u0153JSON\u0153,\u0153DataFrame\u0153,\u0153Table\u0153,\u0153Message\u0153],\u0153type\u0153:\u0153other\u0153}", "selected": false, "source": "TextInput-dW7qt", "sourceHandle": "{\u0153dataType\u0153:\u0153TextInput\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153,\u0153name\u0153:\u0153text\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}", "target": "ChatOutput-TwOup", "targetHandle": "{\u0153fieldName\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153ChatOutput-TwOup\u0153,\u0153inputTypes\u0153:[\u0153Data\u0153,\u0153JSON\u0153,\u0153DataFrame\u0153,\u0153Table\u0153,\u0153Message\u0153],\u0153type\u0153:\u0153other\u0153}"}], "viewport": {"zoom": 1, "x": 0, "y": 0}}, "is_component": false, "name": "Inner group", "description": "", "id": "Nc1t8"}, "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "ChatOutput-TwOup_message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null, "proxy": {"id": "ChatOutput-TwOup", "name": "message", "nodeDisplayName": "Chat Output"}}]}}}], "edges": [{"animated": false, "className": "", "data": {"sourceHandle": {"dataType": "ChatInput", "id": "ChatInput-mFoZc", "name": "message", "output_types": ["Message"]}, "targetHandle": {"fieldName": "input_value_TextInput-dW7qt", "id": "groupComponent-1KKIA", "inputTypes": ["Message"], "type": "str", "proxy": {"id": "TextInput-dW7qt", "field": "input_value"}}}, "id": "reactflow__edge-ChatInput-mFoZc{\u0153dataType\u0153:\u0153ChatInput\u0153,\u0153id\u0153:\u0153ChatInput-mFoZc\u0153,\u0153name\u0153:\u0153message\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}-groupComponent-1KKIA{\u0153fieldName\u0153:\u0153input_value_TextInput-dW7qt\u0153,\u0153id\u0153:\u0153groupComponent-1KKIA\u0153,\u0153inputTypes\u0153:[\u0153Message\u0153],\u0153type\u0153:\u0153str\u0153}", "selected": false, "source": "ChatInput-mFoZc", "sourceHandle": "{\u0153dataType\u0153:\u0153ChatInput\u0153,\u0153id\u0153:\u0153ChatInput-mFoZc\u0153,\u0153name\u0153:\u0153message\u0153,\u0153output_types\u0153:[\u0153Message\u0153]}", "target": "groupComponent-1KKIA", "targetHandle": "{\u0153fieldName\u0153:\u0153input_value_TextInput-dW7qt\u0153,\u0153id\u0153:\u0153groupComponent-1KKIA\u0153,\u0153inputTypes\u0153:[\u0153Message\u0153],\u0153proxy\u0153:{\u0153field\u0153:\u0153input_value\u0153,\u0153id\u0153:\u0153TextInput-dW7qt\u0153},\u0153type\u0153:\u0153str\u0153}"}], "viewport": {"zoom": 1, "x": 0, "y": 0}}, "is_component": false, "name": "Outer group", "description": "", "id": "h0a1a"}, "outputs": [{"allows_loop": false, "cache": true, "display_name": "Output Message", "group_outputs": false, "method": "message_response", "name": "groupComponent-1KKIA_ChatOutput-TwOup_message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null, "proxy": {"id": "groupComponent-1KKIA", "name": "ChatOutput-TwOup_message", "nodeDisplayName": "Group"}}]}}}], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}',0,NULL,NULL,'PRIVATE','workflow',0,'null','8fc277947ee842ca903c632e7739462d','807bc5eb65aa47528d014d42975104e9',NULL,'null',0,'610039a62609486984f06f8617d255ba',NULL,NULL,'68724b09f7734257913c6e3ffea5e0ea','807bc5eb65aa47528d014d42975104e9');
INSERT INTO flow VALUES('Fixture saved component','A saved component.',NULL,NULL,1,'2026-10-27 18:14:59.006401',0,NULL,'{"nodes": [{"id": "ChatInput-pWoJh", "type": "genericNode", "position": {"x": 0, "y": 0}, "selected": false, "data": {"id": "ChatInput-pWoJh", "type": "ChatInput", "node": {"base_classes": ["Message"], "beta": false, "conditional_paths": [], "custom_fields": {}, "description": "Get chat inputs from the Playground.", "display_name": "Chat Input", "documentation": "https://docs.langflow.org/chat-input-and-output", "edited": false, "field_order": ["input_value", "should_store_message", "sender", "sender_name", "session_id", "context_id", "files"], "frozen": false, "icon": "MessagesSquare", "legacy": false, "metadata": {"code_hash": "45974e6b1909", "component_class_name": "ChatInput", "dependencies": {"dependencies": [{"name": "lfx", "version": null}], "total_dependencies": 1}, "module": "lfx.components.input_output.chat.ChatInput"}, "minimized": true, "output_types": [], "outputs": [{"allows_loop": false, "cache": true, "display_name": "Chat Message", "group_outputs": false, "method": "message_response", "name": "message", "selected": "Message", "tool_mode": true, "types": ["Message"], "value": "__UNDEFINED__", "hidden": false, "options": null, "required_inputs": null}], "pinned": false, "template": {"_type": "Component", "code": {"advanced": true, "api_editable": false, "dynamic": true, "fileTypes": [], "file_path": "", "info": "", "list": false, "load_from_db": false, "multiline": true, "name": "code", "password": false, "placeholder": "", "required": true, "show": true, "title_case": false, "type": "code", "value": "from lfx.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom lfx.base.io.chat import ChatComponent\nfrom lfx.inputs.inputs import BoolInput\nfrom lfx.io import (\n    DropdownInput,\n    FileInput,\n    MessageTextInput,\n    MultilineInput,\n    Output,\n)\nfrom lfx.schema.image import get_file_paths\nfrom lfx.schema.message import Message\nfrom lfx.services.deps import get_settings_service\nfrom lfx.utils.constants import (\n    MESSAGE_SENDER_AI,\n    MESSAGE_SENDER_NAME_USER,\n    MESSAGE_SENDER_USER,\n)\nfrom lfx.utils.file_path_security import (\n    component_file_access_scopes,\n    enforce_local_file_access,\n    is_local_file_access_restricted,\n)\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    documentation: str = \"https://docs.langflow.org/chat-input-and-output\"\n    icon = \"MessagesSquare\"\n    name = \"ChatInput\"\n    minimized = True\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Input Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n            input_types=[],\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"context_id\",\n            display_name=\"Context ID\",\n            info=\"The context ID of the chat. Adds an extra layer to the local memory.\",\n            value=\"\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n            temp_file=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Chat Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    async def message_response(self) -> Message:\n        # Ensure files is a list and filter out empty/None values\n        files = self.files if self.files else []\n        if files and not isinstance(files, list):\n            files = [files]\n        # Filter out None/empty values\n        files = [f for f in files if f is not None and f != \"\"]\n\n        # Build endpoints inject caller-controlled file references directly into\n        # ChatInput. Resolve and validate local references before the Message can\n        # later read them while constructing model attachment content.\n        if files:\n            settings_service = get_settings_service()\n            storage_type = getattr(getattr(settings_service, \"settings\", None), \"storage_type\", \"local\")\n            # The storage factory falls back to local storage for unsupported\n            # values, so only the explicitly configured S3 backend may bypass\n            # filesystem containment.\n            if str(storage_type).lower() != \"s3\" and is_local_file_access_restricted():\n                scope_ids = list(component_file_access_scopes(self))\n                # Public executions replace graph.flow_id with a per-visitor\n                # virtual ID. Only the server-populated source provenance may\n                # restore the already-validated public attachment namespace.\n                source_flow_id = getattr(self.graph, \"source_flow_id\", None)\n                if source_flow_id:\n                    scope_ids.append(source_flow_id)\n                for file_path in get_file_paths(files):\n                    enforce_local_file_access(file_path, scope_ids=scope_ids)\n\n        session_id = self.session_id or self.graph.session_id or \"\"\n        message = await Message.create(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=session_id,\n            context_id=self.context_id,\n            files=files,\n        )\n        if session_id and isinstance(message, Message) and self.should_store_message:\n            stored_message = await self.send_message(\n                message,\n            )\n            self.message.value = stored_message\n            message = stored_message\n\n        self.status = message\n        return message\n"}, "context_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Context ID", "dynamic": false, "info": "The context ID of the chat. Adds an extra layer to the local memory.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "context_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "files": {"_input_type": "FileInput", "advanced": true, "api_editable": false, "display_name": "Files", "dynamic": false, "fileTypes": ["csv", "json", "pdf", "txt", "md", "mdx", "yaml", "yml", "xml", "html", "htm", "docx", "py", "sh", "sql", "js", "ts", "tsx", "jpg", "jpeg", "png", "bmp", "image"], "file_path": "", "info": "Files to be sent with the message.", "list": true, "list_add_label": "Add More", "name": "files", "override_skip": false, "placeholder": "", "required": false, "show": true, "temp_file": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": false, "type": "file", "value": ""}, "input_value": {"_input_type": "MultilineInput", "advanced": false, "ai_enabled": false, "api_editable": false, "copy_field": false, "display_name": "Input Text", "dynamic": false, "info": "Message to be passed as input.", "input_types": [], "list": false, "list_add_label": "Add More", "load_from_db": false, "multiline": true, "name": "input_value", "override_skip": false, "password": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "sender": {"_input_type": "DropdownInput", "advanced": true, "api_editable": false, "combobox": false, "dialog_inputs": {}, "display_name": "Sender Type", "dynamic": false, "external_options": {}, "info": "Type of sender.", "name": "sender", "options": ["Machine", "User"], "options_metadata": [], "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "toggle": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "str", "value": "User"}, "sender_name": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Sender Name", "dynamic": false, "info": "Name of the sender.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "sender_name", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": "User"}, "session_id": {"_input_type": "MessageTextInput", "advanced": true, "api_editable": false, "display_name": "Session ID", "dynamic": false, "info": "The session ID of the chat. If empty, the current session ID parameter will be used.", "input_types": ["Message"], "list": false, "list_add_label": "Add More", "load_from_db": false, "name": "session_id", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_input": true, "trace_as_metadata": true, "track_in_telemetry": false, "type": "str", "value": ""}, "should_store_message": {"_input_type": "BoolInput", "advanced": true, "api_editable": false, "display_name": "Store Messages", "dynamic": false, "info": "Store the message in the history.", "list": false, "list_add_label": "Add More", "name": "should_store_message", "override_skip": false, "placeholder": "", "required": false, "show": true, "title_case": false, "tool_mode": false, "trace_as_metadata": true, "track_in_telemetry": true, "type": "bool", "value": true}}, "tool_mode": false}, "showNode": true}}], "edges": []}',0,NULL,NULL,'PRIVATE','workflow',0,'null','015cf9a4b6fe430e93b036ccb7bb84eb','807bc5eb65aa47528d014d42975104e9',NULL,'null',0,'610039a62609486984f06f8617d255ba',NULL,NULL,'a333d1a1190946388ce091df83cabbc2','807bc5eb65aa47528d014d42975104e9');
CREATE TABLE IF NOT EXISTS "vertex_build" (
	timestamp DATETIME NOT NULL,
	id VARCHAR NOT NULL,
	data JSON,
	artifacts JSON,
	params TEXT,
	build_id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	valid BOOLEAN NOT NULL, job_id CHAR(32),
	CONSTRAINT pk_vertex_build PRIMARY KEY (build_id)
);
CREATE TABLE IF NOT EXISTS "transaction" (
	timestamp DATETIME NOT NULL,
	vertex_id VARCHAR NOT NULL,
	target_id VARCHAR,
	inputs JSON,
	outputs JSON,
	status VARCHAR NOT NULL,
	id CHAR(32) NOT NULL,
	flow_id CHAR(32) NOT NULL,
	error VARCHAR, user_id CHAR(32), session_id VARCHAR,
	CONSTRAINT pk_transaction PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS "trace" (
	name VARCHAR NOT NULL,
	status VARCHAR(5) NOT NULL,
	start_time DATETIME NOT NULL,
	end_time DATETIME,
	total_latency_ms INTEGER NOT NULL,
	total_tokens INTEGER NOT NULL,
	flow_id CHAR(32) NOT NULL,
	session_id VARCHAR,
	id CHAR(32) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_trace_flow_id_flow FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE,
	FOREIGN KEY(flow_id) REFERENCES flow (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "file" (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	name VARCHAR NOT NULL,
	path VARCHAR NOT NULL,
	size INTEGER NOT NULL,
	provider VARCHAR,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT file_name_user_id_key UNIQUE (name, user_id),
	CONSTRAINT fk_file_user_id_user FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES user (id)
);
CREATE TABLE IF NOT EXISTS "deployment_provider_account" (
	id CHAR(32) NOT NULL,
	user_id CHAR(32) NOT NULL,
	provider_tenant_id VARCHAR,
	name VARCHAR NOT NULL,
	provider_url VARCHAR NOT NULL,
	api_key VARCHAR NOT NULL,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	provider_key VARCHAR(19) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_deployment_provider_account_user_url_tenant UNIQUE (user_id, provider_url, provider_tenant_id),
	CONSTRAINT uq_deployment_provider_account_provider_name UNIQUE (user_id, provider_key, name),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "message" (
	timestamp DATETIME NOT NULL,
	sender VARCHAR NOT NULL,
	sender_name VARCHAR NOT NULL,
	session_id VARCHAR NOT NULL,
	text TEXT,
	id CHAR(32) NOT NULL,
	flow_id CHAR(32),
	files JSON,
	error BOOLEAN DEFAULT 0 NOT NULL,
	edit BOOLEAN DEFAULT 0 NOT NULL,
	properties JSON,
	category TEXT,
	content_blocks JSON,
	context_id VARCHAR,
	session_metadata JSON,
	run_id CHAR(32),
	is_output BOOLEAN DEFAULT false NOT NULL, user_id CHAR(32),
	CONSTRAINT pk_message PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS "deployment" (
	id CHAR(32) NOT NULL,
	resource_key VARCHAR NOT NULL,
	user_id CHAR(32) NOT NULL,
	project_id CHAR(32) NOT NULL,
	deployment_provider_account_id CHAR(32) NOT NULL,
	workspace_id CHAR(32),
	display_name VARCHAR,
	description TEXT,
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
	deployment_type VARCHAR(5),
	PRIMARY KEY (id),
	CONSTRAINT uq_deployment_resource_key_in_provider UNIQUE (deployment_provider_account_id, resource_key),
	FOREIGN KEY(user_id) REFERENCES user (id) ON DELETE CASCADE,
	FOREIGN KEY(deployment_provider_account_id) REFERENCES deployment_provider_account (id) ON DELETE CASCADE,
	FOREIGN KEY(project_id) REFERENCES folder (id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "execution_signals" (
	id CHAR(32) NOT NULL,
	job_id CHAR(32) NOT NULL,
	signal_type VARCHAR(6) NOT NULL,
	data JSON,
	created_at DATETIME NOT NULL,
	consumed_at DATETIME,
	PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS "sso_config" (
	id CHAR(32) NOT NULL,
	slug VARCHAR NOT NULL,
	display_name VARCHAR NOT NULL,
	protocol VARCHAR NOT NULL,
	enabled BOOLEAN NOT NULL,
	sort_order INTEGER DEFAULT 0 NOT NULL,
	client_secret_encrypted VARCHAR,
	provider_settings JSON NOT NULL,
	email_claim VARCHAR NOT NULL,
	username_claim VARCHAR NOT NULL,
	user_id_claim VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	created_by CHAR(32),
	updated_by CHAR(32),
	PRIMARY KEY (id),
	CONSTRAINT ck_sso_config_client_secret_envelope CHECK (client_secret_encrypted IS NULL OR substr(client_secret_encrypted, 1, 37) = 'lf-sso:v1:hkdf-sha256-v1:aes-256-gcm:' AND substr(client_secret_encrypted, 54, 1) = ':' AND length(client_secret_encrypted) >= 76),
	CONSTRAINT ck_sso_config_protocol_consistency CHECK (protocol IN ('oidc', 'saml', 'ldap') AND JSON_EXTRACT(provider_settings, '$."protocol"') IS NOT NULL AND JSON_EXTRACT(provider_settings, '$."protocol"') = protocol),
	CONSTRAINT ck_sso_config_enabled_complete CHECK (enabled IS 0 OR protocol IN ('saml', 'ldap') OR protocol = 'oidc' AND client_secret_encrypted IS NOT NULL AND JSON_EXTRACT(provider_settings, '$."client_id"') IS NOT NULL AND length(trim(JSON_EXTRACT(provider_settings, '$."client_id"'))) > 0 AND (JSON_EXTRACT(provider_settings, '$."discovery_url"') IS NOT NULL AND length(trim(JSON_EXTRACT(provider_settings, '$."discovery_url"'))) > 0 OR JSON_EXTRACT(provider_settings, '$."authorization_endpoint"') IS NOT NULL AND length(trim(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'))) > 0 AND JSON_EXTRACT(provider_settings, '$."token_endpoint"') IS NOT NULL AND length(trim(JSON_EXTRACT(provider_settings, '$."token_endpoint"'))) > 0 AND JSON_EXTRACT(provider_settings, '$."jwks_uri"') IS NOT NULL AND length(trim(JSON_EXTRACT(provider_settings, '$."jwks_uri"'))) > 0) AND (JSON_EXTRACT(provider_settings, '$."discovery_url"') IS NULL OR lower(JSON_EXTRACT(provider_settings, '$."discovery_url"')) LIKE 'http://%' AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) > 7 AND (substr(JSON_EXTRACT(provider_settings, '$."discovery_url"'), 8, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '
', '')) OR lower(JSON_EXTRACT(provider_settings, '$."discovery_url"')) LIKE 'https://%' AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) > 8 AND (substr(JSON_EXTRACT(provider_settings, '$."discovery_url"'), 9, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."discovery_url"')) = length(replace(JSON_EXTRACT(provider_settings, '$."discovery_url"'), '
', ''))) AND (JSON_EXTRACT(provider_settings, '$."token_endpoint"') IS NULL OR lower(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) LIKE 'http://%' AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) > 7 AND (substr(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), 8, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '
', '')) OR lower(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) LIKE 'https://%' AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) > 8 AND (substr(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), 9, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."token_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."token_endpoint"'), '
', ''))) AND (JSON_EXTRACT(provider_settings, '$."authorization_endpoint"') IS NULL OR lower(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) LIKE 'http://%' AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) > 7 AND (substr(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), 8, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '
', '')) OR lower(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) LIKE 'https://%' AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) > 8 AND (substr(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), 9, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"')) = length(replace(JSON_EXTRACT(provider_settings, '$."authorization_endpoint"'), '
', ''))) AND (JSON_EXTRACT(provider_settings, '$."jwks_uri"') IS NULL OR lower(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) LIKE 'http://%' AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) > 7 AND (substr(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), 8, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '
', '')) OR lower(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) LIKE 'https://%' AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) > 8 AND (substr(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), 9, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."jwks_uri"')) = length(replace(JSON_EXTRACT(provider_settings, '$."jwks_uri"'), '
', ''))) AND (JSON_EXTRACT(provider_settings, '$."issuer"') IS NULL OR lower(JSON_EXTRACT(provider_settings, '$."issuer"')) LIKE 'http://%' AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) > 7 AND (substr(JSON_EXTRACT(provider_settings, '$."issuer"'), 8, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '
', '')) OR lower(JSON_EXTRACT(provider_settings, '$."issuer"')) LIKE 'https://%' AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) > 8 AND (substr(JSON_EXTRACT(provider_settings, '$."issuer"'), 9, 1) NOT IN ('/', '\', '?', '#', ':')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), ' ', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '	', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '', '')) AND length(JSON_EXTRACT(provider_settings, '$."issuer"')) = length(replace(JSON_EXTRACT(provider_settings, '$."issuer"'), '
', '')))),
	FOREIGN KEY(created_by) REFERENCES user (id) ON DELETE SET NULL,
	FOREIGN KEY(updated_by) REFERENCES user (id) ON DELETE SET NULL
);
CREATE TRIGGER trg_sso_config_slug_immutable
                BEFORE UPDATE OF slug ON sso_config
                FOR EACH ROW
                WHEN OLD.slug IS NOT NULL AND NEW.slug IS NOT OLD.slug
                BEGIN
                    SELECT RAISE(ABORT, 'SSOConfig.slug is immutable after insert');
                END;
CREATE INDEX ix_audit_events_actor_timeline ON audit_events (actor_type, actor_id, timestamp);
CREATE INDEX ix_audit_events_acting_timeline ON audit_events (acting_issuer, acting_subject, timestamp);
CREATE INDEX ix_audit_events_request_id ON audit_events (request_id);
CREATE INDEX ix_audit_events_timeline ON audit_events (timestamp, id);
CREATE INDEX ix_audit_events_type_timeline ON audit_events (resource_type, timestamp, id);
CREATE INDEX ix_audit_events_resource_timeline ON audit_events (resource_type, resource_id, timestamp, id);
CREATE INDEX ix_audit_events_user_timeline ON audit_events (user_id, timestamp);
CREATE INDEX ix_authz_team_team_name ON authz_team (team_name);
CREATE UNIQUE INDEX ix_authz_team_adom_name ON authz_team (adom_name);
CREATE INDEX ix_casbin_rule_ptype ON casbin_rule (ptype);
CREATE INDEX ix_data_subject_request_status ON data_subject_request (status);
CREATE INDEX ix_dsr_subject_status ON data_subject_request (subject_user_id, status);
CREATE INDEX ix_job_user_id ON job (user_id);
CREATE INDEX ix_job_job_id ON job (job_id);
CREATE INDEX ix_job_flow_id ON job (flow_id);
CREATE INDEX ix_job_asset_id ON job (asset_id);
CREATE INDEX ix_job_status_created ON job (status, created_timestamp);
CREATE INDEX ix_job_finished_timestamp ON job (finished_timestamp);
CREATE INDEX ix_job_dedupe_key ON job (dedupe_key);
CREATE INDEX ix_job_type ON job (type);
CREATE INDEX ix_job_checkpoints_job_id ON job_checkpoints (job_id);
CREATE INDEX ix_job_events_id ON job_events (id);
CREATE INDEX ix_job_events_job_id ON job_events (job_id);
CREATE INDEX ix_knowledge_base_storage_migration_phase ON knowledge_base_storage_migration (phase);
CREATE INDEX ix_knowledge_base_storage_migration_kb_id ON knowledge_base_storage_migration (kb_id);
CREATE INDEX ix_memory_base_user_id ON memory_base (user_id);
CREATE INDEX ix_memory_base_flow_id ON memory_base (flow_id);
CREATE INDEX ix_trigger_cleanup_available_at ON trigger_cleanup (available_at);
CREATE UNIQUE INDEX ix_user_username_lower ON user (lower(username));
CREATE UNIQUE INDEX ix_user_username ON user (username);
CREATE INDEX ix_authz_access_exception_resource_type ON authz_access_exception (resource_type);
CREATE INDEX ix_authz_access_exception_resource ON authz_access_exception (resource_type, resource_id);
CREATE INDEX ix_authz_access_exception_user_id ON authz_access_exception (user_id);
CREATE INDEX ix_authz_access_exception_resource_id ON authz_access_exception (resource_id);
CREATE INDEX ix_authz_audit_log_action ON authz_audit_log (action);
CREATE INDEX ix_authz_audit_log_user_timestamp ON authz_audit_log (user_id, timestamp);
CREATE INDEX ix_authz_audit_log_actor_timestamp ON authz_audit_log (actor_id, timestamp);
CREATE INDEX ix_authz_audit_log_actor_type_timestamp ON authz_audit_log (actor_type, timestamp);
CREATE INDEX ix_authz_audit_log_timestamp ON authz_audit_log (timestamp);
CREATE INDEX ix_authz_audit_log_resource ON authz_audit_log (resource_type, resource_id);
CREATE INDEX ix_authz_audit_log_user_id ON authz_audit_log (user_id);
CREATE INDEX ix_authz_role_workspace_id ON authz_role (workspace_id);
CREATE UNIQUE INDEX ix_authz_role_name ON authz_role (name);
CREATE INDEX ix_authz_share_scope ON authz_share (scope);
CREATE INDEX ix_authz_share_resource ON authz_share (resource_type, resource_id);
CREATE UNIQUE INDEX uq_authz_share_targeted ON authz_share (resource_type, resource_id, scope, target_id) WHERE target_id IS NOT NULL;
CREATE INDEX ix_authz_share_resource_id ON authz_share (resource_id);
CREATE INDEX ix_authz_share_target_id ON authz_share (target_id);
CREATE INDEX ix_authz_share_resource_type ON authz_share (resource_type);
CREATE UNIQUE INDEX uq_authz_share_untargeted ON authz_share (resource_type, resource_id, scope) WHERE target_id IS NULL;
CREATE INDEX ix_authz_team_member_team_id ON authz_team_member (team_id);
CREATE INDEX ix_authz_team_member_user_id ON authz_team_member (user_id);
CREATE UNIQUE INDEX uq_catalog_policy_rule_unscoped ON catalog_policy_rule (resource_kind, resource_key, scope) WHERE domain_id IS NULL;
CREATE UNIQUE INDEX uq_catalog_policy_rule_scoped ON catalog_policy_rule (resource_kind, resource_key, scope, domain_id) WHERE domain_id IS NOT NULL;
CREATE UNIQUE INDEX uq_connection_instance_provider_name ON connection (provider_key, name) WHERE ownership_mode = 'instance';
CREATE UNIQUE INDEX uq_connection_user_provider_name ON connection (owner_id, provider_key, name) WHERE ownership_mode = 'user';
CREATE INDEX ix_connection_owner_id ON connection (owner_id);
CREATE INDEX ix_folder_is_personal ON folder (is_personal);
CREATE INDEX ix_folder_workspace_id ON folder (workspace_id);
CREATE INDEX ix_folder_name ON folder (name);
CREATE INDEX ix_knowledge_base_status ON knowledge_base (status);
CREATE INDEX ix_knowledge_base_name ON knowledge_base (name);
CREATE INDEX ix_knowledge_base_user_id ON knowledge_base (user_id);
CREATE INDEX ix_knowledge_base_storage_state ON knowledge_base (storage_state);
CREATE INDEX ix_mbpo_listing ON memory_base_preprocessing_output (memory_base_id, session_id, created_at);
CREATE INDEX ix_mbpo_pending ON memory_base_preprocessing_output (memory_base_id, session_id, status, created_at);
CREATE INDEX ix_mbpo_job_id ON memory_base_preprocessing_output (job_id);
CREATE INDEX ix_memory_base_session_memory_base_id ON memory_base_session (memory_base_id);
CREATE INDEX ix_memory_base_session_lookup ON memory_base_session (memory_base_id, session_id);
CREATE INDEX ix_memory_base_session_session_id ON memory_base_session (session_id);
CREATE INDEX ix_mbwr_ingestion_job_id ON memory_base_workflow_run (ingestion_job_id);
CREATE INDEX ix_mbwr_mb_session ON memory_base_workflow_run (memory_base_id, session_id);
CREATE INDEX ix_mir_memory_base_session ON message_ingestion_record (memory_base_id, session_id);
CREATE INDEX ix_mir_job_id ON message_ingestion_record (job_id);
CREATE INDEX ix_mir_message_id ON message_ingestion_record (message_id);
CREATE INDEX ix_sso_user_profile_user_id ON sso_user_profile (user_id);
CREATE UNIQUE INDEX uq_sso_user_profile_user_provider ON sso_user_profile (user_id, sso_provider);
CREATE UNIQUE INDEX uq_sso_user_profile_provider_user ON sso_user_profile (sso_provider, sso_user_id);
CREATE INDEX ix_sso_user_profile_email ON sso_user_profile (email);
CREATE UNIQUE INDEX uq_authz_role_assignment_scoped ON authz_role_assignment (user_id, role_id, domain_type, domain_id) WHERE domain_id IS NOT NULL;
CREATE INDEX ix_authz_role_assignment_user_id ON authz_role_assignment (user_id);
CREATE INDEX ix_authz_role_assignment_domain_id ON authz_role_assignment (domain_id);
CREATE INDEX ix_authz_role_assignment_role_id ON authz_role_assignment (role_id);
CREATE INDEX ix_authz_role_assignment_user_domain ON authz_role_assignment (user_id, domain_type, domain_id);
CREATE UNIQUE INDEX uq_authz_role_assignment_unscoped ON authz_role_assignment (user_id, role_id, domain_type) WHERE domain_id IS NULL;
CREATE UNIQUE INDEX uq_authz_team_member_grant_manual ON authz_team_member_grant (membership_id) WHERE source_kind = 'manual';
CREATE INDEX ix_authz_team_member_grant_provider_group ON authz_team_member_grant (provider_id, external_group_id);
CREATE UNIQUE INDEX uq_authz_team_member_grant_legacy ON authz_team_member_grant (membership_id, legacy_source) WHERE source_kind = 'legacy';
CREATE UNIQUE INDEX uq_authz_team_member_grant_directory ON authz_team_member_grant (membership_id, provider_id, external_group_id) WHERE source_kind = 'directory';
CREATE INDEX ix_authz_team_member_grant_membership_id ON authz_team_member_grant (membership_id);
CREATE INDEX ix_ingestion_run_source_type ON ingestion_run (source_type);
CREATE INDEX ix_ingestion_run_job_id ON ingestion_run (job_id);
CREATE INDEX ix_ingestion_run_user_id ON ingestion_run (user_id);
CREATE INDEX ix_ingestion_run_kb_name ON ingestion_run (kb_name);
CREATE INDEX ix_ingestion_run_status ON ingestion_run (status);
CREATE INDEX ix_ingestion_run_kb_id ON ingestion_run (kb_id);
CREATE INDEX ix_ingestion_run_started_at ON ingestion_run (started_at);
CREATE UNIQUE INDEX ix_authz_edit_lock_flow_id ON authz_edit_lock (flow_id);
CREATE INDEX ix_authz_edit_lock_expires_at ON authz_edit_lock (expires_at);
CREATE INDEX ix_authz_role_assignment_grant_assignment_id ON authz_role_assignment_grant (assignment_id);
CREATE UNIQUE INDEX uq_authz_role_assignment_grant_manual ON authz_role_assignment_grant (assignment_id) WHERE source_kind = 'manual';
CREATE UNIQUE INDEX uq_authz_role_assignment_grant_idp ON authz_role_assignment_grant (assignment_id, provider_id, external_group) WHERE source_kind = 'idp';
CREATE INDEX ix_authz_role_assignment_grant_provider_group ON authz_role_assignment_grant (provider_id, external_group);
CREATE INDEX ix_flow_version_flow_id ON flow_version (flow_id);
CREATE INDEX ix_flow_version_created_at ON flow_version (created_at);
CREATE INDEX ix_flow_version_user_id ON flow_version (user_id);
CREATE INDEX ix_flow_version_deployment_attachment_deployment_id ON flow_version_deployment_attachment (deployment_id);
CREATE INDEX ix_flow_version_deployment_attachment_provider_snapshot_id ON flow_version_deployment_attachment (provider_snapshot_id);
CREATE INDEX ix_flow_version_deployment_attachment_flow_version_id ON flow_version_deployment_attachment (flow_version_id);
CREATE INDEX ix_flow_version_deployment_attachment_user_id ON flow_version_deployment_attachment (user_id);
CREATE INDEX ix_span_parent_span_id ON span (parent_span_id);
CREATE INDEX ix_span_trace_id ON span (trace_id);
CREATE UNIQUE INDEX uq_trigger_flow_node ON "trigger" (flow_id, node_id) WHERE node_id IS NOT NULL;
CREATE INDEX ix_trigger_flow_version_id ON "trigger" (flow_version_id);
CREATE INDEX ix_trigger_kind ON "trigger" (kind);
CREATE UNIQUE INDEX uq_trigger_public_id ON "trigger" (public_id);
CREATE INDEX ix_trigger_state ON "trigger" (state);
CREATE INDEX ix_trigger_user_id ON "trigger" (user_id);
CREATE INDEX ix_trigger_connection_id ON "trigger" (connection_id);
CREATE INDEX ix_trigger_state_next_fire_at ON "trigger" (state, next_fire_at);
CREATE INDEX ix_trigger_flow_id ON "trigger" (flow_id);
CREATE INDEX ix_trigger_event_trigger_id ON trigger_event (trigger_id);
CREATE INDEX ix_trigger_event_state_available_at ON trigger_event (state, available_at);
CREATE INDEX ix_trigger_event_trigger_created_at ON trigger_event (trigger_id, created_at);
CREATE INDEX ix_trigger_event_created_at ON trigger_event (created_at);
CREATE INDEX ix_trigger_subscription_trigger_id ON trigger_subscription (trigger_id);
CREATE INDEX ix_trigger_subscription_renew_after ON trigger_subscription (state, renew_after);
CREATE INDEX ix_apikey_user_id ON apikey (user_id);
CREATE INDEX ix_apikey_name ON apikey (name);
CREATE INDEX ix_apikey_api_key_hash ON apikey (api_key_hash);
CREATE UNIQUE INDEX ix_apikey_api_key ON apikey (api_key);
CREATE INDEX ix_flow_workspace_id ON flow (workspace_id);
CREATE INDEX ix_flow_last_modified_by ON flow (last_modified_by);
CREATE INDEX ix_flow_description ON flow (description);
CREATE INDEX ix_flow_user_id ON flow (user_id);
CREATE INDEX ix_flow_name ON flow (name);
CREATE INDEX ix_flow_folder_id ON flow (folder_id);
CREATE INDEX ix_flow_endpoint_name ON flow (endpoint_name);
CREATE INDEX ix_vertex_build_job_id ON vertex_build (job_id);
CREATE INDEX ix_trace_flow_id ON trace (flow_id);
CREATE INDEX ix_trace_session_id ON trace (session_id);
CREATE INDEX ix_deployment_provider_account_user_id ON deployment_provider_account (user_id);
CREATE INDEX ix_deployment_provider_account_provider_key ON deployment_provider_account (provider_key);
CREATE INDEX ix_deployment_provider_account_provider_tenant_id ON deployment_provider_account (provider_tenant_id);
CREATE INDEX ix_message_run_id ON message (run_id);
CREATE INDEX ix_deployment_resource_key ON deployment (resource_key);
CREATE INDEX ix_deployment_user_id ON deployment (user_id);
CREATE INDEX ix_deployment_deployment_provider_account_id ON deployment (deployment_provider_account_id);
CREATE INDEX ix_deployment_project_id ON deployment (project_id);
CREATE INDEX ix_deployment_deployment_type ON deployment (deployment_type);
CREATE INDEX ix_deployment_workspace_id ON deployment (workspace_id);
CREATE INDEX ix_message_user_id ON message (user_id);
CREATE INDEX ix_execution_signals_id ON execution_signals (id);
CREATE INDEX ix_execution_signals_job_id ON execution_signals (job_id);
CREATE UNIQUE INDEX uq_sso_config_slug ON sso_config (slug);
CREATE INDEX ix_message_flow_id_timestamp_id ON message (flow_id, timestamp, id);
CREATE INDEX ix_message_session_id_timestamp_id ON message (session_id, timestamp, id);
CREATE INDEX ix_transaction_user_id ON "transaction" (user_id);
CREATE INDEX ix_transaction_session_id ON "transaction" (session_id);
CREATE INDEX ix_message_flow_id_session_id_timestamp ON message (flow_id, session_id, timestamp);
COMMIT;
