import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecs from 'aws-cdk-lib/aws-ecs'

import { Network, EcrRepository, FrontEndCluster, BackEndCluster, Rds, EcsIAM } from './construct';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class LangflowAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    // Arch
    const arch = ecs.CpuArchitecture.X86_64

    // VPC
    const { vpc, cluster, alb, targetGroup, cloudmapNamespace, ecsFrontSG, ecsBackSG, dbSG, albSG, backendLogGroup, frontendLogGroup} = new Network(this, 'Network')

    // ECR
    const { ecrFrontEndRepository,ecrBackEndRepository} = new EcrRepository(this, 'Ecr', {
      cloudmapNamespace:cloudmapNamespace,
      arch:arch
    })

    // RDS
    // VPCとSGのリソース情報をPropsとして引き渡す
    const { rdsCluster } = new Rds(this, 'Rds', { vpc, dbSG })

    // IAM
    const { frontendTaskRole, frontendTaskExecutionRole, backendTaskRole, backendTaskExecutionRole } = new EcsIAM(this, 'EcsIAM',{
      rdsCluster:rdsCluster
    })

    const backendService = new BackEndCluster(this, 'backend', {
      cluster:cluster,
      ecsBackSG:ecsBackSG,
      ecrBackEndRepository:ecrBackEndRepository,
      backendTaskRole:backendTaskRole,
      backendTaskExecutionRole:backendTaskExecutionRole,
      backendLogGroup:backendLogGroup,
      cloudmapNamespace:cloudmapNamespace,
      rdsCluster:rdsCluster,
      alb:alb,
      arch:arch
    })
    backendService.node.addDependency(rdsCluster);

    const frontendService = new FrontEndCluster(this, 'frontend',{
      cluster:cluster,
      ecsFrontSG:ecsFrontSG,
      ecrFrontEndRepository:ecrFrontEndRepository,
      targetGroup: targetGroup,
      backendServiceName: backendService.backendServiceName,
      frontendTaskRole: frontendTaskRole,
      frontendTaskExecutionRole: frontendTaskExecutionRole,
      frontendLogGroup: frontendLogGroup,
      cloudmapNamespace: cloudmapNamespace,
      arch:arch 
    })
    frontendService.node.addDependency(backendService);


    // S3+CloudFront
    // new Web(this,'Cloudfront-S3')
  }
}
