terraform {
  backend "s3" {
    bucket         = "rcp-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "rcp-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws       = { source = "hashicorp/aws", version = "~> 5.0" }
    cloudamqp = { source = "cloudamqp/cloudamqp", version = "~> 1.30" }
    supabase  = { source = "supabase/supabase", version = "~> 1.0" }
    random    = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "cloudamqp" {
  apikey = var.cloudamqp_api_key
}

provider "supabase" {
  access_token = var.supabase_access_token
}
