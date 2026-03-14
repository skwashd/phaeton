# Aurora Rds Data Api

**Priority:** P2
**Effort:** L
**Gap Analysis Ref:** Item #22

## Overview

The initial database connector version will only support Amazon Aurora databases with the RDS Data API (HTTP API) enabled. This avoids the need for VPC configuration, database drivers, and connection pooling -- the RDS Data API is accessible via the AWS SDK as an HTTP endpoint. The translator should emit SDK integration states (`rds-data:ExecuteStatement`, `rds-data:BatchExecuteStatement`) rather than Lambda-backed handlers. Support for other databases (PostgreSQL, MySQL, MongoDB) is deferred.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A new translator class `DatabaseTranslator` exists that handles database nodes classified as `AWS_NATIVE`.
2. The translator produces `TaskState` with SDK integration resources: `arn:aws:states:::aws-sdk:rdsdata:executeStatement` and `arn:aws:states:::aws-sdk:rdsdata:batchExecuteStatement`.
3. SQL queries from n8n parameters are mapped to the `Sql` parameter.
4. Database connection details (cluster ARN, secret ARN, database name) are parameterized via SSM or CDK context.
5. The translator handles SELECT, INSERT, UPDATE, DELETE operations.
6. `CredentialArtifact` entries are created for database connection secrets.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/database.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (register new translator)
- `n8n-to-sfn/tests/test_database_translator.py` (new)

### Technical Approach

1. **SDK Integration state:**
   ```json
   {
     "Type": "Task",
     "Resource": "arn:aws:states:::aws-sdk:rdsdata:executeStatement",
     "Arguments": {
       "ResourceArn": "${DatabaseClusterArn}",
       "SecretArn": "${DatabaseSecretArn}",
       "Database": "${DatabaseName}",
       "Sql": "SELECT * FROM users WHERE id = :id",
       "Parameters": [
         { "name": "id", "value": { "longValue": "{% $states.input.userId %}" } }
       ]
     }
   }
   ```

2. **n8n database node parameter mapping:**
   - `node.parameters.operation`: `select`, `insert`, `update`, `delete`.
   - `node.parameters.query`: Raw SQL string.
   - `node.parameters.table`: Table name (for ORM-style operations).
   - Connection credentials from `node.credentials`.

3. **Credential handling:**
   - Create `CredentialArtifact` with SSM parameter for the database secret ARN.
   - The secret should be stored in AWS Secrets Manager (referenced by ARN).

### Testing Requirements

- Test SELECT query translation with parameterized values.
- Test INSERT, UPDATE, DELETE operations.
- Test batch statement generation for bulk operations.
- Verify generated ASL references correct SDK integration resources.
- Test credential artifact generation.
