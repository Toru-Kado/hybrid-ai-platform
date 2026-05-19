"""CloudFront + S3 construct for SPA hosting with API origins.

Creates a single CloudFront distribution serving three origins:
1. S3 bucket (React SPA via OAC) — default behavior
2. API Gateway HTTP API — /api/* except streaming
3. Lambda Function URL — /api/chat/stream (SSE streaming)

This single-distribution approach eliminates CORS complexity since the
frontend and API share the same origin domain.
"""
from __future__ import annotations

from aws_cdk import Duration, Fn, RemovalPolicy
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct

from stacks.config import EnvironmentType, ServerlessConfig


class CloudFrontDistribution(Construct):
    """CloudFront distribution serving S3 SPA + API Gateway + Function URL.

    Behaviors:
        - Default (/) -> S3 bucket (React SPA, with 403/404 -> /index.html)
        - /api/* -> API Gateway HTTP API origin (no cache)
        - /api/chat/stream -> Lambda Function URL origin (no cache)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        stack_prefix: str,
        http_api: apigwv2.HttpApi,
        function_url: lambda_.FunctionUrl,
    ) -> None:
        super().__init__(scope, construct_id)

        removal_policy = (
            RemovalPolicy.DESTROY
            if config.environment_type == EnvironmentType.DEV
            else RemovalPolicy.RETAIN
        )

        # S3 bucket for Vite build output — all public access blocked,
        # CloudFront accesses via Origin Access Control (OAC)
        self.spa_bucket = s3.Bucket(
            self,
            "SpaBucket",
            bucket_name=f"{stack_prefix}-spa-assets",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            auto_delete_objects=config.environment_type == EnvironmentType.DEV,
            removal_policy=removal_policy,
        )

        # OAC (Origin Access Control) replaces legacy OAI for S3 access
        oac = cloudfront.S3OriginAccessControl(
            self,
            "OAC",
            signing=cloudfront.Signing.SIGV4_NO_OVERRIDE,
        )

        s3_origin = origins.S3BucketOrigin.with_origin_access_control(
            self.spa_bucket,
            origin_access_control=oac,
        )

        # Parse API Gateway URL for origin
        api_origin = origins.HttpOrigin(
            f"{http_api.http_api_id}.execute-api.{http_api.stack.region}.amazonaws.com",
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        )

        # Extract the domain from the Function URL token (https://<domain>/)
        function_url_domain = Fn.select(2, Fn.split("/", function_url.url))
        stream_origin = origins.HttpOrigin(
            function_url_domain,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        )

        # Use AWS-managed policies for API origins:
        # - CACHING_DISABLED: no caching, forwards all query strings
        # - ALL_VIEWER_EXCEPT_HOST_HEADER: forwards all viewer headers
        #   (including Authorization) and query strings to the origin
        api_cache_policy = cloudfront.CachePolicy.CACHING_DISABLED
        api_origin_request_policy = cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER

        # Custom domain requires both a domain name and an ACM certificate
        # in us-east-1 (CloudFront global requirement)
        domain_names = None
        certificate = None
        if config.custom_domain_name and config.custom_domain_certificate_arn:
            domain_names = [config.custom_domain_name]
            certificate = acm.Certificate.from_certificate_arn(
                self,
                "Certificate",
                config.custom_domain_certificate_arn,
            )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"{stack_prefix} SPA + API distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
            ),
            additional_behaviors={
                "/api/chat/stream": cloudfront.BehaviorOptions(
                    origin=stream_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    cache_policy=api_cache_policy,
                    origin_request_policy=api_origin_request_policy,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
                "/api/*": cloudfront.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    cache_policy=api_cache_policy,
                    origin_request_policy=api_origin_request_policy,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
            },
            domain_names=domain_names,
            certificate=certificate,
            # SPA routing: redirect S3 403/404 errors to index.html so that
            # client-side React Router handles the path resolution
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            web_acl_id=config.waf_web_acl_arn,
        )
