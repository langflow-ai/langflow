from typing import Any, Optional, TypedDict

import pulumi
import pulumi_aws as aws
from pulumi import Input


class DockerSwarmArgs(TypedDict, total=False):
    keyName: Input[Any]
    vpcId: Input[Any]
    subnetId: Input[Any]
    securityGroup: Input[Any]
    instanceType: Input[str]
    managerCount: Input[Any]
    workerCount: Input[Any]
    projectName: Input[Any]


class DockerSwarm(pulumi.ComponentResource):
    def __init__(self, name: str, args: DockerSwarmArgs, opts: Optional[pulumi.ResourceOptions] = None):
        super().__init__("components:index:DockerSwarm", name, args, opts)

        manager = []
        for i in range(0, args["managerCount"]):
            manager.append(
                aws.ec2.Instance(
                    resource_name=f"{name}-manager-{i}",
                    ami="ami-08a52ddb321b32a8c",
                    instance_type=args["instanceType"],
                    key_name=args["keyName"],
                    vpc_security_group_ids=[args["securityGroup"]],
                    subnet_id=args["subnetId"],
                    associate_public_ip_address=True,
                    user_data="""#!/bin/bash
sudo yum update -y
sudo yum install -y docker
sudo yum install -y git
sudo yum install -y nc
sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo chkconfig docker on

# Fetch instance metadata with token
TOKEN=`curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
IP_ADDR=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/local-ipv4)

docker swarm init --advertise-addr $IP_ADDR

# Create a script to get the join token
echo 'docker swarm join-token worker -q' > get_token.sh
chmod +x get_token.sh
timeout 5m bash -c "while true; do { echo -e 'HTTP/1.1 200 OK\r\n'; ./get_token.sh; } | nc -l 8080; done" &
sleep 10

# Clone the repo and start the stack
git clone https://github.com/logspace-ai/langflow.git
cd /langflow
git checkout terraform
cd /langflow/deploy

sudo cp .env.example .env

sleep 20
# Add the label to random worker node to ensure that the data volume is created on the same node
docker node update --label-add app-db-data=true $(docker node ls --format '{{.Hostname}}' --filter role=worker | head -n 1)

docker network create --driver=overlay traefik-public --attachable

env $(cat .env | grep ^[A-Z] | xargs) docker stack deploy --compose-file docker-compose.yml -c docker-compose.override.yml langflow_stack

""",
                    tags={
                        "Name": f"{args['projectName']}-manager-{i}",
                    },
                    opts=pulumi.ResourceOptions(parent=self),
                )
            )

        worker = []
        for i in range(0, args["workerCount"]):
            worker.append(
                aws.ec2.Instance(
                    resource_name=f"{name}-worker-{i}",
                    ami="ami-08a52ddb321b32a8c",
                    instance_type=args["instanceType"],
                    key_name=args["keyName"],
                    vpc_security_group_ids=[args["securityGroup"]],
                    subnet_id=args["subnetId"],
                    associate_public_ip_address=True,
                    user_data=manager[0].private_ip.apply(
                        lambda private_ip: f"""#!/bin/bash
MANAGER_IP="{private_ip}"
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo chkconfig docker on
TOKEN=`curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
IP_ADDR=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/local-ipv4)
docker swarm join --token $(curl -s http://$MANAGER_IP:8080/token) --advertise-addr $IP_ADDR $MANAGER_IP:2377
"""
                    ),
                    tags={
                        "Name": f"{args['projectName']}-worker-{i}",
                    },
                    opts=pulumi.ResourceOptions(parent=self),
                )
            )

        self.managerPublicIps = [__item.public_ip for __item in manager]
        self.workerPublicIps = [__item.public_ip for __item in worker]
        self.register_outputs(
            {
                "managerPublicIps": [__item.public_ip for __item in manager],
                "workerPublicIps": [__item.public_ip for __item in worker],
            }
        )
