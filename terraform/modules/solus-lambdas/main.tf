terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "archive_file" "book_site_survey" {
  type        = "zip"
  source_file = "${path.root}/../../starter/lambda/book_site_survey.py"
  output_path = "${path.module}/book_site_survey.zip"
}

data "archive_file" "submit_net_metering" {
  type        = "zip"
  source_file = "${path.root}/../../starter/lambda/submit_net_metering.py"
  output_path = "${path.module}/submit_net_metering.zip"
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.name_prefix}-lambda-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "book_site_survey" {
  function_name = "${var.name_prefix}-book-site-survey"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "book_site_survey.lambda_handler"
  runtime       = "python3.12"
  filename      = data.archive_file.book_site_survey.output_path
  source_code_hash = data.archive_file.book_site_survey.output_base64sha256
}

resource "aws_lambda_function" "submit_net_metering" {
  function_name = "${var.name_prefix}-submit-net-metering"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "submit_net_metering.lambda_handler"
  runtime       = "python3.12"
  filename      = data.archive_file.submit_net_metering.output_path
  source_code_hash = data.archive_file.submit_net_metering.output_base64sha256
}

resource "aws_api_gateway_rest_api" "solus" {
  name = "${var.name_prefix}-survey-api"
}

resource "aws_api_gateway_resource" "surveys" {
  rest_api_id = aws_api_gateway_rest_api.solus.id
  parent_id   = aws_api_gateway_rest_api.solus.root_resource_id
  path_part   = "surveys"
}

resource "aws_api_gateway_method" "post_surveys" {
  rest_api_id   = aws_api_gateway_rest_api.solus.id
  resource_id   = aws_api_gateway_resource.surveys.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post_surveys_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.solus.id
  resource_id             = aws_api_gateway_resource.surveys.id
  http_method             = aws_api_gateway_method.post_surveys.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.book_site_survey.invoke_arn
}

resource "aws_lambda_permission" "survey_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.book_site_survey.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.solus.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "solus" {
  depends_on  = [aws_api_gateway_integration.post_surveys_lambda]
  rest_api_id = aws_api_gateway_rest_api.solus.id
}
