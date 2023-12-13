import { Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_ecr as ecr,
  aws_servicediscovery as servicediscovery,
  aws_iam as iam,
  aws_logs as logs,
  aws_elasticloadbalancingv2 as elb,
} from 'aws-cdk-lib';
import { CpuArchitecture } from 'aws-cdk-lib/aws-ecs';

interface FrontEndProps {
  cluster:ecs.Cluster
  ecsFrontSG:ec2.SecurityGroup
  ecrFrontEndRepository:ecr.Repository
  targetGroup: elb.ApplicationTargetGroup;
  backendServiceName: string;
  frontendTaskRole: iam.Role;
  frontendTaskExecutionRole: iam.Role;
  frontendLogGroup: logs.LogGroup;
  cloudmapNamespace: servicediscovery.PrivateDnsNamespace;
  arch:ecs.CpuArchitecture;
}

export class FrontEndCluster extends Construct {
  constructor(scope: Construct, id: string, props:FrontEndProps) {
    super(scope, id)

    const containerPort = 3000
    const frontendTaskDefinition = new ecs.FargateTaskDefinition(
      this,
      'FrontendTaskDef',
      {
          memoryLimitMiB: 3072,
          cpu: 1024,
          executionRole: props.frontendTaskExecutionRole,
          runtimePlatform:{
            operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
            cpuArchitecture: props.arch,
          },
          taskRole: props.frontendTaskRole,
      }
  );
  const frontendServiceName = 'frontend'
  frontendTaskDefinition.addContainer('frontendContainer', {
      image: ecs.ContainerImage.fromEcrRepository(props.ecrFrontEndRepository, "latest"),
      containerName:'langflow-front-container',
      environment: {
          BACKEND_SERVICE_NAME: props.backendServiceName,
          BACKEND_URL: `http://${props.backendServiceName}.${props.cloudmapNamespace.namespaceName}:7860/`,
          VITE_PROXY_TARGET: `http://${props.backendServiceName}.${props.cloudmapNamespace.namespaceName}:7860/`,
      },
      logging: ecs.LogDriver.awsLogs({
          streamPrefix: 'my-stream',
          logGroup: props.frontendLogGroup,
      }),
      portMappings: [
          {
              name:frontendServiceName,
              containerPort: containerPort,
              protocol: ecs.Protocol.TCP,
              appProtocol:ecs.AppProtocol.http,
          },
      ],
  });
  const frontendService = new ecs.FargateService(
      this,
      'FrontendService',
      {
        serviceName: frontendServiceName,
        cluster: props.cluster,
        desiredCount: 1,
        assignPublicIp: false,
        taskDefinition: frontendTaskDefinition,
        enableExecuteCommand: true,
        securityGroups: [props.ecsFrontSG],
        cloudMapOptions: {
          cloudMapNamespace: props.cloudmapNamespace,
          containerPort: containerPort,
          dnsRecordType: servicediscovery.DnsRecordType.A,
          dnsTtl: Duration.seconds(10),
          name: frontendServiceName
        },
        healthCheckGracePeriod: Duration.seconds(1000),
      }
  );

  props.targetGroup.addTarget(frontendService);

    // // Create ALB and ECS Fargate Service
    // const frontService = new ecs_patterns.ApplicationLoadBalancedFargateService(
    //   this,
    //   "FrontEndService",
    //   {
    //     cluster: cluster,
    //     serviceName: 'langflow-frontend-service',
    //     cpu: 256,
    //     memoryLimitMiB: 512,
    //     listenerPort: 80,
    //     assignPublicIp: true, // Public facing - ALB
    //     taskSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    //     securityGroups:[ecsFrontSG],
    //     taskImageOptions: {
    //       family: 'langflow-taskdef',
    //       containerName: 'langflow-front-container',
    //       image: ecs.ContainerImage.fromEcrRepository(ecrFrontEndRepository, "latest"),
    //       containerPort: 3000, // L2なので、TargetGroupのportが3000で設定されるはず
    //     },
    //     loadBalancer:alb,
    //     openListener:false,
    //   }
    // );

  }
}