locals {
  services = {
    api    = { command = ["python", "scripts/serve.py", "--host", "0.0.0.0", "--port", "8000"], count = var.api_count }
    worker = { command = ["python", "scripts/worker.py"], count = var.worker_count }
  }
  secret_resources = distinct([for arn in values(var.secret_arns) : join(":", slice(split(":", arn), 0, 7))])
  environment = {
    AAAEM_MODE             = "production"
    AAAEM_INTEGRATION_MODE = "live"
    AAAEM_PUBLIC_ORIGIN    = "https://${var.hostname}"
    AAAEM_ALLOWED_HOSTS    = "${var.hostname},127.0.0.1"
    AAAEM_MODEL_PROVIDER   = var.model_provider
    AAAEM_MODEL_ID         = var.model_id
    AAAEM_MODEL_ENDPOINT   = var.model_endpoint
    AWS_REGION             = var.region
    AAAEM_WORKER_ENABLED   = "false"
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/aaaem/${var.name}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "app" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = local.secret_resources }
    ], length(var.secret_kms_key_arns) > 0 ? [{
      Effect    = "Allow", Action = ["kms:Decrypt"], Resource = var.secret_kms_key_arns,
      Condition = { StringEquals = { "kms:ViaService" = "secretsmanager.${var.region}.amazonaws.com" } }
  }] : []) })
}
resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}
resource "aws_iam_role_policy" "bedrock" {
  count = length(var.bedrock_resource_arns) > 0 ? 1 : 0
  role  = aws_iam_role.task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["bedrock:InvokeModel"], Resource = var.bedrock_resource_arns
  }] })
}

resource "aws_security_group" "load_balancer" {
  name_prefix = "${var.name}-alb-"
  description = "HTTPS from configured operator networks"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_client_cidrs
  }
  egress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "tasks" {
  name_prefix = "${var.name}-tasks-"
  description = "Private API and workers; use a controlled NAT or egress proxy"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.load_balancer.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = var.database_security_group_id
  referenced_security_group_id = aws_security_group.tasks.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_lb" "app" {
  name                       = var.name
  internal                   = var.internal_load_balancer
  load_balancer_type         = "application"
  subnets                    = var.load_balancer_subnet_ids
  security_groups            = [aws_security_group.load_balancer.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = true
}
resource "aws_lb_target_group" "app" {
  name        = var.name
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/healthz"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_ecs_task_definition" "app" {
  for_each                 = local.services
  family                   = "${var.name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name            = each.key, image = var.image_uri, essential = true, user = "10001", command = each.value.command,
    stopTimeout     = 120,
    linuxParameters = { initProcessEnabled = true },
    portMappings    = each.key == "api" ? [{ containerPort = 8000, protocol = "tcp" }] : [],
    environment     = [for key, value in merge(local.environment, each.key == "worker" ? { AAAEM_WORKER_HEARTBEAT = "/tmp/aaaem-worker-heartbeat" } : {}) : { name = key, value = value }],
    secrets         = [for key, arn in var.secret_arns : { name = key, valueFrom = arn }],
    logConfiguration = { logDriver = "awslogs", options = {
      awslogs-group = aws_cloudwatch_log_group.app.name, awslogs-region = var.region, awslogs-stream-prefix = each.key
    } },
    healthCheck = {
      command  = ["CMD-SHELL", each.key == "api" ? "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)\"" : "python -c \"import time; from pathlib import Path; assert time.time()-Path('/tmp/aaaem-worker-heartbeat').stat().st_mtime < 180\""],
      interval = 30, timeout = 5, retries = 3, startPeriod = 60
    }
  }])
}

resource "aws_ecs_service" "app" {
  for_each                          = local.services
  name                              = each.key
  cluster                           = aws_ecs_cluster.app.id
  task_definition                   = aws_ecs_task_definition.app[each.key].arn
  desired_count                     = each.value.count
  launch_type                       = "FARGATE"
  platform_version                  = "1.4.0"
  health_check_grace_period_seconds = each.key == "api" ? 60 : null
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.app.arn
      container_name   = "api"
      container_port   = 8000
    }
  }
  depends_on = [aws_lb_listener.https, aws_iam_role_policy.secrets, aws_iam_role_policy_attachment.execution]
}
