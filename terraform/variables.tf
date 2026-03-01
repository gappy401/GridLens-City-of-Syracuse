variable "project_name" {
  default = "renewable-atlas"
}

variable "env" {
  default     = "dev"
  description = "dev | prod"
}

variable "aws_region" {
  default = "us-east-1"
}

variable "vpc_id" {
  description = "VPC to deploy into"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for RDS, ECS, Redis"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for ALB"
}

variable "db_name"     { default = "atlas" }
variable "db_username" { default = "atlas_admin" }
variable "db_password" { sensitive = true }

variable "db_instance_class" {
  default     = "db.t3.medium"
  description = "RDS instance class"
}

variable "acm_certificate_arn" {
  description = "ACM cert ARN for HTTPS listener"
}
