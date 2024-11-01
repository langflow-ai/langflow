import * as kendra from 'aws-cdk-lib/aws-kendra';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { Duration, Token, Arn } from 'aws-cdk-lib';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';
import { Runtime } from 'aws-cdk-lib/aws-lambda';

export interface RagProps {
}

/**
 * RAG を実行するためのリソースを作成する
 */
export class Rag extends Construct {
  constructor(scope: Construct, id: string, props: RagProps) {
    super(scope, id);

    const kendraIndexArnInCdkContext =
      this.node.tryGetContext('kendraIndexArn');

    let kendraIndexArn: string;
    let kendraIndexId: string;

    if (kendraIndexArnInCdkContext) {
      // 既存の Kendra Index を利用する場合
      kendraIndexArn = kendraIndexArnInCdkContext!;
      kendraIndexId = Arn.extractResourceName(
        kendraIndexArnInCdkContext,
        'index'
      );
    } else {
      // 新規に Kendra Index を作成する場合
      const indexRole = new iam.Role(this, 'KendraIndexRole', {
        assumedBy: new iam.ServicePrincipal('kendra.amazonaws.com'),
      });

      indexRole.addToPolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          resources: ['*'],
          actions: ['s3:GetObject'],
        })
      );

      indexRole.addManagedPolicy(
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLogsFullAccess')
      );

      const index = new kendra.CfnIndex(this, 'KendraIndex', {
        name: 'langflow-index',
        edition: 'DEVELOPER_EDITION',
        roleArn: indexRole.roleArn,
      });

      kendraIndexArn = Token.asString(index.getAtt('Arn'));
      kendraIndexId = index.ref;

      // WebCrawler を作成
      const webCrawlerRole = new iam.Role(this, 'KendraWebCrawlerRole', {
        assumedBy: new iam.ServicePrincipal('kendra.amazonaws.com'),
      });
      webCrawlerRole.addToPolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          resources: [kendraIndexArn],
          actions: ['kendra:BatchPutDocument', 'kendra:BatchDeleteDocument'],
        })
      );

      new kendra.CfnDataSource(this, 'WebCrawler', {
        indexId: kendraIndexId,
        name: 'WebCrawler',
        type: 'WEBCRAWLER',
        roleArn: webCrawlerRole.roleArn,
        languageCode: 'ja',
        dataSourceConfiguration: {
          webCrawlerConfiguration: {
            urls: {
              seedUrlConfiguration: {
                webCrawlerMode: 'HOST_ONLY',
                // デモ用に AWS の GenAI 関連のページを取り込む
                seedUrls: [
                  'https://aws.amazon.com/jp/what-is/generative-ai/',
                  'https://aws.amazon.com/jp/generative-ai/',
                  'https://aws.amazon.com/jp/generative-ai/use-cases/',
                  'https://aws.amazon.com/jp/bedrock/',
                  'https://aws.amazon.com/jp/bedrock/features/',
                  'https://aws.amazon.com/jp/bedrock/testimonials/',
                ],
              },
            },
            crawlDepth: 1,
            urlInclusionPatterns: ['https://aws.amazon.com/jp/.*'],
          },
        },
      });
    }

    // RAG 関連の API を追加する
    // Lambda
    const queryFunction = new NodejsFunction(this, 'Query', {
      runtime: Runtime.NODEJS_18_X,
      entry: './lambda/queryKendra.ts',
      timeout: Duration.minutes(15),
      bundling: {
        // 新しい Kendra の機能を使うため、AWS SDK を明示的にバンドルする
        externalModules: [],
      },
      environment: {
        INDEX_ID: kendraIndexId,
      },
    });
    queryFunction.role?.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        resources: [kendraIndexArn],
        actions: ['kendra:Query'],
      })
    );

    const retrieveFunction = new NodejsFunction(this, 'Retrieve', {
      runtime: Runtime.NODEJS_18_X,
      entry: './lambda/retrieveKendra.ts',
      timeout: Duration.minutes(15),
      bundling: {
        // 新しい Kendra の機能を使うため、AWS SDK を明示的にバンドルする
        externalModules: [],
      },
      environment: {
        INDEX_ID: kendraIndexId,
      },
    });
    retrieveFunction.role?.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        resources: [kendraIndexArn],
        actions: ['kendra:Retrieve'],
      })
    );
  }
}
