# Migration Scripts

## migrate_published_flows.py

A reusable standalone Python script to migrate published flow data between PostgreSQL database environments.

### Use Cases
- DEV → QA
- QA → QA-E2E
- QA-E2E → PROD

### Prerequisites
- Python 3.8+
- `psycopg2` library installed (`pip install psycopg2-binary`)
- Access to both source and target PostgreSQL databases
- Migration user must exist in the target database
- Required folders must exist in target database:
  - "Marketplace Agent" (shared folder)
  - "Starter Project" (for the migration user)

### What It Migrates
For each `published_flow` in the source database, the script creates:
1. **Two flows** in the `flow` table:
   - Original flow in "Starter Project" folder
   - Published/cloned flow in "Marketplace Agent" folder
2. **One `published_flow` record**
3. **One `published_flow_input_sample` record** (if source has data)
4. **One `version_flow_input_sample` record**
5. **One `flow_version` record**

### Usage

```bash
python scripts/migrate_published_flows.py \
  --source "postgresql://user:pass@source-host:5432/source_db" \
  --target "postgresql://user:pass@target-host:5432/target_db" \
  --email "rishikant.kumar@autonomize.ai"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--source` | Yes | Source database connection string |
| `--target` | Yes | Target database connection string |
| `--email` | Yes | Email of the migration user in target database |
| `--dry-run` | No | Run without making changes (preview mode) |

### Examples

**Dry run (preview without changes):**
```bash
python scripts/migrate_published_flows.py \
  --source "postgresql://rishi:@localhost:5432/genesis-studio-dev" \
  --target "postgresql://rishi:@localhost:5432/genesis-studio-qa" \
  --email "rishikant.kumar@autonomize.ai" \
  --dry-run
```

**Actual migration:**
```bash
python scripts/migrate_published_flows.py \
  --source "postgresql://rishi:@localhost:5432/genesis-studio-dev" \
  --target "postgresql://rishi:@localhost:5432/genesis-studio-qa" \
  --email "rishikant.kumar@autonomize.ai"
```

### Validation Rules
The script will **fail with an error** if:
- "Marketplace Agent" folder doesn't exist in target
- "Starter Project" folder doesn't exist for the migration user in target
- Migration user email doesn't exist in target database

### Error Handling
- Each `published_flow` migration is wrapped in a transaction
- Individual failures don't stop the entire migration
- Success/failure is logged for each record
- Summary is provided at the end

### Output
The script provides detailed logging:
```
============================================================
Published Flow Migration Script
============================================================
Source: localhost:5432/genesis-studio-dev
Target: localhost:5432/genesis-studio-qa
Migration User: rishikant.kumar@autonomize.ai
Dry Run: False
============================================================

Validating target database...
Found user: rishikant.kumar@autonomize.ai (ID: xxx-xxx-xxx)
Found folder: Marketplace Agent (ID: xxx-xxx-xxx)
Found folder: Starter Project (ID: xxx-xxx-xxx)

Fetching published flows from source...
Found 10 published flows to migrate

[1/10] Migrating: My Flow (ID: xxx-xxx-xxx)
  Created Flow 1 (Starter Project): xxx-xxx-xxx
  Created Flow 2 (Marketplace Agent): xxx-xxx-xxx
  Created published_flow: xxx-xxx-xxx
  ...

============================================================
Migration Summary
============================================================
Total: 10
Success: 10
Failed: 0
============================================================
```
