import { Stack, Duration, RemovalPolicy, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_ec2 as ec2,
  aws_ecs as ecs,
  aws_s3 as s3,
  aws_iam as iam,
  aws_logs as logs,
  aws_elasticloadbalancingv2 as elb,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
  aws_s3_deployment as s3_deployment
} from 'aws-cdk-lib';
import { CloudFrontToS3 } from '@aws-solutions-constructs/aws-cloudfront-s3';
import { CfnDistribution, Distribution } from 'aws-cdk-lib/aws-cloudfront';
import { NodejsBuild } from 'deploy-time-build';

interface WebProps {
  cluster:ecs.Cluster
  alb:elb.IApplicationLoadBalancer;
  albSG:ec2.SecurityGroup;
}

export class Web extends Construct {
  readonly distribution;
  constructor(scope: Construct, id: string, props:WebProps) {
    super(scope, id)

  const commonBucketProps: s3.BucketProps = {
    blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    encryption: s3.BucketEncryption.S3_MANAGED,
    autoDeleteObjects: true,
    removalPolicy: RemovalPolicy.DESTROY,
    objectOwnership: s3.ObjectOwnership.OBJECT_WRITER,
    enforceSSL: true,
  };

  // CDKにて 静的WebサイトをホストするためのAmazon S3バケットを作成
  const websiteBucket = new s3.Bucket(this, 'LangflowWebsiteBucket', commonBucketProps);

  const originAccessIdentity = new cloudfront.OriginAccessIdentity(
    this,
    'OriginAccessIdentity',
    {
      comment: 'langflow-distribution-originAccessIdentity',
    }
  );

  const webSiteBucketPolicyStatement = new iam.PolicyStatement({
    actions: ['s3:GetObject'],
    effect: iam.Effect.ALLOW,
    principals: [
      new iam.CanonicalUserPrincipal(
        originAccessIdentity.cloudFrontOriginAccessIdentityS3CanonicalUserId
      ),
    ],
    resources: [`${websiteBucket.bucketArn}/*`],
  });

  websiteBucket.addToResourcePolicy(webSiteBucketPolicyStatement);
  websiteBucket.grantRead(originAccessIdentity);

  const s3SpaOrigin = new origins.S3Origin(websiteBucket);
  const ApiSpaOrigin = new origins.LoadBalancerV2Origin(props.alb,{
    protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY
  });

  const albBehaviorOptions = {
    origin: ApiSpaOrigin,
    allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,

    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.ALLOW_ALL,
    cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
    originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
  }

  const cloudFrontWebDistribution = new cloudfront.Distribution(this, 'distribution', {
    comment: 'langflow-distribution',
    defaultRootObject: 'index.html',
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
    defaultBehavior: { origin:  s3SpaOrigin },
    additionalBehaviors: {
      '/api/v1/*': albBehaviorOptions,
      '/api/v2/*': albBehaviorOptions,
      '/health' : albBehaviorOptions,
    },
    enableLogging: true, // ログ出力設定
    logBucket: new s3.Bucket(this, 'LogBucket',commonBucketProps),
    logFilePrefix: 'distribution-access-logs/',
    logIncludesCookies: true,
  });
  this.distribution = cloudFrontWebDistribution;


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
    destinationBucket: websiteBucket,
    distribution: cloudFrontWebDistribution,
    outputSourceDirectory: 'build',
    buildCommands: ['npm install', 'npm run build'],
    buildEnvironment: {
      // VITE_AXIOS_BASE_URL: `https://${this.distribution.domainName}`
    },
  });

  // distribution から backendへのinbound 許可
  const alb_listen_port=80
  props.albSG.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(alb_listen_port))
  const alb_listen_port_443=443
  props.albSG.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(alb_listen_port_443))


  new CfnOutput(this, 'URL', {
    value: `https://${this.distribution.domainName}`,
  });
}

}
