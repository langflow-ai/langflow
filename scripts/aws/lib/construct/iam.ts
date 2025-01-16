import { RemovalPolicy, Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_iam as iam,
  aws_secretsmanager as secretsmanager,
  SecretValue
} from 'aws-cdk-lib';

interface IAMProps {
}

export class EcsIAM extends Construct {
  readonly backendTaskRole: iam.Role;
  readonly backendTaskExecutionRole: iam.Role;
  readonly dbSecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props:IAMProps) {
    super(scope, id)

    // Create database credentials secret
    this.dbSecret = new secretsmanager.Secret(this, 'DatabaseSecret', {
      secretName: 'langflow/database',
      secretStringValue: SecretValue.unsafePlainText(JSON.stringify({
        username: 'langflow',
        host: 'localhost',
        port: '5432',
        dbname: 'langflow',
        password: 'langflow'
      })),
    });

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

    // Secrets Manager Policy
    const SecretsManagerPolicy = new iam.Policy(this, 'SecretsManagerPolicy', {
      statements: [
        new iam.PolicyStatement({
          sid: 'AllowSecretsManagerAccess',
          effect: iam.Effect.ALLOW,
          actions: ['secretsmanager:GetSecretValue'],
          resources: [this.dbSecret.secretArn],
        }),
      ],
    });

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
  
    this.backendTaskExecutionRole.attachInlinePolicy(RagAccessPolicy);
    this.backendTaskExecutionRole.attachInlinePolicy(SecretsManagerPolicy);
  }
}