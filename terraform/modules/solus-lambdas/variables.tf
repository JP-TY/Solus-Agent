variable "name_prefix" {
  description = "Prefix for Solus resources"
  type        = string
  default     = "solus"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "stage_name" {
  description = "API Gateway stage for survey REST API"
  type        = string
  default     = "prod"
}

output "survey_api_url" {
  description = "Invoke URL for the site-survey REST API"
  value       = "${aws_api_gateway_deployment.solus.invoke_url}${var.stage_name}"
}

output "lambda_names" {
  description = "Deployed Lambda function names"
  value       = [aws_lambda_function.book_site_survey.function_name, aws_lambda_function.submit_net_metering.function_name]
}
