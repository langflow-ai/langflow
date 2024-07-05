import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as cdk from "aws-cdk-lib";

interface RdsProps {
  vpc: ec2.Vpc;
  dbSG: ec2.SecurityGroup;
}

export class Rds extends Construct {
  readonly rdsCluster: rds.DatabaseCluster;

  constructor(scope: Construct, id: string, props: RdsProps) {
    super(scope, id);

    const { vpc, dbSG } = props;
    const instanceType = ec2.InstanceType.of(
      ec2.InstanceClass.BURSTABLE4_GRAVITON,
      ec2.InstanceSize.MEDIUM,
    );

    // RDSのパスワードを自動生成してSecrets Managerに格納
    const rdsCredentials = rds.Credentials.fromGeneratedSecret("db_user", {
      secretName: "langflow-DbSecret",
    });

    // DB クラスターのパラメータグループ作成
    const clusterParameterGroup = new rds.ParameterGroup(
      scope,
      "ClusterParameterGroup",
      {
        engine: rds.DatabaseClusterEngine.auroraMysql({
          version: rds.AuroraMysqlEngineVersion.of(
            "8.0.mysql_aurora.3.05.2",
            "8.0",
          ),
        }),
        description: "for-langflow",
      },
    );
    clusterParameterGroup.bindToCluster({});

    // DB インスタンスのパラメタグループ作成
    const instanceParameterGroup = new rds.ParameterGroup(
      scope,
      "InstanceParameterGroup",
      {
        engine: rds.DatabaseClusterEngine.auroraMysql({
          version: rds.AuroraMysqlEngineVersion.of(
            "8.0.mysql_aurora.3.05.2",
            "8.0",
          ),
        }),
        description: "for-langflow",
      },
    );
    instanceParameterGroup.bindToInstance({});

    this.rdsCluster = new rds.DatabaseCluster(scope, "LangflowDbCluster", {
      engine: rds.DatabaseClusterEngine.auroraMysql({
        version: rds.AuroraMysqlEngineVersion.of(
          "8.0.mysql_aurora.3.05.2",
          "8.0",
        ),
      }),
      storageEncrypted: true,
      credentials: rdsCredentials,
      instanceIdentifierBase: "langflow-instance",
      vpc: vpc,
      vpcSubnets: vpc.selectSubnets({
        subnetGroupName: "langflow-Isolated",
      }),
      securityGroups: [dbSG],
      writer: rds.ClusterInstance.provisioned("WriterInstance", {
        instanceType: instanceType,
        enablePerformanceInsights: true,
        parameterGroup: instanceParameterGroup,
      }),
      // 2台目以降はreaders:で設定
      parameterGroup: clusterParameterGroup,
      defaultDatabaseName: "langflow",
    });
  }
}
