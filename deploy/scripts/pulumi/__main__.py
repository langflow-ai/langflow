#! ./venv/bin/python
import json
import os

import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define AWS resources
aws_region = "us-west-2"
vpc_cidr_block = "10.0.0.0/16"
subnet_cidr_block = "10.0.1.0/24"

# AWS Provider
aws_provider = aws.Provider("aws_provider", region=aws_region)
# Create a VPC
vpc = aws.ec2.Vpc("app_vpc", cidr_block=vpc_cidr_block)

task_exec_role = aws.iam.Role(
    "task_exec_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Effect": "Allow",
                    "Sid": "",
                }
            ],
        }
    ),
)

# Create a Subnet
subnet = aws.ec2.Subnet(
    "app_subnet",
    vpc_id=vpc.id,
    cidr_block=subnet_cidr_block,
    map_public_ip_on_launch=True,
    availability_zone=f"{aws_region}a",
)

subnet_group = aws.rds.SubnetGroup(
    "subnet_group",
    subnet_ids=[subnet.id],
    tags={"Name": "subnet_group"},
)

# ECS Cluster
cluster = aws.ecs.Cluster("app_cluster")

# Backend Service
backend_repository = aws.ecr.Repository("backend_repository")
# ECS Task Definition for Backend
backend_task_definition = aws.ecs.TaskDefinition(
    "backend_task_definition",
    family="backend",
    cpu="512",
    memory="1024",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    execution_role_arn=task_exec_role.arn,
    container_definitions=pulumi.Output.all(backend_repository.repository_url).apply(
        lambda url: json.dumps(
            [
                {
                    "name": "backend",
                    "image": f"{url}:latest",
                    "portMappings": [{"containerPort": 7860}],
                    # Include other necessary settings from .env file
                }
            ]
        )
    ),
)

# ECS Service for Backend
backend_service = aws.ecs.Service(
    "backend_service",
    cluster=cluster.arn,
    desired_count=1,
    launch_type="FARGATE",
    task_definition=backend_task_definition.arn,
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=[subnet.id],
        # Assign security groups as needed
    ),
)


# RDS Instance for PostgreSQL
db_instance = aws.rds.Instance(
    "db_instance",
    allocated_storage=20,
    engine="postgres",
    engine_version="13",
    instance_class="db.t2.micro",
    name="mydatabase",
    username=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    parameter_group_name="default.postgres13",
    db_subnet_group_name=subnet_group.name,
    skip_final_snapshot=True,
    # Include other configurations as necessary
)

# ElastiCache Redis
redis_security_group = aws.ec2.SecurityGroup(
    "redis_security_group",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            from_port=6379,
            to_port=6379,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
)


redis_cluster = aws.elasticache.Cluster(
    "redis_cluster",
    engine="redis",
    node_type="cache.t2.micro",
    num_cache_nodes=1,
    parameter_group_name="default.redis6.x",
    engine_version="6.x",
    subnet_group_name=subnet_group.name,
    security_group_ids=[redis_security_group.id],
    # Include other configurations as necessary
)


# Amazon MQ for RabbitMQ
rabbitmq_broker = aws.mq.Broker(
    "rabbitmq_broker",
    broker_name="myrabbitmq",
    engine_type="rabbitmq",
    engine_version="3.8.6",
    host_instance_type="mq.t3.micro",
    user=[
        {
            "username": os.getenv("RABBITMQ_DEFAULT_USER"),
            "password": os.getenv("RABBITMQ_DEFAULT_PASS"),
        }
    ],
    # Include other configurations as necessary
)


# ECS Task Definition for Frontend
frontend_task_definition = aws.ecs.TaskDefinition(
    "frontend_task_definition",
    # Task Definition Configurations
)

frontend_service = aws.ecs.Service(
    "frontend_service",
    # Service Configurations
)


# Output relevant information
pulumi.export("vpc_id", vpc.id)
pulumi.export("subnet_id", subnet.id)
# Other outputs as needed
