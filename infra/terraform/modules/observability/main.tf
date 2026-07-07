variable "env" { type = string }
variable "alarm_topic_arn" {
  description = "SNS topic for paging"
  type        = string
}
variable "dlq_names" {
  type    = list(string)
  default = ["dlq.logistics.iam-events", "dlq.rto.domain-events"]
}

# The crisis-readiness alarms from the blueprint (§6.3). Broker metrics
# arrive via the CloudAMQP CloudWatch integration; outbox lag and WS
# connection counts are custom metrics emitted by the services.

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each            = toset(var.dlq_names)
  alarm_name          = "rcp-${var.env}-dlq-depth-${replace(each.value, ".", "-")}"
  namespace           = "RCP/Broker"
  metric_name         = "QueueDepth"
  dimensions          = { Queue = each.value }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_description   = "Dead-lettered events waiting — a consumer is failing"
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "outbox_lag" {
  for_each            = toset(["iam", "logistics"])
  alarm_name          = "rcp-${var.env}-outbox-lag-${each.value}"
  namespace           = "RCP/Outbox"
  metric_name         = "UnpublishedAgeSeconds"
  dimensions          = { Service = each.value }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 60
  comparison_operator = "GreaterThanThreshold"
  alarm_description   = "Outbox rows older than 60s — broker unreachable or relay down"
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "ws_saturation" {
  alarm_name          = "rcp-${var.env}-ws-connection-saturation"
  namespace           = "RCP/RTO"
  metric_name         = "ActiveConnectionCount"
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 3
  threshold           = 8000 # per-task soft ceiling; also drives RTO autoscaling
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.alarm_topic_arn]
  treat_missing_data  = "notBreaching"
}
