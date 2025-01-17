import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecs from 'aws-cdk-lib/aws-ecs'

import { Network, EcrRepository, Web, BackEndCluster, Db, EcsIAM, Rag} from './construct';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

const errorMessageForBooleanContext = (key: string) => {
  return `There was an error setting $ {key}. Possible causes are as follows.
  - Trying to set it with the -c option instead of changing cdk.json
  - cdk.json is set to a value that is not a boolean (e.g. "true" double quotes are not required)
  - no items in cdk.json (unset) `;
};

export class LangflowAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    const stackProps = {
      ...props,
      env: {
        account: process.env.CDK_DEFAULT_ACCOUNT,
        region: process.env.CDK_DEFAULT_REGION
      }
    };
    
    super(scope, id, stackProps);
    
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
    const { centralVpc, cluster, centralEcsBackSG, centralDbSG, backendLogGroup, alb, albTG, centralAlbSG} = new Network(this, 'Network')

    const vpc = centralVpc
    const dbSG = centralDbSG
    const ecsBackSG = centralEcsBackSG
    const albSG = centralAlbSG

    // ECR
    const { ecrBackEndRepository } = new EcrRepository(this, 'Ecr', {
      arch:arch
    })

    // Database placeholder (no RDS)
    new Db(this, 'Db', { vpc, dbSG })

    // IAM
    const { backendTaskRole, backendTaskExecutionRole, dbSecret } = new EcsIAM(this, 'EcsIAM', {})

    const backendService = new BackEndCluster(this, 'backend', {
      cluster:cluster,
      ecsBackSG:ecsBackSG,
      ecrBackEndRepository:ecrBackEndRepository,
      backendTaskRole:backendTaskRole,
      backendTaskExecutionRole:backendTaskExecutionRole,
      backendLogGroup:backendLogGroup,
      arch:arch,
      albTG:albTG,
      dbSecret:dbSecret
    })

    const frontendService = new Web(this, 'frontend',{
      cluster:cluster,
      alb:alb,
      albSG:albSG
    })
    frontendService.node.addDependency(backendService);
  }
}
