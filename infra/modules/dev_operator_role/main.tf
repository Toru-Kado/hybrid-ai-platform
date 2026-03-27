data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  sanitized_project_name = trim(
    replace(
      replace(
        replace(
          replace(lower(var.project_name), "_", "-"),
          " ",
          "-"
        ),
        ".",
        "-"
      ),
      "/",
      "-"
    ),
    "-"
  )
  sanitized_environment = trim(
    replace(
      replace(
        replace(
          replace(lower(var.environment), "_", "-"),
          " ",
          "-"
        ),
        ".",
        "-"
      ),
      "/",
      "-"
    ),
    "-"
  )
  role_name = coalesce(
    var.role_name_override,
    substr("${local.sanitized_project_name}-${local.sanitized_environment}-operator", 0, 64)
  )
  operator_user_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/${var.operator_user_name}"
  bedrock_invoke_resource_arns = [
    for model_id in var.foundation_model_ids :
    startswith(model_id, "arn:")
    ? model_id
    : "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${model_id}"
  ]
  invoke_resources = length(local.bedrock_invoke_resource_arns) + length(var.inference_profile_arns) > 0 ? concat(
    local.bedrock_invoke_resource_arns,
    var.inference_profile_arns
  ) : ["*"]
  assume_policy_name = substr("${local.role_name}-assume", 0, 128)
  access_policy_name = substr("${local.role_name}-access", 0, 128)
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "AllowOperatorUser"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [local.operator_user_arn]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = merge(
    var.tags,
    {
      Name = local.role_name
    }
  )
}

data "aws_iam_policy_document" "operator_access" {
  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    resources = local.invoke_resources
  }

  dynamic "statement" {
    for_each = length(var.guardrail_arns) > 0 ? [1] : []

    content {
      sid    = "ApplyBedrockGuardrails"
      effect = "Allow"
      actions = [
        "bedrock:ApplyGuardrail"
      ]
      resources = var.guardrail_arns
    }
  }

  statement {
    sid    = "ListAssetsBucket"
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket"
    ]
    resources = [var.assets_bucket_arn]
  }

  statement {
    sid    = "ManageAssetsBucketObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload"
    ]
    resources = ["${var.assets_bucket_arn}/*"]
  }

  statement {
    sid    = "WriteAssistantLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents"
    ]
    resources = [
      var.log_group_arn,
      "${var.log_group_arn}:*"
    ]
  }

  dynamic "statement" {
    for_each = var.enable_observability_access ? [1] : []

    content {
      sid    = "ReadBedrockObservability"
      effect = "Allow"
      actions = [
        "bedrock:GetInferenceProfile",
        "bedrock:ListFoundationModels",
        "bedrock:ListGuardrails",
        "bedrock:ListInferenceProfiles",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "servicequotas:GetAWSDefaultServiceQuota",
        "servicequotas:GetServiceQuota",
        "servicequotas:ListAWSDefaultServiceQuotas",
        "servicequotas:ListServiceQuotas"
      ]
      resources = ["*"]
    }
  }
}

resource "aws_iam_role_policy" "operator_access" {
  name   = local.access_policy_name
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.operator_access.json
}

data "aws_iam_policy_document" "allow_user_assume_role" {
  statement {
    sid       = "AllowAssumeOperatorRole"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = [aws_iam_role.this.arn]
  }
}

resource "aws_iam_user_policy" "allow_assume_role" {
  name   = local.assume_policy_name
  user   = var.operator_user_name
  policy = data.aws_iam_policy_document.allow_user_assume_role.json
}
