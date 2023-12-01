# Langflow on AWS

Langflow on AWS は、 Langflow を AWS 上に展開する Project になります。
この Branch では、AWS CDK を用いて 各種 Dockerfile からコンテナイメージを ECR に展開し、ECS、Aurora MySQL を用いて Langflow を構築します。

# デプロイ
[CloudShell](https://us-east-1.console.aws.amazon.com/cloudshell/home?region=us-east-1)を開きます。

以下のコマンドを実行します。
```shell
git clone https://github.com/aws-samples/cloud9-setup-for-prototyping
cd cloud9-setup-for-prototyping
./bin/bootstrap
```

`Done!` と表示されたら [Cloud9](https://us-east-1.console.aws.amazon.com/cloud9control/home?region=us-east-1#/) から `cloud9-for-prototyping` を開きます。
![make-cloud9](./img/langflow-cloud9.png)

以下のコマンドを実行します。

```shell
git clone -b aws-cdk-dev2 https://github.com/kazuki306/langflow
cd langflow/scripts/aws
cp .env.example .env # この後envの設定が必要ならここで追記
npm ci
cdk bootstrap
cdk deploy
```
表示される URL にアクセスします。
```shell
Outputs:
LangflowAppStack.NetworkURLXXXXXX = http://alb-XXXXXXXXXXX.elb.amazonaws.com
```

# 環境の削除
`Cloud9` で以下のコマンドを実行します。
```shell
cdk destroy
```


[CloudFormation](https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/getting-started)を開き、`aws-cloud9-cloud9-for-prototyping-XXXX` を選択して削除します。
![delete-cfn](./img/langflow-cfn.png)