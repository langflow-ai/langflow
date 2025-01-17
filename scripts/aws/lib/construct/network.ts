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
  readonly centralVpc: ec2.IVpc;
  readonly cluster: ecs.Cluster;
  readonly centralEcsBackSG: ec2.SecurityGroup;
  readonly centralDbSG: ec2.SecurityGroup;
  readonly backendLogGroup: logs.LogGroup;
  readonly alb: elb.IApplicationLoadBalancer;
  readonly albTG: elb.ApplicationTargetGroup;
  readonly centralAlbSG: ec2.SecurityGroup;

  constructor(scope: Construct, id: string) {
    super(scope, id)
    const alb_listen_port=80
    const back_service_port=7860

    // Use existing VPC
    this.centralVpc = ec2.Vpc.fromLookup(scope, 'ExistingVPC', {
      vpcId: 'vpc-027288988b1ac3149'
    });

    // ALBに設定するセキュリティグループ
    this.centralAlbSG = new ec2.SecurityGroup(scope, 'ALBSecurityGroup', {
      securityGroupName: 'langflow-alb-cn-sg',
      description: 'Security group for langflow ALB',
      vpc: this.centralVpc
    });

    this.alb = new elb.ApplicationLoadBalancer(this,'langflow-alb',{
      internetFacing: true, //インターネットからのアクセスを許可するかどうか指定
      loadBalancerName: 'langflow-alb',
      securityGroup: this.centralAlbSG, //作成したセキュリティグループを割り当てる
      vpc:this.centralVpc,   
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
        interval: Duration.seconds(30),
        timeout: Duration.seconds(10),
        healthyHttpCodes: '200,302,404',
      },
    });

    // Cluster
    this.cluster = new ecs.Cluster(this, 'EcsCluster', {
      clusterName: 'langflow-cluster',
      vpc: this.centralVpc,
      enableFargateCapacityProviders: true,
    });

    // ECS BackEndに設定するセキュリティグループ
    this.centralEcsBackSG = new ec2.SecurityGroup(scope, 'ECSBackEndSecurityGroup', {
      securityGroupName: 'langflow-ecs-back-cn-sg',
      description: 'Security group for langflow backend ECS',
      vpc: this.centralVpc,
    });
    this.centralEcsBackSG.addIngressRule(this.centralAlbSG,ec2.Port.tcp(back_service_port));

    // RDSに設定するセキュリティグループ
    this.centralDbSG = new ec2.SecurityGroup(scope, 'DBSecurityGroup', {
      allowAllOutbound: true,
      securityGroupName: 'langflow-cn-db-sg',
      description: 'for langflow-db',
      vpc: this.centralVpc,
    });

    // Create CloudWatch Log Group
    this.backendLogGroup = new logs.LogGroup(this, 'backendLogGroup', {
      logGroupName: 'langflow-backend-logs',
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }
}