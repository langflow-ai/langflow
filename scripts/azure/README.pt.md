# Langflow Azure ARM Quickstart

*[Read in English](README.md)*

Este repositório fornece um guia rápido para implantação do projeto [Langflow](https://github.com/langflow-ai/langflow) na Azure usando contêineres Docker com modelos Bicep. Com um único clique, você pode implantar o Langflow no Azure App Service.

## Funcionalidades

- Implantação automatizada do Langflow no Azure App Service usando Docker
- Ambiente Python 3.10
- Integração com Application Insights para monitoramento
- Configuração personalizada para expor a porta 7860 internamente e 443 externamente

## Começando

### Pré-requisitos

- Assinatura da Azure
- Conta no GitHub
- [Azure CLI instalado](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Bicep CLI instalado](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install)

### Implantação

1. Crie o Resource Group:

   ```
   az group create --name <SeuResourceGroup> --location <localizacao>
   ```

   Substitua `<SeuResourceGroup>` pelo nome desejado para o seu Resource Group e `<localizacao>` pela região da Azure desejada (ex.: `EastUS`, `WestUS`, `NorthEurope`, etc.).

2. Clique no botão abaixo para implantar o Langflow na Azure:

   [![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fdanielgines%2Flangflow-azure-arm-quickstart%2Fmain%2Fazure-deploy.json)

3. Siga as instruções no portal da Azure para completar a implantação.

4. Para visualizar o modelo, clique no botão abaixo:

   [![Visualize](https://raw.githubusercontent.com/Azure/azure-quickstart-templates/master/1-CONTRIBUTION-GUIDE/images/visualizebutton.svg?sanitize=true)](https://armviz.io/#/?load=https%3A%2F%2Fraw.githubusercontent.com%2Fdanielgines%2Flangflow-azure-arm-quickstart%2Fmain%2Fazure-deploy.json)

>   **Atenção:** A primeira implantação pode levar vários minutos para ser concluída. Por favor, aguarde até que o processo de implantação seja finalizado. Uma vez concluído, abra o domínio padrão fornecido na tela de visão geral do Web App para acessar o Langflow.

### Planos de Desempenho

Aqui estão os diferentes planos de desempenho que você pode escolher para sua implantação:

| Característica             | Free (F1)                  | Standard (S1)                  | Premium (P1v2)                 | Premium (P2v2)                 |
|----------------------------|----------------------------|--------------------------------|--------------------------------|--------------------------------|
| **CPU**                    | Compartilhada              | 1 núcleo dedicado              | 1 núcleo dedicado              | 2 núcleos dedicados            |
| **Memória**                | Muito limitada             | 1.75 GB                        | 3.5 GB                         | 7 GB                           |
| **Tempo de Execução**      | Limitado                   | Ilimitado                      | Ilimitado                      | Ilimitado                      |
| **SSL/HTTPS**              | Limitado                   | Completo                       | Completo                       | Completo                       |
| **Armazenamento**          | Limitado, sem persistência | 50 GB                          | 250 GB                         | 250 GB                         |
| **Escalabilidade**         | Não                        | Até 10 instâncias              | Até 30 instâncias              | Até 30 instâncias              |
| **Slots de Deployment**    | Não                        | 5 slots                        | 20 slots                       | 20 slots                       |
| **Backups Automáticos**    | Não                        | Sim                            | Sim                            | Sim                            |
| **Monitoramento Avançado** | Não                        | Sim (com Application Insights) | Sim (com Application Insights) | Sim (com Application Insights) |
| **Rede Virtual**           | Não                        | Sim                            | Sim                            | Sim                            |

### Parâmetros de Configuração

Aqui estão os parâmetros de configuração para os diferentes planos:

| Plano                   | SKU           | Código SKU | Tamanho do Worker |
|-------------------------|---------------|------------|-------------------|
| **Free**                | Free          | F1         | 0                 |
| **Standard**            | Standard      | S1         | 1                 |
| **Premium (P1v2)**      | PremiumV2     | P1v2       | 1                 |
| **Premium (P2v2)**      | PremiumV2     | P2v2       | 2                 |

### Customização

Se você precisar customizar a implantação, pode modificar o arquivo `azure-deploy.bicep` conforme necessário. Por exemplo, para usar o plano Premium (P1v2), defina as variáveis da seguinte forma:

   ```
   var sku = 'PremiumV2'
   var skuCode = 'P1v2'
   var workerSize = 1
   ```

### Usando o Azure CLI

Para implantar o modelo usando o Azure CLI, siga estes passos:

1. Compile o arquivo Bicep para um modelo ARM:

   ```
   bicep build azure-deploy.bicep
   ```

   Isso irá gerar um arquivo `azure-deploy.json`.

2. Implemente o template ARM compilado:

   ```
   az deployment group create --resource-group <SeuResourceGroup> --template-file azure-deploy.json
   ```

   Substitua <SeuResourceGroup> pelo nome do seu Resource Group na Azure.

## Contribuindo

Contribuições são bem-vindas! Por favor, faça um fork do repositório e envie um pull request.

## Licença

Este projeto está licenciado sob a licença MIT.
