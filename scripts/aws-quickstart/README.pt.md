# Langflow AWS Elastic Beanstalk Quickstart

*[Read in English](README.md)*

Este repositório fornece um deployment rápido do projeto [Langflow](https://github.com/langflow-ai/langflow) na AWS usando contêineres Docker com CloudFormation. Com um único clique, você pode fazer o deploy do Langflow no Elastic Beanstalk.

## Funcionalidades

- Deploy automatizado do Langflow no Elastic Beanstalk usando Docker
- Configuração personalizada do ambiente AWS Elastic Beanstalk

## Pré-requisitos

- Conta AWS
- Permissões adequadas para criar recursos AWS Elastic Beanstalk
- [AWS CLI instalada](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- [Configuração do AWS CLI com suas credenciais](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

## Deploy com 1 Clique

Clique no botão abaixo para fazer o deploy da stack na sua conta AWS:

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/create/review?stackName=LangFlowApp&templateURL=https://langflow-quickstart.s3.amazonaws.com/template-aws-quickstart.yaml)

## Instruções de Deploy

1. Clique no botão "Launch Stack" acima.
2. Revise os detalhes da stack no console da AWS.
3. Clique em "Create stack" para iniciar o processo de deploy.
4. Acompanhe o progresso da criação da stack no console da AWS.

## Recursos Criados

Este modelo CloudFormation cria os seguintes recursos:

- VPC personalizada com sub-redes públicas
- Gateway de Internet e tabelas de rotas associadas
- Grupo de segurança configurado para permitir tráfego na porta 7860
- Aplicação AWS Elastic Beanstalk para rodar o contêiner Docker

## Notas

Certifique-se de substituir os parâmetros necessários no modelo antes de fazer o deploy.

### Performance Plans

Aqui estão os diferentes planos de desempenho que você pode escolher para seu deployment:

| Característica           | t3.medium                       | t3.large                        | m5.large                       | m5.xlarge                       |
|--------------------------|---------------------------------|---------------------------------|--------------------------------|---------------------------------|
| **vCPU**                 | 2                               | 2                               | 2                              | 4                               |
| **Memória**              | 4 GB                            | 8 GB                            | 8 GB                           | 16 GB                           |
| **Armazenamento**        | EBS apenas                      | EBS apenas                      | EBS apenas                     | EBS apenas                      |
| **Rede**                 | Moderada                        | Moderada                        | Alta                           | Alta                            |
| **Custo estimado**       | $0.0416 por hora                | $0.0832 por hora                | $0.096 por hora                | $0.192 por hora                 |

### Parâmetros de Configuração

Aqui estão os parâmetros de configuração para os diferentes planos:

| Plano                     | Tipo de Instância  | CPU       | Memória   |
|---------------------------|--------------------|-----------|-----------|
| **t3.medium**             | t3.medium          | 2         | 4 GB      |
| **t3.large**              | t3.large           | 2         | 8 GB      |
| **m5.large**              | m5.large           | 2         | 8 GB      |
| **m5.xlarge**             | m5.xlarge          | 4         | 16 GB     |

## Customização

Se você precisar customizar o deployment, pode modificar o arquivo `template-aws-quickstart.yaml` conforme necessário. Por exemplo, para usar o plano `m5.large`, ajuste o parâmetro `InstanceType` para `m5.large`.

### Usando AWS CLI

Para fazer o deploy do modelo usando o AWS CLI, siga os passos abaixo:

1. Compile o arquivo YAML para um modelo CloudFormation:

   ```sh
   aws cloudformation package --template-file template-aws-quickstart.yaml --s3-bucket <SeuBucketS3> --output-template-file output-template.yaml
   ```
   Substitua `<SeuBucketS3>` pelo nome do seu bucket S3.

2. Faça o deploy do modelo compilado:

   ```sh
   aws cloudformation deploy --template-file output-template.yaml --stack-name LangFlowApp --capabilities CAPABILITY_NAMED_IAM
   ```

## Contribuições

Contribuições são bem-vindas! Por favor, faça um fork do repositório e envie um pull request.

## Licença

Este projeto é licenciado sob a Licença MIT.
