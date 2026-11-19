# Historical upgrade fixtures

`langflow-1.10.3.sql` is the published-release SQLite dump already used by the upgrade-check reader tests.
It preserves users, projects, saved flow graphs, saved components, and flow versions.
Its recorded revision is `d49cbced8696`.

`langflow-1.10.3-postgres-schema.sql` is a native PostgreSQL schema created by the migrations in tag `v1.10.3` at `c462e44d5a211e3b5836214675c08f291865af02`.
The migration files were extracted from that tag and upgraded to `d49cbced8696` with Alembic on PostgreSQL 18.6.
The schema was exported with `pg_dump --schema-only --no-owner --no-acl --no-comments --no-tablespaces`.
The psql restriction commands and version-specific `transaction_timeout` setting were removed for portable test loading.
Tests restore its native enum, UUID, and constraint definitions into an isolated schema, then copy the SQLite fixture's typed rows into those tables.
No application data comes from a production installation.
