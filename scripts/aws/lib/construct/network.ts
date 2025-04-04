import { RemovalPolicy, Duration, CfnOutput } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_logs as logs,
  aws_servicediscovery as servicediscovery,
  aws_elasticloadbalancingv2 as elb,
} from 'aws-cdk-lib';

export class Network extends Construct {
  readonly vpc: ec2.Vpc;
  readonly cluster: ecs.Cluster;
  readonly ecsBackSG: ec2.SecurityGroup;
  readonly dbSG: ec2.SecurityGroup;
  readonly backendLogGroup: logs.LogGroup;
  readonly alb: elb.IApplicationLoadBalancer;
  readonly albTG: elb.ApplicationTargetGroup;
  readonly albSG: ec2.SecurityGroup;

  constructor(scope: Construct, id: string) {
    super(scope, id)
    const alb_listen_port=80
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

    // ALBに設定するセキュリティグループ
    this.albSG = new ec2.SecurityGroup(scope, 'ALBSecurityGroup', {
      securityGroupName: 'alb-sg',
      description: 'for alb',
      vpc: this.vpc,
    })

    this.alb = new elb.ApplicationLoadBalancer(this,'langflow-alb',{
      internetFacing: true, //インターネットからのアクセスを許可するかどうか指定
      loadBalancerName: 'langflow-alb',
      securityGroup: this.albSG, //作成したセキュリティグループを割り当てる
      vpc:this.vpc,
    })

    const listener = this.alb.addListener('Listener', { port: alb_listen_port });

    this.albTG = listener.addTargets('targetGroup', {
      port: back_service_port,
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

    // Cluster
    this.cluster = new ecs.Cluster(this, 'EcsCluster', {
      clusterName: 'langflow-cluster',
      vpc: this.vpc,
      enableFargateCapacityProviders: true,
    });

    // ECS BackEndに設定するセキュリティグループ
    this.ecsBackSG = new ec2.SecurityGroup(scope, 'ECSBackEndSecurityGroup', {
      securityGroupName: 'langflow-ecs-back-sg',
      description: 'for langflow-back-ecs',
      vpc: this.vpc,
    })
    this.ecsBackSG.addIngressRule(this.albSG,ec2.Port.tcp(back_service_port))

    // RDSに設定するセキュリティグループ
    this.dbSG = new ec2.SecurityGroup(scope, 'DBSecurityGroup', {
      allowAllOutbound: true,
      securityGroupName: 'langflow-db',
      description: 'for langflow-db',
      vpc: this.vpc,
    })
    // langflow-ecs-back-sg からのポート3306:mysql(5432:postgres)のインバウンドを許可
    this.dbSG.addIngressRule(this.ecsBackSG, ec2.Port.tcp(3306))

    // Create CloudWatch Log Group
    this.backendLogGroup = new logs.LogGroup(this, 'backendLogGroup', {
      logGroupName: 'langflow-backend-logs',
      removalPolicy: RemovalPolicy.DESTROY,
    });

  }
}
