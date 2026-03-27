data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  sanitized_project_name = replace(lower(var.project_name), "_", "-")
  role_name              = coalesce(var.role_name_override, "${local.sanitized_project_name}-${var.environment}-bedrock-runtime")
  trusted_principal_arns = length(var.trusted_principal_arns) > 0 ? var.trusted_principal_arns : [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
  ]
  foundation_model_arns = [
    for model_id in var.foundation_model_ids :
    "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${model_id}"
  ]
  invoke_resources = length(local.foundation_model_arns) + length(var.inference_profile_arns) > 0 ? concat(
    local.foundation_model_arns,
    var.inference_profile_arns
  ) : ["*"]
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    sid     = "AllowTrustedPrincipals"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = local.trusted_principal_arns
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

data "aws_iam_policy_document" "runtime_access" {
  statement {
    sid    = "BedrockModelMetadata"
    effect = "Allow"
    actions = [
      "bedrock:GetFoundationModel",
      "bedrock:ListFoundationModels"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream"
    ]
    resources = local.invoke_resources
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
    sid    = "CreateLogGroup"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup"
    ]
    resources = ["*"]
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
}

resource "aws_iam_role_policy" "runtime_access" {
  name   = "${local.role_name}-access"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.runtime_access.json
}
