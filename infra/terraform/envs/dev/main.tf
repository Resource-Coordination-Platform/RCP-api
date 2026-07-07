# Dev: same modules, small sizes, single-node broker.

module "network" {
  source   = "../../modules/network"
  env      = "dev"
  az_count = 2
}

module "secrets" {
  source = "../../modules/secrets"
  env    = "dev"
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
  env               = "dev"
  organization_slug = var.supabase_org
  db_region         = var.aws_region
  db_password       = module.secrets.values["db-master-password"]
  bootstrap_sql     = file("${path.module}/../../../compose/db-init/01-schemas-roles.sql")
}

module "broker" {
  source = "../../modules/message-broker"
  env    = "dev"
  plan   = "lemur" # single node, free tier
}

module "registry" {
  source = "../../modules/container-registry"
  repos  = ["iam", "logistics", "rto"]
}

module "runtime" {
  source  = "../../modules/app-runtime"
  env     = "dev"
  vpc_id  = module.network.vpc_id
  subnets = module.network.private_subnets

  services = {
    iam       = { image = "${module.registry.urls["iam"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 1 }
    logistics = { image = "${module.registry.urls["logistics"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 2 }
    rto       = { image = "${module.registry.urls["rto"]}:${var.release}", port = 8080, cpu = 256, memory = 512, min = 1, max = 2, scale_metric = "connections" }
  }
}
