# Langflow on AWS

Langflow on AWS では、 Langflow を AWS 上にデプロイする方法を学べます。

このチュートリアルは、AWS アカウントと AWS に関する基本的な知識を有していることを前提としています。


# 環境構築とデプロイ方法
1. [CloudShell](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1)を開きます。

1. 以下のコマンドを実行します。
```shell
git clone https://github.com/aws-samples/cloud9-setup-for-prototyping
cd cloud9-setup-for-prototyping
./bin/bootstrap
```

1. `Done!` と表示されたら [Cloud9](https://us-east-1.console.aws.amazon.com/cloud9control/home?region=us-east-1#/) から `cloud9-for-prototyping` を開きます。
![make-cloud9](./img/langflow-cloud9.png)

1. 以下のコマンドを実行します。
```shell
git clone -b aws-cdk-dev2 https://github.com/kazuki306/langflow
cd langflow/scripts/aws
cp .env.example .env # 環境設定を変える場合はこのファイル(.env)を編集してください。
npm ci
cdk bootstrap
cdk deploy
```
1. 表示される URL にアクセスします。
```shell
Outputs:
LangflowAppStack.NetworkURLXXXXXX = http://alb-XXXXXXXXXXX.elb.amazonaws.com
```

# 環境の削除
1. `Cloud9` で以下のコマンドを実行します。
```shell
cdk destroy
```


1. [CloudFormation](https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/getting-started)を開き、`aws-cloud9-cloud9-for-prototyping-XXXX` を選択して削除します。
![delete-cfn](./img/langflow-cfn.png)