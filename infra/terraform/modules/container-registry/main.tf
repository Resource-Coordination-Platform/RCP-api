variable "repos" { type = list(string) }

resource "aws_ecr_repository" "this" {
  for_each             = toset(var.repos)
  name                 = "rcp/${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

output "urls" {
  value = { for name, repo in aws_ecr_repository.this : name => repo.repository_url }
}
