"""Cognito User Pool construct for authentication.

Creates a Cognito User Pool with email-based sign-up, configurable MFA,
and an SPA-compatible app client (no client secret). The hosted UI domain
provides a ready-to-use login page; custom domains can be configured
separately at the CloudFront level.
"""
from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from constructs import Construct

from stacks.config import EnvironmentType, ServerlessConfig


class CognitoAuth(Construct):
    """Cognito User Pool with email-based sign-up and JWT support.

    Configurable MFA (off/optional/required), self-registration,
    and produces a user pool client suitable for SPA usage (no secret).
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

        mfa_map = {
            "off": cognito.Mfa.OFF,
            "optional": cognito.Mfa.OPTIONAL,
            "required": cognito.Mfa.REQUIRED,
        }

        removal_policy = (
            RemovalPolicy.DESTROY
            if config.environment_type == EnvironmentType.DEV
            else RemovalPolicy.RETAIN
        )

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{stack_prefix}-users",
            self_sign_up_enabled=config.cognito_self_signup,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            mfa=mfa_map.get(config.cognito_mfa, cognito.Mfa.OPTIONAL),
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=False, otp=True
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
                temp_password_validity=Duration.days(7),
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=removal_policy,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
        )

        # SPA client: no secret (public client), uses SRP for secure
        # password-based auth without transmitting the password directly.
        # OAuth2 authorization_code flow for hosted UI integration.
        self.user_pool_client = self.user_pool.add_client(
            "SpaClient",
            user_pool_client_name=f"{stack_prefix}-spa",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=False,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=False,
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
            ),
            id_token_validity=Duration.hours(1),
            access_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
        )

        self.user_pool_domain = self.user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{stack_prefix}-auth",
            ),
        )
