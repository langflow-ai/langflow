variable "region" {
  description = "The AWS region"
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  default     = "t2.micro"
}

variable "manager_count" {
  description = "Number of manager nodes"
  default     = 1
}

variable "worker_count" {
  description = "Number of worker nodes"
  default     = 3
}
