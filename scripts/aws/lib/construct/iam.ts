import { RemovalPolicy, Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_rds as rds,
  aws_iam as iam,
} from 'aws-cdk-lib';

interface IAMProps {
  rdsCluster:rds.DatabaseCluster
}

export class EcsIAM extends Construct {
  readonly backendTaskRole: iam.Role;
  readonly backendTaskExecutionRole: iam.Role;

  constructor(scope: Construct, id: string, props:IAMProps) {
    super(scope, id)

    // Policy Statements
    // ECS Policy State
    const ECSExecPolicyStatement = new iam.PolicyStatement({
      sid: 'allowECSExec',
      resources: ['*'],
      actions: [
        'ecr:GetAuthorizationToken',
        'ecr:BatchCheckLayerAvailability',
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage',
      ],
    });
    // Bedrock Policy State
    const BedrockPolicyStatement = new iam.PolicyStatement({
      sid: 'allowBedrockAccess',
      resources: ['*'],
      actions: [
        'bedrock:*',
      ],
    });
    // Kendra Policy State
    const KendraPolicyStatement = new iam.PolicyStatement({
      sid: 'allowKendraAccess',
      resources: ['*'],
      actions: [
        'kendra:*'
      ],
    });
    // Create Rag Policy
    const RagAccessPolicy = new iam.Policy(this, 'RAGFullAccess', {
      statements: [KendraPolicyStatement,BedrockPolicyStatement],
    })
    // Secrets ManagerからDB認証情報を取ってくるためのPolicy
    const SecretsManagerPolicy = new iam.Policy(this, 'SMGetPolicy', {
      statements: [new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [props.rdsCluster.secret!.secretArn],
      })],
    })

    // BackEnd Task Role
    this.backendTaskRole = new iam.Role(this, 'BackendTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    // ECS Exec Policyの付与
    this.backendTaskRole.addToPolicy(ECSExecPolicyStatement);
    // KendraとBedrockのアクセス権付与
    this.backendTaskRole.attachInlinePolicy(RagAccessPolicy);

    // BackEnd Task ExecutionRole 
    this.backendTaskExecutionRole = new iam.Role(this, 'backendTaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        {
          managedPolicyArn:
            'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
        },
      ],
    });
  
    this.backendTaskExecutionRole.attachInlinePolicy(SecretsManagerPolicy);
    this.backendTaskExecutionRole.attachInlinePolicy(RagAccessPolicy);
  }
}