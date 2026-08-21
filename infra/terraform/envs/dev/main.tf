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



module "broker" {
  source = "../../modules/message-broker"
  env    = "dev"
  plan   = "lemur" # single node, free tier
}

module "registry" {
  source = "../../modules/container-registry"
  repos  = ["iam", "logistics", "rto", "analytics", "volunteer", "gateway"]
}

module "runtime" {
  source         = "../../modules/app-runtime"
  env            = "dev"
  vpc_id         = module.network.vpc_id
  subnets        = module.network.private_subnets
  public_subnets = module.network.public_subnets

  services = {
    iam       = { image = "${module.registry.urls["iam"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 1, env = { DATABASE_URL = var.manual_db_url, RABBITMQ_URL = module.broker.url }, secrets = { JWT_PRIVATE_KEY = module.secrets.arns["jwt-signing-key"] } }
    logistics = { image = "${module.registry.urls["logistics"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 2, env = { DATABASE_URL = var.manual_db_url, RABBITMQ_URL = module.broker.url } }
    rto       = { image = "${module.registry.urls["rto"]}:${var.release}", port = 8080, cpu = 256, memory = 512, min = 1, max = 2, scale_metric = "connections", env = { DATABASE_URL = var.manual_db_url, RABBITMQ_URL = module.broker.url } }
    analytics = { image = "${module.registry.urls["analytics"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 1, env = { DATABASE_URL = var.manual_db_url, RABBITMQ_URL = module.broker.url } }
    volunteer = { image = "${module.registry.urls["volunteer"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 1, env = { DATABASE_URL = var.manual_db_url, RABBITMQ_URL = module.broker.url } }
    gateway   = { image = "${module.registry.urls["gateway"]}:${var.release}", port = 8000, cpu = 256, memory = 512, min = 1, max = 1, public = true, env = { ENVIRONMENT = "aws", IAM_URL = "http://iam:8000", LOGISTICS_URL = "http://logistics:8000", ANALYTICS_URL = "http://analytics:8000", VOLUNTEER_URL = "http://volunteer:8000", RTO_URL = "http://rto:8080" } }
  }
}

output "alb_url" {
  value = module.runtime.alb_url
}
