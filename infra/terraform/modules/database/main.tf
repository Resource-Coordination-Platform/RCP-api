terraform {
  required_providers {
    supabase = { source = "supabase/supabase" }
  }
}

variable "env" { type = string }
variable "organization_slug" { type = string }
variable "db_region" {
  type    = string
  default = "ap-south-1"
}
variable "db_password" {
  type      = string
  sensitive = true
}
variable "bootstrap_sql" {
  description = "Schema/role bootstrap (db-init/01-schemas-roles.sql) run post-provision"
  type        = string
}

resource "supabase_project" "this" {
  organization_id   = var.organization_slug
  name              = "rcp-${var.env}"
  database_password = var.db_password
  region            = var.db_region
}

# Post-provision bootstrap: creates schema_iam / schema_logistics /
# schema_rto and the svc_* roles. Requires psql on the runner; service
# role passwords are substituted from the secrets module by the caller.
resource "terraform_data" "bootstrap" {
  triggers_replace = [sha256(var.bootstrap_sql)]

  provisioner "local-exec" {
    command     = "psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -f -"
    interpreter = ["bash", "-c"]
    environment = {
      DATABASE_URL = "postgresql://postgres:${var.db_password}@db.${supabase_project.this.id}.supabase.co:5432/postgres"
    }
  }

  depends_on = [supabase_project.this]
}

output "project_id" { value = supabase_project.this.id }
output "db_host" { value = "db.${supabase_project.this.id}.supabase.co" }
