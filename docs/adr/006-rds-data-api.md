# ADR-006: RDS Data API for Database Support

**Status:** Accepted
**Date:** 2025-06-01

## Context

n8n supports database nodes for PostgreSQL, MySQL, and Microsoft SQL Server. These nodes execute SQL queries as part of workflow logic. When translating database operations to Step Functions, the pipeline must choose how the state machine interacts with databases.

Two approaches were considered:
- **VPC-bound database drivers** — Lambda functions with native database drivers (psycopg2, mysql-connector) running inside a VPC with direct network access to the database. This is the traditional approach but requires VPC configuration, NAT gateways, security groups, and subnet management.
- **RDS Data API** — an HTTP-based API that allows Step Functions to call database operations directly via AWS SDK integrations (`aws-sdk:rdsdata`), without requiring the state machine or Lambda functions to be inside a VPC.

## Decision

Translate database nodes to RDS Data API calls using the Step Functions `aws-sdk:rdsdata` service integration. The database translator generates ASL `TaskState` definitions that call either `executeStatement` (single query) or `batchExecuteStatement` (multiple queries) with parameters for `sql`, `resourceArn`, `database`, and `secretArn`.

Key implementation details:
- SQL is constructed from n8n's ORM-style parameters (table name, columns, where clauses) using dedicated SQL builder functions.
- Database credentials are stored as SSM parameters at `/n8n-sfn/{workflow-name}/{credential-type}` and referenced via `CredentialArtifact` objects.
- Retry configuration defaults to 3 attempts with a 2-second initial interval, 2.0 backoff rate, and 30-second maximum delay.
- Supported database nodes: `n8n-nodes-base.postgres`, `n8n-nodes-base.mySql`, `n8n-nodes-base.microsoftSql`.

## Consequences

### Positive
- No VPC configuration required — the state machine calls RDS Data API over HTTPS, dramatically simplifying the generated infrastructure.
- Direct Step Functions SDK integration — database calls are ASL states, not Lambda functions, reducing Lambda cold starts and code complexity.
- Built-in retry and error handling via ASL `Retry` and `Catch` blocks.
- Credentials managed through AWS Secrets Manager (referenced by `secretArn`), following AWS security best practices.

### Negative
- RDS Data API is only available for Amazon Aurora (MySQL and PostgreSQL compatible) and Aurora Serverless, not for standard RDS instances or self-hosted databases.
- Data API has a 1 MB response size limit and a 1,000-row limit per request, which may not be sufficient for large result sets.
- Not all SQL features are exposed through the Data API (e.g., multi-statement transactions have limitations).

### Neutral
- Users with databases that are not Aurora-compatible will need to use the VPC-bound approach, which can be added as an alternative translator in the future.
- The SQL builder functions handle the translation from n8n's ORM-style parameters to raw SQL, but complex queries authored directly in n8n's SQL editor are passed through as-is.
