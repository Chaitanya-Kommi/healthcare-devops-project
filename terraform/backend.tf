terraform {
  backend "s3" {
    bucket       = "healthcare-devops-tfstate-190535468276"
    key          = "dev/terraform.tfstate"
    region       = "eu-west-2"
    use_lockfile = true
  }
}