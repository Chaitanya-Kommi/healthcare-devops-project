resource"aws_ecr_repository" "services" {

  for_each = toset(var.repository_names)

  name = each.value
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    project     = var.project_name
    Environment = "shared"
  }
}