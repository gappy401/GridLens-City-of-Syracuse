output "api_url" {
  value       = "https://${aws_lb.main.dns_name}"
  description = "ALB endpoint for the FastAPI service"
}

output "rds_endpoint" {
  value       = aws_db_instance.atlas.endpoint
  sensitive   = true
  description = "RDS PostgreSQL endpoint"
}

output "ecr_repo_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "ECR repo URL for docker push"
}

output "s3_bucket" {
  value       = aws_s3_bucket.data_lake.bucket
  description = "Data lake S3 bucket name"
}
