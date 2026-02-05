# Terraform Outputs for Polymarket Arbitrage Bot

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.bot.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.bot.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.bot.private_ip
}

output "elastic_ip" {
  description = "Elastic IP address (if enabled)"
  value       = var.use_elastic_ip ? aws_eip.bot_eip[0].public_ip : null
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.bot_sg.id
}

output "iam_role_arn" {
  description = "IAM role ARN"
  value       = aws_iam_role.bot_role.arn
}

output "secrets_manager_secret_name" {
  description = "Secrets Manager secret name for credentials"
  value       = aws_secretsmanager_secret.bot_credentials.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.bot_logs.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.bot_alerts.arn
}

output "prometheus_url" {
  description = "Prometheus metrics URL"
  value       = "http://${aws_instance.bot.public_ip}:9090/metrics"
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_instance.bot.public_ip}"
}
