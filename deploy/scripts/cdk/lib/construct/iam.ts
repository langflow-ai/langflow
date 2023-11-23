import { RemovalPolicy, Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_iam as iam,
  aws_logs as logs,
} from 'aws-cdk-lib';

export class EcsIAM extends Construct {
  readonly backendTaskRole: iam.Role;
  readonly TaskExecutionRole: iam.Role;
  readonly frontendTaskRole: iam.Role;

  constructor(scope: Construct, id: string) {
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

    // FrontEnd Task Role
    this.frontendTaskRole = new iam.Role(this, 'FrontendTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    this.frontendTaskRole.addToPolicy(ECSExecPolicyStatement);

    // BackEnd Task Role
    this.backendTaskRole = new iam.Role(this, 'BackendTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    // ECS Exec Policyの付与
    this.backendTaskRole.addToPolicy(ECSExecPolicyStatement);
    // KendraとBedrockのアクセス権付与
    this.backendTaskRole.addToPolicy(KendraPolicyStatement);
    this.backendTaskRole.addToPolicy(BedrockPolicyStatement);

    // Task ExecutionRole -> ここは共通
    this.TaskExecutionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        {
          managedPolicyArn:
            'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
        },
      ],
    });
  }
}