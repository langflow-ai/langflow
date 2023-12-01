# Deploy Langflow on AWS

In this tutorial, you will learn how to deploy langflow on AWS using CDK.

This tutorial assumes you have an AWS account and basic knowledge of AWS.

# How to set up your environment and deploy langflow
1. Open [CloudShell](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1).
1. Run the following commands in Cloudshell:
    ```shell
    git clone https://github.com/aws-samples/cloud9-setup-for-prototyping
    cd cloud9-setup-for-prototyping
    ./bin/bootstrap
    ```
1. When you see `Done!` in Cloudshell, open `cloud9-for-prototyping` from [Cloud9](https://us-east-1.console.aws.amazon.com/cloud9control/home?region=us-east-1#/).
    ![make-cloud9](./img/langflow-cloud9-en.png)
1. Run the following command in the Cloud9 terminal.
    ```shell
    git clone -b aws-cdk-dev2 https://github.com/kazuki306/langflow
    cd langflow/scripts/aws
    cp .env.example .env # Edit this file if you need environment settings
    npm ci
    cdk bootstrap
    cdk deploy
    ```
1. Access the URL displayed.
    ```shell
    Outputs:
    LangflowAppStack.NetworkURLXXXXXX = http://alb-XXXXXXXXXXX.elb.amazonaws.com
    ```

# Cleanup
1. Run the following command in the `Cloud9` terminal.
    ```shell
    cdk destroy
    bash delete-ecr.sh
    ```
1. Open [CloudFormation](https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/getting-started), select `aws-cloud9-cloud9-for-prototyping-XXXX` and delete it.
![delete-cfn](./img/langflow-cfn.png)