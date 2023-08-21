variable "key_name" {}
variable "vpc_id" {}
variable "subnet_id" {}
variable "security_group" {}
variable "instance_type" {}
variable "manager_count" {}
variable "worker_count" {}


resource "aws_instance" "manager" {
  count                  = var.manager_count
  ami                    = "ami-08a52ddb321b32a8c" # Amazon Linux 2 LTS
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [var.security_group]
  subnet_id              = var.subnet_id
  associate_public_ip_address = true

  user_data = <<-EOT
                #!/bin/bash
                sudo yum update -y
                sudo yum install -y docker
                sudo service docker start
                sudo usermod -a -G docker ec2-user
                sudo chkconfig docker on
                docker swarm init --advertise-addr $(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)
                EOT

  tags = {
    Name = "manager-${count.index}"
  }
}

resource "aws_instance" "worker" {
  count                  = var.worker_count
  ami                    = "ami-08a52ddb321b32a8c" # Amazon Linux 2 LTS
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [var.security_group]
  subnet_id              = var.subnet_id
  associate_public_ip_address = true

  user_data = <<-EOT
                #!/bin/bash
                sudo yum update -y
                sudo yum install -y docker
                sudo service docker start
                sudo usermod -a -G docker ec2-user
                sudo chkconfig docker on
                docker swarm join --token $(curl -s http://${aws_instance.manager.0.public_ip}:8080/token) ${aws_instance.manager.0.private_ip}:2377
                EOT

  tags = {
    Name = "worker-${count.index}"
  }
}

output "manager_public_ips" {
  value = aws_instance.manager[*].public_ip
}

output "worker_public_ips" {
  value = aws_instance.worker[*].public_ip
}
