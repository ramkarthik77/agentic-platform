variable "region" { type = string }
variable "name" {
  type    = string
  default = "aaaem-agentic"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.name))
    error_message = "Use a lowercase resource name of 3 to 20 characters."
  }
}
variable "vpc_id" { type = string }
variable "private_subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Provide private subnets in at least two availability zones."
  }
}
variable "load_balancer_subnet_ids" { type = list(string) }
variable "internal_load_balancer" {
  type    = bool
  default = true
}
variable "allowed_client_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.allowed_client_cidrs) > 0 && alltrue([for cidr in var.allowed_client_cidrs : can(cidrhost(cidr, 0))])
    error_message = "Provide the explicit network CIDRs allowed to reach the workspace."
  }
}
variable "hostname" { type = string }
variable "certificate_arn" { type = string }
variable "image_uri" {
  type = string
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image_uri))
    error_message = "Use an immutable ECR image URI with its sha256 digest."
  }
}
variable "database_security_group_id" { type = string }
variable "secret_arns" {
  description = "Environment variable name -> Secrets Manager ARN (optionally including a JSON key selector). No secret values."
  type        = map(string)
  validation {
    condition = alltrue([for key in ["DATABASE_URL", "AAAEM_WORKSPACE_JSON", "AAAEM_REGISTRY_JSON"] : contains(keys(var.secret_arns), key)]) && alltrue([
      for key, arn in var.secret_arns : can(regex("^[A-Z][A-Z0-9_]+$", key)) && can(regex("^arn:[^:]+:secretsmanager:[^:]+:[0-9]{12}:secret:", arn))
    ])
    error_message = "Provide valid secret ARNs, including DATABASE_URL, AAAEM_WORKSPACE_JSON, and AAAEM_REGISTRY_JSON."
  }
}
variable "secret_kms_key_arns" {
  type    = list(string)
  default = []
}
variable "model_provider" {
  type    = string
  default = "fixture"
  validation {
    condition     = contains(["fixture", "bedrock", "openai_compatible"], var.model_provider)
    error_message = "Select a supported summary provider. Fixture means deterministic text, not synthetic live integrations."
  }
}
variable "model_id" {
  type    = string
  default = ""
}
variable "model_endpoint" {
  type    = string
  default = ""
}
variable "bedrock_resource_arns" {
  type    = list(string)
  default = []
}
variable "api_count" {
  type    = number
  default = 1
  validation {
    condition     = var.api_count >= 1 && var.api_count <= 4 && floor(var.api_count) == var.api_count
    error_message = "Use 1–4 API replicas for this starter."
  }
}
variable "worker_count" {
  type    = number
  default = 1
  validation {
    condition     = var.worker_count >= 1 && var.worker_count <= 4 && floor(var.worker_count) == var.worker_count
    error_message = "Use 1–4 workers for this starter; validate service quotas before increasing concurrency."
  }
}
