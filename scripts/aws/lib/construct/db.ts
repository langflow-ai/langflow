import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";

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

    this.rdsCluster = new rds.DatabaseCluster(scope, "LangflowDbCluster", {
      engine: rds.DatabaseClusterEngine.auroraMysql({
        version: rds.AuroraMysqlEngineVersion.VER_3_06_0,
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
      }),
      // 2台目以降はreaders:で設定
      defaultDatabaseName: "langflow",
    });
  }
}
