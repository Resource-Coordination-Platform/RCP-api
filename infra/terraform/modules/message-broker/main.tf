terraform {
  required_providers {
    cloudamqp = { source = "cloudamqp/cloudamqp" }
  }
}

variable "env" { type = string }
variable "plan" {
  description = "CloudAMQP plan: lemur (dev, free) / penguin-3 (prod HA cluster)"
  type        = string
}
variable "region" {
  type    = string
  default = "amazon-web-services::ap-south-1"
}

resource "cloudamqp_instance" "this" {
  name   = "rcp-${var.env}"
  plan   = var.plan
  region = var.region
  tags   = ["rcp", var.env]
}

# Topology (rcp.events, rcp.dlx, quorum queues, bindings) is the same
# definitions file used locally. Import it once per environment:
#   curl -u <user>:<pass> -XPOST -H 'Content-Type: application/json' \
#     https://<host>/api/definitions -d @../../compose/rabbitmq/definitions.json
# Services also declare their topology idempotently on startup, so a fresh
# broker converges even without the import.

output "url" {
  value     = cloudamqp_instance.this.url
  sensitive = true
}
output "host" { value = cloudamqp_instance.this.host }
