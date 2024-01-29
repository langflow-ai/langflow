import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecs from 'aws-cdk-lib/aws-ecs'

import { Network, EcrRepository, FrontEndCluster, BackEndCluster, Rds, EcsIAM, Rag} from './construct';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

const errorMessageForBooleanContext = (key: string) => {
  return `There was an error setting $ {key}. Possible causes are as follows.
  - Trying to set it with the -c option instead of changing cdk.json
  - cdk.json is set to a value that is not a boolean (e.g. “true” double quotes are not required)
  - no items in cdk.json (unset) `;
};


export class LangflowAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    // Kendra Enable
    const ragEnabled: boolean = this.node.tryGetContext('ragEnabled')!;
    if (typeof ragEnabled !== 'boolean') {
      throw new Error(errorMessageForBooleanContext('ragEnabled'));
    }
    if (ragEnabled) {
      new Rag(this, 'Rag', {
      });
    }

    // Arch
    const arch = ecs.CpuArchitecture.X86_64

    // VPC
    const { vpc, cluster, cloudmapNamespace, ecsBackSG, dbSG, backendLogGroup, alb, albTG, albSG} = new Network(this, 'Network')

    // ECR
    const { ecrBackEndRepository } = new EcrRepository(this, 'Ecr', {
      cloudmapNamespace:cloudmapNamespace,
      arch:arch
    })

    // RDS
    // VPCとSGのリソース情報をPropsとして引き渡す
    const { rdsCluster } = new Rds(this, 'Rds', { vpc, dbSG })

    // IAM
    const { backendTaskRole, backendTaskExecutionRole } = new EcsIAM(this, 'EcsIAM',{
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
      arch:arch,
      albTG:albTG
    })
    backendService.node.addDependency(rdsCluster);

    const frontendService = new FrontEndCluster(this, 'frontend',{
      cluster:cluster,
      backendServiceName: backendService.backendServiceName,
      cloudmapNamespace: cloudmapNamespace,
      arch:arch,
      alb:alb,
      albSG:albSG
    })
    frontendService.node.addDependency(backendService);


    // S3+CloudFront
    // new Web(this,'Cloudfront-S3')
  }
}
