output "workspace_url" { value = "https://${var.hostname}" }
output "load_balancer_dns_name" { value = aws_lb.app.dns_name }
output "load_balancer_zone_id" { value = aws_lb.app.zone_id }
output "cluster_name" { value = aws_ecs_cluster.app.name }
output "task_security_group_id" { value = aws_security_group.tasks.id }
