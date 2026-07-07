module "network" {
  source   = "../../modules/network"
  env      = "prod"
  az_count = 3
}

module "secrets" {
  source = "../../modules/secrets"
  env    = "prod"
  names = [
    "db-master-password",
    "db-svc-iam-password",
    "db-svc-logistics-password",
    "db-svc-rto-password",
    "jwt-signing-key",
  ]
}

module "database" {
  source            = "../../modules/database"
  env               = "prod"
  organization_slug = var.supabase_org
  db_region         = var.aws_region
  db_password       = module.secrets.values["db-master-password"]
  bootstrap_sql     = file("${path.module}/../../../compose/db-init/01-schemas-roles.sql")
}

module "broker" {
  source = "../../modules/message-broker"
  env    = "prod"
  plan   = "penguin-3" # 3-node HA quorum cluster
}

module "registry" {
  source = "../../modules/container-registry"
  repos  = ["iam", "logistics", "rto"]
}

module "runtime" {
  source  = "../../modules/app-runtime"
  env     = "prod"
  vpc_id  = module.network.vpc_id
  subnets = module.network.private_subnets

  services = {
    iam = {
      image  = "${module.registry.urls["iam"]}:${var.release}"
      port   = 8000
      cpu    = 512
      memory = 1024
      min    = 2
      max    = 4
      secrets = {
        DATABASE_PASSWORD = module.secrets.arns["db-svc-iam-password"]
        JWT_PRIVATE_KEY   = module.secrets.arns["jwt-signing-key"]
      }
    }
    logistics = {
      image  = "${module.registry.urls["logistics"]}:${var.release}"
      port   = 8000
      cpu    = 1024
      memory = 2048
      min    = 2
      max    = 8
      secrets = {
        DATABASE_PASSWORD = module.secrets.arns["db-svc-logistics-password"]
      }
    }
    rto = {
      image        = "${module.registry.urls["rto"]}:${var.release}"
      port         = 8080
      cpu          = 1024
      memory       = 2048
      min          = 3
      max          = 20
      scale_metric = "connections" # crisis-spike scaling on live WS count
      secrets = {
        DATABASE_PASSWORD = module.secrets.arns["db-svc-rto-password"]
      }
    }
  }
}

module "observability" {
  source          = "../../modules/observability"
  env             = "prod"
  alarm_topic_arn = var.alarm_topic_arn
}
