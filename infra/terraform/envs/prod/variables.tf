variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "release" {
  description = "Image tag to deploy (CI normally owns deploys; this is the initial/base tag)"
  type        = string
}

variable "supabase_org" { type = string }

variable "supabase_access_token" {
  type      = string
  sensitive = true
}

variable "cloudamqp_api_key" {
  type      = string
  sensitive = true
}

variable "alarm_topic_arn" { type = string }
