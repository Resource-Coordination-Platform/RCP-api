variable "env" { type = string }
variable "vpc_id" { type = string }
variable "subnets" { type = list(string) }
variable "services" {
  description = "Per-service runtime spec"
  type = map(object({
    image        = string
    port         = number
    cpu          = number
    memory       = number
    min          = number
    max          = number
    env          = optional(map(string), {})
    secrets      = optional(map(string), {}) # env var -> secrets manager ARN
    scale_metric = optional(string, "cpu")   # "cpu" | "connections"
  }))
}

resource "aws_ecs_cluster" "this" {
  name = "rcp-${var.env}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "rcp-${var.env}-task-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_security_group" "service" {
  name   = "rcp-${var.env}-services"
  vpc_id = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "service" {
  for_each          = var.services
  name              = "/rcp/${var.env}/${each.key}"
  retention_in_days = 30
}

resource "aws_ecs_task_definition" "service" {
  for_each                 = var.services
  family                   = "rcp-${var.env}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.task_execution.arn

  container_definitions = jsonencode([{
    name      = each.key
    image     = each.value.image
    essential = true
    portMappings = [{
      containerPort = each.value.port
      protocol      = "tcp"
    }]
    environment = [for k, v in each.value.env : { name = k, value = v }]
    secrets     = [for k, arn in each.value.secrets : { name = k, valueFrom = arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
        awslogs-region        = data.aws_region.current.name
        awslogs-stream-prefix = each.key
      }
    }
  }])
}

data "aws_region" "current" {}

resource "aws_ecs_service" "service" {
  for_each        = var.services
  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.service[each.key].arn
  desired_count   = each.value.min
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.subnets
    security_groups = [aws_security_group.service.id]
  }

  lifecycle {
    # CI updates the task definition on deploy; Terraform only owns shape
    ignore_changes = [task_definition, desired_count]
  }
}

resource "aws_appautoscaling_target" "service" {
  for_each           = var.services
  max_capacity       = each.value.max
  min_capacity       = each.value.min
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.service[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# CPU-based policy for the FastAPI services. RTO instead scales on the
# custom ActiveConnectionCount metric it publishes (connection storms
# precede CPU load in a crisis) — see modules/observability.
resource "aws_appautoscaling_policy" "cpu" {
  for_each = { for k, v in var.services : k => v if v.scale_metric == "cpu" }

  name               = "${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.service[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.service[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.service[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

output "cluster_name" { value = aws_ecs_cluster.this.name }
output "security_group_id" { value = aws_security_group.service.id }
