import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";

interface DbProps {
  vpc: ec2.Vpc;
  dbSG: ec2.SecurityGroup;
}

export class Db extends Construct {
  constructor(scope: Construct, id: string, props: DbProps) {
    super(scope, id);
    // No RDS resources needed as we're using local PostgreSQL
  }
}
