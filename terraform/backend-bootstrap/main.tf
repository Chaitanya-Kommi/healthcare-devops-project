data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "${var.project_name}-terraform-state"
    Environment = "bootstrap"
    Project     = var.project_name
  }
}