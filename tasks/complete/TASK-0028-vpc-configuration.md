# Vpc Configuration

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #28

## Overview

Lambda functions that access RDS, ElastiCache, or other VPC-bound resources need VPC configuration (subnets, security groups). The packager generates no VPC-related CDK constructs. Workflows targeting private resources will fail with connection timeouts because the Lambda functions cannot reach VPC-bound endpoints.

## Dependencies

- **Blocked by:** TASK-0022 (Aurora RDS is the first VPC-bound resource)
- **Blocks:** None

## Acceptance Criteria

1. The generated CDK stack includes VPC configuration when the workflow uses VPC-bound resources.
2. Lambda functions that need VPC access are configured with `vpc`, `vpc_subnets`, and `security_groups` parameters.
3. The VPC configuration is parameterized via CDK context or stack parameters (not hardcoded).
4. Security groups are created with appropriate ingress/egress rules for the target services.
5. Lambda functions in a VPC have a NAT Gateway path for outbound internet access (if needed for non-VPC services).
6. The packager detects when VPC configuration is needed based on the services referenced in the workflow.
7. `uv run pytest` passes in `packager/`.
8. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`
- `packager/src/n8n_to_sfn_packager/models/inputs.py` (may need VPC config fields)
- `packager/tests/` (update/add tests)

### Technical Approach

1. **VPC detection:**
   - Check if any Lambda function or SDK integration targets a VPC-bound service (RDS, ElastiCache, Redshift, etc.).
   - Maintain a set of services that require VPC access.

2. **CDK VPC constructs:**
   ```python
   # Look up existing VPC
   vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=self.node.try_get_context("vpc_id"))

   # Or create a new VPC
   vpc = ec2.Vpc(self, "PhaethonVPC", max_azs=2, nat_gateways=1)

   # Security group for Lambda
   lambda_sg = ec2.SecurityGroup(self, "LambdaSG", vpc=vpc)

   # Lambda with VPC
   fn = lambda_.Function(self, "Handler",
       vpc=vpc,
       vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
       security_groups=[lambda_sg],
       ...
   )
   ```

3. **Parameterization:**
   - Use CDK context variables: `vpc_id`, `subnet_ids`, `security_group_ids`.
   - Allow users to provide existing VPC details or create a new VPC.
   - Document the VPC requirements in the generated package.

4. **Service-specific security group rules:**
   - RDS: allow outbound TCP 3306 (MySQL) or 5432 (PostgreSQL).
   - ElastiCache: allow outbound TCP 6379 (Redis) or 11211 (Memcached).

### Testing Requirements

- Test CDK code generation with VPC-bound resources.
- Test CDK code generation without VPC-bound resources (no VPC constructs).
- Test VPC lookup from context variables.
- Test security group rule generation for different services.
