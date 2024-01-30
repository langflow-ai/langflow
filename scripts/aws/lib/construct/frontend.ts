import { Stack, Duration, RemovalPolicy, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_ecr as ecr,
  aws_s3 as s3,
  aws_servicediscovery as servicediscovery,
  aws_iam as iam,
  aws_logs as logs,
  aws_elasticloadbalancingv2 as elb,
} from 'aws-cdk-lib';
import { CloudFrontToS3 } from '@aws-solutions-constructs/aws-cloudfront-s3';
import { CfnDistribution, Distribution } from 'aws-cdk-lib/aws-cloudfront';
import { NodejsBuild } from 'deploy-time-build';
import { CpuArchitecture } from 'aws-cdk-lib/aws-ecs';

interface FrontEndProps {
  cluster:ecs.Cluster
  backendServiceName: string;
  cloudmapNamespace: servicediscovery.PrivateDnsNamespace;
  arch:ecs.CpuArchitecture;
  alb:elb.IApplicationLoadBalancer;
  albSG:ec2.SecurityGroup;
}

export class FrontEndCluster extends Construct {
  readonly distribution;
  constructor(scope: Construct, id: string, props:FrontEndProps) {
    super(scope, id)

  // 
  // S3 + Cloud Front
  // 
  const alb_listen_port=80
  const commonBucketProps: s3.BucketProps = {
    blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    encryption: s3.BucketEncryption.S3_MANAGED,
    autoDeleteObjects: true,
    removalPolicy: RemovalPolicy.DESTROY,
    objectOwnership: s3.ObjectOwnership.OBJECT_WRITER,
    enforceSSL: true,
  };

  const { cloudFrontWebDistribution, s3BucketInterface } = new CloudFrontToS3(
    this,
    'Web',
    {
      insertHttpSecurityHeaders: false,
      loggingBucketProps: commonBucketProps,
      bucketProps: commonBucketProps,
      cloudFrontLoggingBucketProps: commonBucketProps,
      cloudFrontDistributionProps: {
        errorResponses: [
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
          },
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
          },
        ],
      },
    }
  );
  
  // const endpoint = "http://langflow-alb-1779019476.us-east-1.elb.amazonaws.com"
  const endpoint = `http://${props.alb.loadBalancerDnsName}`
  
  new NodejsBuild(this, 'BuildFrontEnd', {
    assets: [
      {
        path: '../../src/frontend',
        exclude: [
          '.git',
          '.github',
          '.gitignore',
          '.prettierignore',
          'build',
          'node_modules'
        ],
      },
    ],
    nodejsVersion:20,
    destinationBucket: s3BucketInterface,
    distribution: cloudFrontWebDistribution,
    outputSourceDirectory: 'build',
    buildCommands: ['npm install', 'npm run build'],
    buildEnvironment: {
      BACKEND_SERVICE_NAME: props.backendServiceName,
      BACKEND_URL: endpoint,
      VITE_PROXY_TARGET: endpoint,
      VITE_PORT:'443',
    },
    // workingDirectory:"../../src/frontend"
  });
  console.log(`VITE_PROXY_TARGET: ${endpoint}`)

  this.distribution = cloudFrontWebDistribution;
  // distribution から backendへのinbound 許可
  props.albSG.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(alb_listen_port))

  new CfnOutput(this, 'URL', {
    value: this.distribution.domainName,
  });
}

}