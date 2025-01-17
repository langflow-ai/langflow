import { Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs';
import {
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elb,
    aws_secretsmanager as secretsmanager,
} from 'aws-cdk-lib';
import * as dotenv from 'dotenv';
const path = require('path');
dotenv.config({path: path.join(__dirname, "../../.env")});

interface BackEndProps {
  cluster: ecs.Cluster
  ecsBackSG:ec2.SecurityGroup
  ecrBackEndRepository:ecr.Repository
  backendTaskRole: iam.Role;
  backendTaskExecutionRole: iam.Role;
  backendLogGroup: logs.LogGroup;
  arch:ecs.CpuArchitecture
  albTG: elb.ApplicationTargetGroup;
  dbSecret: secretsmanager.Secret;
}

export class BackEndCluster extends Construct {
  
  constructor(scope: Construct, id: string, props:BackEndProps) {
    super(scope, id)
    const backendServiceName = 'backend'
    const backendServicePort = 7860

    // Create Backend Fargate Service
    const backendTaskDefinition = new ecs.FargateTaskDefinition(
      this,
      'BackEndTaskDef',
      {
          memoryLimitMiB: 3072,
          cpu: 1024,
          executionRole: props.backendTaskExecutionRole,
          runtimePlatform:{
            operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
            cpuArchitecture: props.arch,
          },
          taskRole: props.backendTaskRole,
      }
    );
    backendTaskDefinition.addContainer('backendContainer', {
      image: ecs.ContainerImage.fromEcrRepository(props.ecrBackEndRepository, "latest"),
      containerName:'langflow-back-container',
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: 'my-stream',
        logGroup: props.backendLogGroup,
      }),
      environment:{
        "LANGFLOW_AUTO_LOGIN": process.env.LANGFLOW_AUTO_LOGIN ?? 'false',
        "LANGFLOW_SUPERUSER": process.env.LANGFLOW_SUPERUSER ?? "admin",
        "LANGFLOW_SUPERUSER_PASSWORD": process.env.LANGFLOW_SUPERUSER_PASSWORD ?? "123456",
      },
      secrets: {
        "LANGFLOW_DATABASE_URL": ecs.Secret.fromSecretsManager(props.dbSecret),
      },
      portMappings: [
          {
              containerPort: backendServicePort,
              protocol: ecs.Protocol.TCP,
          },
      ],
    });
    
    const backendService = new ecs.FargateService(this, 'BackEndService', {
      cluster: props.cluster,
      serviceName: backendServiceName,
      taskDefinition: backendTaskDefinition,
      enableExecuteCommand: true,
      securityGroups: [props.ecsBackSG],
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });
    props.albTG.addTarget(backendService);
  }
}