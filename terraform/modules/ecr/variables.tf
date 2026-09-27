variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "project_name" {
  description = "Name of the project for tagging"
  type        = string
}