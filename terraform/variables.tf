variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets"
  type        = list(string)
}

variable "availability_zones" {
  description = "AWS availability zones for the VPC"
  type        = list(string)
}

variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "project_name" {
  description = "Name of the project for tagging"
  type        = string
}