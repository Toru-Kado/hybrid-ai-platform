"""DynamoDB single-table construct for session and message storage.

Uses a single-table design where all access patterns (list sessions by
recency, get session, get messages, add message) are served from one table
with a composite primary key. DynamoDB Streams are enabled for the
OpenSearch indexing pipeline.
"""
from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

from stacks.config import EnvironmentType, ServerlessConfig


class SessionTable(Construct):
    """Single-table DynamoDB design for sessions and messages.

    Key schema:
        PK: USER#{userId}
        SK: SESSION#{sessionId} (session record)
            SESSION#{sessionId}#MSG#{messageId} (message record)

    GSI1 (SessionsByRecency):
        GSI1PK: USER#{userId}
        GSI1SK: {updatedAt}#{sessionId}
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        stack_prefix: str,
    ) -> None:
        super().__init__(scope, construct_id)

        removal_policy = (
            RemovalPolicy.DESTROY
            if config.environment_type == EnvironmentType.DEV
            else RemovalPolicy.RETAIN
        )

        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=f"{stack_prefix}-sessions",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=config.dynamodb_pitr,
            ),
            removal_policy=removal_policy,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # GSI1 enables "list sessions by recency" query pattern:
        # Query GSI1PK = USER#{userId}, ScanIndexForward=False
        # GSI1SK format: {updatedAt}#{sessionId} provides time-based ordering
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # TTL enables automatic expiry of dev/staging data to control costs.
        # TTLIndex supports querying items by expiration for admin tooling.
        if config.dynamodb_ttl_days > 0:
            self.table.add_global_secondary_index(
                index_name="TTLIndex",
                partition_key=dynamodb.Attribute(
                    name="PK", type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="ttl", type=dynamodb.AttributeType.NUMBER
                ),
                projection_type=dynamodb.ProjectionType.KEYS_ONLY,
            )
            # L2 construct doesn't expose TTL directly; use escape hatch
            cfn_table = self.table.node.default_child
            cfn_table.add_property_override(
                "TimeToLiveSpecification",
                {"AttributeName": "ttl", "Enabled": True},
            )
