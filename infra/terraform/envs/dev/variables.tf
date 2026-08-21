variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "release" {
  description = "Image tag to deploy (CI normally owns deploys; this is the initial/base tag)"
  type        = string
}

variable "manual_db_url" {
  type        = string
  sensitive   = true
  description = "Connection string for the manually created Supabase DB"
}

variable "cloudamqp_api_key" {
  type      = string
  sensitive = true
}

