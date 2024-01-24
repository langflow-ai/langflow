from pathlib import Path

import pulumi
import pulumi_aws as aws
import pulumi_std as std
from docker_swarm import DockerSwarm

config = pulumi.Config()
# The AWS region
region = config.get("region")
if region is None:
    region = "us-east-1"
# EC2 instance type
instance_type = config.get("instanceType")
if instance_type is None:
    instance_type = "t2.small"
# Number of manager nodes
manager_count = config.get_float("managerCount")
if manager_count is None:
    manager_count = 1
# Number of worker nodes
worker_count = config.get_float("workerCount")
if worker_count is None:
    worker_count = 3
# The name of the project
project_name = config.require("projectName")


# as string
ssh_key_path = Path("~/.ssh/id_rsa.pub").expanduser().as_posix()

swarm_key = aws.ec2.KeyPair(
    "swarm-key",
    key_name="swarm-key",
    public_key=std.file_output(input=ssh_key_path).apply(lambda invoke: invoke.result),
)
swarm_vpc = aws.ec2.Vpc("swarm-vpc", cidr_block="10.0.0.0/16", enable_dns_support=True, enable_dns_hostnames=True)
swarm_public_subnet = aws.ec2.Subnet("swarm-public-subnet", vpc_id=swarm_vpc.id, cidr_block="10.0.2.0/24")
swarm_sg = aws.ec2.SecurityGroup(
    "swarm-sg",
    vpc_id=swarm_vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            from_port=22,
            to_port=22,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=2376,
            to_port=2377,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=7946,
            to_port=7946,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=7946,
            to_port=7946,
            protocol="udp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=4789,
            to_port=4789,
            protocol="udp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=80,
            to_port=80,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=8080,
            to_port=8080,
            protocol="tcp",
            # cidr_blocks=[swarm_public_subnet.cidr_block],
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"],
        ),
        aws.ec2.SecurityGroupEgressArgs(
            from_port=8080,
            to_port=8080,
            protocol="tcp",
            # cidr_blocks=[swarm_public_subnet.cidr_block],
            cidr_blocks=["0.0.0.0/0"],
        ),
    ],
)
docker_swarm = DockerSwarm(
    project_name,
    {
        "keyName": swarm_key.key_name,
        "vpcId": swarm_vpc.id,
        "subnetId": swarm_public_subnet.id,
        "securityGroup": swarm_sg.id,
        "instanceType": instance_type,
        "managerCount": manager_count,
        "workerCount": worker_count,
        "projectName": project_name,
    },
)
swarm_private_subnet = aws.ec2.Subnet("swarm-private-subnet", vpc_id=swarm_vpc.id, cidr_block="10.0.1.0/24")
igw = aws.ec2.InternetGateway("igw", vpc_id=swarm_vpc.id)
public_rt = aws.ec2.RouteTable(
    "public_rt",
    vpc_id=swarm_vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=igw.id,
        )
    ],
)
public_subnet_asso = aws.ec2.RouteTableAssociation(
    "public_subnet_asso", subnet_id=swarm_public_subnet.id, route_table_id=public_rt.id
)
pulumi.export("managerPublicIps", docker_swarm.managerPublicIps)
