import { RemovalPolicy, Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_dynamodb as dynamodb,
  aws_iam as iam,
  aws_logs as logs,
  aws_servicediscovery as servicediscovery,
  aws_elasticloadbalancingv2 as elb,
} from 'aws-cdk-lib';

export class Network extends Construct {
  readonly vpc: ec2.Vpc;
  readonly cluster: ecs.Cluster;
  readonly alb: elb.IApplicationLoadBalancer;
  readonly targetGroup: elb.ApplicationTargetGroup;
  readonly cloudmapNamespace: servicediscovery.PrivateDnsNamespace;
  readonly ecsFrontSG: ec2.SecurityGroup;
  readonly ecsBackSG: ec2.SecurityGroup;
  readonly dbSG: ec2.SecurityGroup;
  readonly albSG: ec2.SecurityGroup;
  readonly backendTaskRole: iam.Role;
  readonly TaskExecutionRole: iam.Role;
  readonly frontendTaskRole: iam.Role;
  readonly backendLogGroup: logs.LogGroup;
  readonly frontendLogGroup: logs.LogGroup;

  constructor(scope: Construct, id: string) {
    super(scope, id)
    const alb_listen_port=80
    const front_service_port=3000
    const back_service_port=7860

    // VPC等リソースの作成
    this.vpc = new ec2.Vpc(scope, 'VPC', {
      vpcName: 'langflow-vpc',
      ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
      maxAzs: 3,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'langflow-Isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
        {
          cidrMask: 24,
          name: 'langflow-Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'langflow-Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS
        },
      ],
      natGateways: 1,
    })
    // Cluster
    this.cluster = new ecs.Cluster(this, 'EcsCluster', {
      clusterName: 'langflow-cluster',
      vpc: this.vpc,
      enableFargateCapacityProviders: true,
    });

    // Private DNS
    this.cloudmapNamespace = new servicediscovery.PrivateDnsNamespace(
      this,
      'Namespace',
      {
        name: 'ecs-deploy.com',
        vpc: this.vpc,
      }
    );

    // ALBに設定するセキュリティグループ
    this.albSG = new ec2.SecurityGroup(scope, 'ALBSecurityGroup', {
      securityGroupName: 'alb-sg',
      description: 'for alb',
      vpc: this.vpc,
    })
    this.albSG.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(alb_listen_port))

    this.alb = new elb.ApplicationLoadBalancer(this,'alb',{
      internetFacing: true, //インターネットからのアクセスを許可するかどうか指定
      loadBalancerName: 'alb',
      securityGroup: this.albSG, //作成したセキュリティグループを割り当てる
      vpc:this.vpc,   
    })

    const listener = this.alb.addListener('Listener', { port: alb_listen_port });

    this.targetGroup = listener.addTargets('targetGroup', {
      port: front_service_port,
      protocol: elb.ApplicationProtocol.HTTP,
      healthCheck: {
        enabled: true,
        path: '/health',
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 4,
        interval: Duration.seconds(100),
        timeout: Duration.seconds(30),
        healthyHttpCodes: '200',
      },
    });

    // ECS FrontEndに設定するセキュリティグループ
    this.ecsFrontSG = new ec2.SecurityGroup(scope, 'ECSFrontEndSecurityGroup', {
      securityGroupName: 'langflow-ecs-front-sg',
      description: 'for langflow-front-ecs',
      vpc: this.vpc,
    })
    this.ecsFrontSG.addIngressRule(this.albSG, ec2.Port.allTcp())

    // ECS BackEndに設定するセキュリティグループ
    this.ecsBackSG = new ec2.SecurityGroup(scope, 'ECSBackEndSecurityGroup', {
      securityGroupName: 'langflow-ecs-back-sg',
      description: 'for langflow-back-ecs',
      vpc: this.vpc,
    })
    this.ecsBackSG.addIngressRule(this.ecsFrontSG, ec2.Port.tcp(back_service_port))

    // RDSに設定するセキュリティグループ
    this.dbSG = new ec2.SecurityGroup(scope, 'DBSecurityGroup', {
      allowAllOutbound: true,
      securityGroupName: 'langflow-db',
      description: 'for langflow-db',
      vpc: this.vpc,
    })
    // AppRunnerSecurityGroupからのポート3306:mysql(5432:postgres)のインバウンドを許可
    this.dbSG.addIngressRule(this.ecsBackSG, ec2.Port.tcp(3306))
    
    // ECS Policy State
    const ECSExecPolicyStatement = new iam.PolicyStatement({
      sid: 'allowECSExec',
      resources: ['*'],
      actions: [
        'ecr:GetAuthorizationToken',
        'ecr:BatchCheckLayerAvailability',
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage',
        'ssmmessages:CreateControlChannel',
        'ssmmessages:CreateDataChannel',
        'ssmmessages:OpenControlChannel',
        'ssmmessages:OpenDataChannel',
        'logs:CreateLogStream',
        'logs:DescribeLogGroups',
        'logs:DescribeLogStreams',
        'logs:PutLogEvents',
      ],
    });
    // Bedrock roll
    const BedrockPolicyStatement = new iam.PolicyStatement({
      sid: 'allowBedrockAccess',
      resources: ['*'],
      actions: [
        'bedrock:*',
      ],
    });
    // Kendra roll
    const KendraPolicyStatement = new iam.PolicyStatement({
      sid: 'allowKendraAccess',
      resources: ['*'],
      actions: [
        'kendra:*'
      ],
    });

    this.backendTaskRole = new iam.Role(this, 'BackendTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    // ECS Exec Policyの付与
    this.backendTaskRole.addToPolicy(ECSExecPolicyStatement);
    // KendraとBedrockのアクセス権付与
    this.backendTaskRole.addToPolicy(KendraPolicyStatement);
    this.backendTaskRole.addToPolicy(BedrockPolicyStatement);

    

    this.frontendTaskRole = new iam.Role(this, 'FrontendTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    this.frontendTaskRole.addToPolicy(ECSExecPolicyStatement);

    this.TaskExecutionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        {
          managedPolicyArn:
            'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
        },
      ],
    });

    // Create CloudWatch Log Group
    this.backendLogGroup = new logs.LogGroup(this, 'backendLogGroup', {
      logGroupName: 'myapp-backend',
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.frontendLogGroup = new logs.LogGroup(this, 'frontendLogGroup', {
      logGroupName: 'myapp-frontend',
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }
}