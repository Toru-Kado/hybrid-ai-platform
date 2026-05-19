"""Monitoring construct with CloudWatch alarms, dashboard, and SNS.

Provisions:
- SNS topic for alarm notifications (email subscription if configured)
- Lambda error rate alarms (API + streaming functions)
- Lambda p99 latency alarm for the API handler
- DynamoDB throttle alarm (early indicator of capacity issues)
- CloudWatch dashboard with Lambda, DynamoDB, and concurrency metrics
"""
from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from constructs import Construct

from stacks.config import ServerlessConfig


class Monitoring(Construct):
    """CloudWatch alarms, dashboard, and SNS notifications for the serverless stack."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        stack_prefix: str,
        api_function: lambda_.Function,
        stream_function: lambda_.Function,
        sessions_table: dynamodb.Table,
    ) -> None:
        super().__init__(scope, construct_id)

        # SNS topic for alarm notifications
        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"{stack_prefix}-alarms",
            display_name=f"{stack_prefix} Alarm Notifications",
        )

        if config.alarm_notification_email:
            self.alarm_topic.add_subscription(
                subs.EmailSubscription(config.alarm_notification_email)
            )

        alarm_action = cw_actions.SnsAction(self.alarm_topic)

        # Lambda error alarms
        api_errors_alarm = cloudwatch.Alarm(
            self,
            "ApiErrorsAlarm",
            alarm_name=f"{stack_prefix}-api-errors",
            metric=api_function.metric_errors(period=Duration.minutes(5)),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_errors_alarm.add_alarm_action(alarm_action)

        stream_errors_alarm = cloudwatch.Alarm(
            self,
            "StreamErrorsAlarm",
            alarm_name=f"{stack_prefix}-stream-errors",
            metric=stream_function.metric_errors(period=Duration.minutes(5)),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        stream_errors_alarm.add_alarm_action(alarm_action)

        # Lambda p99 latency alarms
        api_latency_alarm = cloudwatch.Alarm(
            self,
            "ApiLatencyAlarm",
            alarm_name=f"{stack_prefix}-api-p99-latency",
            metric=api_function.metric_duration(
                period=Duration.minutes(5),
                statistic="p99",
            ),
            threshold=10000,  # 10 seconds
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_latency_alarm.add_alarm_action(alarm_action)

        # DynamoDB throttle alarm
        dynamo_throttle_alarm = cloudwatch.Alarm(
            self,
            "DynamoThrottleAlarm",
            alarm_name=f"{stack_prefix}-dynamo-throttles",
            metric=cloudwatch.Metric(
                namespace="AWS/DynamoDB",
                metric_name="ThrottledRequests",
                dimensions_map={"TableName": sessions_table.table_name},
                period=Duration.minutes(5),
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dynamo_throttle_alarm.add_alarm_action(alarm_action)

        # CloudWatch Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"{stack_prefix}-serverless",
        )

        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Lambda Invocations & Errors",
                left=[
                    api_function.metric_invocations(period=Duration.minutes(1)),
                    api_function.metric_errors(period=Duration.minutes(1)),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Stream Lambda Invocations & Errors",
                left=[
                    stream_function.metric_invocations(period=Duration.minutes(1)),
                    stream_function.metric_errors(period=Duration.minutes(1)),
                ],
                width=12,
            ),
        )

        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Lambda Duration (p50, p99)",
                left=[
                    api_function.metric_duration(
                        period=Duration.minutes(1), statistic="p50"
                    ),
                    api_function.metric_duration(
                        period=Duration.minutes(1), statistic="p99"
                    ),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Stream Lambda Duration (p50, p99)",
                left=[
                    stream_function.metric_duration(
                        period=Duration.minutes(1), statistic="p50"
                    ),
                    stream_function.metric_duration(
                        period=Duration.minutes(1), statistic="p99"
                    ),
                ],
                width=12,
            ),
        )

        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="DynamoDB Read/Write Capacity",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ConsumedReadCapacityUnits",
                        dimensions_map={"TableName": sessions_table.table_name},
                        period=Duration.minutes(1),
                        statistic="Sum",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/DynamoDB",
                        metric_name="ConsumedWriteCapacityUnits",
                        dimensions_map={"TableName": sessions_table.table_name},
                        period=Duration.minutes(1),
                        statistic="Sum",
                    ),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="Lambda Concurrent Executions",
                left=[
                    api_function.metric(
                        "ConcurrentExecutions",
                        period=Duration.minutes(1),
                        statistic="Maximum",
                    ),
                    stream_function.metric(
                        "ConcurrentExecutions",
                        period=Duration.minutes(1),
                        statistic="Maximum",
                    ),
                ],
                width=12,
            ),
        )
