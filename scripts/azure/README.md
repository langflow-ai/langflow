# Langflow Azure ARM Quickstart

This repository provides a quickstart deployment of the [Langflow](https://github.com/langflow-ai/langflow) project on Azure using Docker containers with Bicep templates. With a single click, you can deploy Langflow to Azure App Service.

## Features

- Automated deployment of Langflow on Azure App Service using Docker
- Python 3.10 environment
- Integration with Application Insights for monitoring
- Custom configuration to expose port 7860 internally and 443 externally

## Getting Started

### Prerequisites

- Azure Subscription
- GitHub account
- [Azure CLI installed](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Bicep CLI installed](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/install)

### Deployment

1. Create the Resource Group:

   ```
   az group create --name <YourResourceGroup> --location <location>
   ```
   Replace `<YourResourceGroup>` with the desired name for your Resource Group and `<location>` with the desired Azure region (e.g., `EastUS`, `WestUS`, `NorthEurope`, etc.).


2. Click the button below to deploy Langflow to Azure:

   [![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fdanielgines%2Flangflow-azure-arm-quickstart%2Fmain%2Fazure-deploy.json)


3. Follow the instructions in the Azure portal to complete the deployment.

**Attention:** The first deployment may take several minutes to complete. Please wait until the deployment process is finalized. Once completed, open the default domain provided on the Overview screen of the Web App to access Langflow.

4. To visualize the template, click the button below:

   [![Visualize](https://raw.githubusercontent.com/Azure/azure-quickstart-templates/master/1-CONTRIBUTION-GUIDE/images/visualizebutton.svg?sanitize=true)](https://armviz.io/#/?load=https%3A%2F%2Fraw.githubusercontent.com%2Fdanielgines%2Flangflow-azure-arm-quickstart%2Fmain%2Fazure-deploy.json)

### Performance Plans

Here are the different performance plans you can choose for your deployment:

| Characteristic           | Free (F1)                      | Standard (S1)                        | Premium (P1v2)                      | Premium (P2v2)                      |
|--------------------------|--------------------------------|--------------------------------------|-------------------------------------|-------------------------------------|
| **CPU**                  | Shared                         | 1 dedicated core                     | 1 dedicated core                    | 2 dedicated cores                   |
| **Memory**               | Very limited                   | 1.75 GB                              | 3.5 GB                              | 7 GB                                |
| **Runtime**              | Limited                        | Unlimited                            | Unlimited                           | Unlimited                           |
| **SSL/HTTPS**            | Limited                        | Full                                 | Full                                | Full                                |
| **Storage**              | Limited, no persistence        | 50 GB                                | 250 GB                              | 250 GB                              |
| **Scalability**          | No                             | Up to 10 instances                   | Up to 30 instances                  | Up to 30 instances                  |
| **Deployment Slots**     | No                             | 5 slots                              | 20 slots                            | 20 slots                            |
| **Automatic Backups**    | No                             | Yes                                  | Yes                                 | Yes                                 |
| **Advanced Monitoring**  | No                             | Yes (with Application Insights)      | Yes (with Application Insights)     | Yes (with Application Insights)     |
| **Virtual Network**      | No                             | Yes                                  | Yes                                 | Yes                                 |

### Configuration Parameters

Here are the configuration parameters for the different plans:

| Plan                    | SKU           | SKU Code | Worker Size |
|-------------------------|---------------|----------|-------------|
| **Free**                | Free          | F1       | 0           |
| **Standard**            | Standard      | S1       | 1           |
| **Premium (P1v2)**      | PremiumV2     | P1v2     | 1           |
| **Premium (P2v2)**      | PremiumV2     | P2v2     | 2           |

### Customization

If you need to customize the deployment, you can modify the `azure-deploy.bicep` file as needed. For example, to use the Premium (P1v2) plan, set the variables as follows:

```
var sku = 'PremiumV2'
var skuCode = 'P1v2'
var workerSize = 1
```

### Using Azure CLI

To deploy the template using the Azure CLI, follow these steps:

1. Compile the Bicep file to an ARM template:

   ```
   bicep build azure-deploy.bicep
   ```
   This will generate an `azure-deploy.json` file.


2. Deploy the compiled ARM template:

   ```
   az deployment group create --resource-group <YourResourceGroup> --template-file azure-deploy.json
   ```
   Replace `<YourResourceGroup>` with the name of your Azure Resource Group.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License.