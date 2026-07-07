variable "env" { type = string }
variable "names" {
  description = "Logical secret names, e.g. db-svc-iam-password, jwt-signing-key"
  type        = list(string)
}

# Passwords are generated here and written straight to Secrets Manager —
# they never appear in tfvars. (They do live in state; the state bucket is
# KMS-encrypted and access-controlled.)
resource "random_password" "generated" {
  for_each = toset(var.names)
  length   = 32
  special  = false
}

resource "aws_secretsmanager_secret" "this" {
  for_each = toset(var.names)
  name     = "rcp/${var.env}/${each.value}"
}

resource "aws_secretsmanager_secret_version" "this" {
  for_each      = toset(var.names)
  secret_id     = aws_secretsmanager_secret.this[each.value].id
  secret_string = random_password.generated[each.value].result

  lifecycle {
    # rotate via the console/CLI or a rotation lambda, not by re-apply
    ignore_changes = [secret_string]
  }
}

output "arns" {
  value = { for name, secret in aws_secretsmanager_secret.this : name => secret.arn }
}

output "values" {
  value     = { for name, pw in random_password.generated : name => pw.result }
  sensitive = true
}
