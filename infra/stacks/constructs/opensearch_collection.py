"""OpenSearch Serverless construct for full-text message search.

Conditionally deployed (staging/prod only) to provide real full-text search
with fuzzy matching and relevance scoring. The pipeline works as follows:
DynamoDB Streams -> search-indexer Lambda -> OpenSearch Serverless collection.

Dev environments skip this entirely and fall back to DynamoDB scan-based
search to avoid the ~$700/month baseline cost of OpenSearch Serverless.
"""
from __future__ import annotations

import json
from pathlib import Path

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_opensearchserverless as oss
from constructs import Construct

from stacks.config import ServerlessConfig


class OpenSearchCollection(Construct):
    """OpenSearch Serverless collection for message full-text search.

    Creates a SEARCH-type collection with public network access.
    Deploys a search-indexer Lambda that processes DynamoDB Streams
    events and indexes messages into the collection.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        stack_prefix: str,
        lambda_layer: lambda_.LayerVersion,
        sessions_table: dynamodb.Table,
        log_retention: logs.RetentionDays,
    ) -> None:
        super().__init__(scope, construct_id)

        collection_name = f"{stack_prefix}-messages"
        # OpenSearch Serverless collection names limited to 32 chars
        if len(collection_name) > 32:
            collection_name = collection_name[:32].rstrip("-")

        # Encryption policy
        encryption_policy = oss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "Resource": [f"collection/{collection_name}"],
                            "ResourceType": "collection",
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        # Network policy - public access
        network_policy = oss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "ResourceType": "collection",
                            }
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        self.collection = oss.CfnCollection(
            self,
            "Collection",
            name=collection_name,
            type="SEARCH",
            description=f"Full-text search index for {stack_prefix} messages",
        )
        self.collection.add_dependency(encryption_policy)
        self.collection.add_dependency(network_policy)

        # Search indexer Lambda
        indexer_log_group = logs.LogGroup(
            self,
            "IndexerLogGroup",
            log_group_name=f"/aws/lambda/{stack_prefix}-search-indexer",
            retention=log_retention,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.indexer_function = lambda_.Function(
            self,
            "SearchIndexer",
            function_name=f"{stack_prefix}-search-indexer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.lambda_handlers.search_indexer.handler",
            code=lambda_.Code.from_asset(
                str(Path(__file__).resolve().parents[3] / "app"),
            ),
            layers=[lambda_layer],
            memory_size=256,
            timeout=Duration.seconds(60),
            environment={
                "OPENSEARCH_ENDPOINT": self.collection.attr_collection_endpoint,
                "OPENSEARCH_INDEX_NAME": "messages",
                "POWERTOOLS_SERVICE_NAME": f"{stack_prefix}-indexer",
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE if config.enable_xray else lambda_.Tracing.DISABLED,
            log_group=indexer_log_group,
        )

        # Grant indexer access to the OpenSearch collection
        data_access_policy = oss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name=f"{collection_name}-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                                "ResourceType": "index",
                            },
                            {
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                ],
                                "ResourceType": "collection",
                            },
                        ],
                        "Principal": [self.indexer_function.role.role_arn],
                    }
                ]
            ),
        )

        self.indexer_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[self.collection.attr_arn],
            )
        )

        # DynamoDB Streams event source — processes message writes in near-real-time.
        # TRIM_HORIZON starts from the oldest available record on first deploy.
        # bisect_batch_on_error isolates poison-pill records that cause failures.
        self.indexer_function.add_event_source(
            event_sources.DynamoEventSource(
                sessions_table,
                starting_position=lambda_.StartingPosition.TRIM_HORIZON,
                batch_size=25,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                bisect_batch_on_error=True,
            )
        )
