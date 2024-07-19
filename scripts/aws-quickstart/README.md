# Langflow AWS Elastic Beanstalk Quickstart

*[Leia em português](README.pt.md)*

This repository provides a quick deployment of the [Langflow](https://github.com/langflow-ai/langflow) project on AWS using Docker containers with CloudFormation. With a single click, you can deploy Langflow on Elastic Beanstalk.

## Features

- Automated deployment of Langflow on Elastic Beanstalk using Docker
- Customized configuration of the AWS Elastic Beanstalk environment

## Prerequisites

- AWS account
- Appropriate permissions to create AWS Elastic Beanstalk resources
- [AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- [Configure the AWS CLI with your credentials](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

## One-Click Deployment

Click the button below to deploy the stack to your AWS account:

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?#/stacks/create/review?stackName=LangFlowApp&templateURL=https://langflow-quickstart.s3.amazonaws.com/template-aws-quickstart.yaml)

## Deployment Instructions

1. Click the "Launch Stack" button above.
2. Review the stack details in the AWS console.
3. Click "Create stack" to start the deployment process.
4. Monitor the progress of the stack creation in the AWS console.

## Created Resources

This CloudFormation template creates the following resources:

- Custom VPC with public subnets
- Internet gateway and associated route tables
- Security group configured to allow traffic on port 7860
- AWS Elastic Beanstalk application to run the Docker container

## Notes

Make sure to replace the necessary parameters in the template before deploying.

### Performance Plans

Here are the different performance plans you can choose for your deployment:

| Characteristic     | t3.medium        | t3.large         | m5.large        | m5.xlarge       |
|--------------------|------------------|------------------|-----------------|-----------------|
| **vCPU**           | 2                | 2                | 2               | 4               |
| **Memory**         | 4 GB             | 8 GB             | 8 GB            | 16 GB           |
| **Storage**        | EBS only         | EBS only         | EBS only        | EBS only        |
| **Network**        | Moderate         | Moderate         | High            | High            |
| **Estimated Cost** | $0.0416 per hour | $0.0832 per hour | $0.096 per hour | $0.192 per hour |

### Configuration Parameters

Here are the configuration parameters for the different plans:

| Plan                     | Instance Type  | CPU       | Memory   |
|--------------------------|----------------|-----------|----------|
| **t3.medium**            | t3.medium      | 2         | 4 GB     |
| **t3.large**             | t3.large       | 2         | 8 GB     |
| **m5.large**             | m5.large       | 2         | 8 GB     |
| **m5.xlarge**            | m5.xlarge      | 4         | 16 GB    |

## Customization

If you need to customize the deployment, you can modify the `template-aws-quickstart.yaml` file as needed. For example, to use the `m5.large` plan, adjust the `InstanceType` parameter to `m5.large`.

### Using AWS CLI

To deploy the template using the AWS CLI, follow these steps:

1. Package the YAML file into a CloudFormation template:

   ```sh
   aws cloudformation package --template-file template-aws-quickstart.yaml --s3-bucket <YourS3Bucket> --output-template-file output-template.yaml
   ```
   Replace `<YourS3Bucket>` with the name of your S3 bucket.

2. Deploy the packaged template:

   ```sh
   aws cloudformation deploy --template-file output-template.yaml --stack-name LangFlowApp --capabilities CAPABILITY_NAMED_IAM
   ```

## Contributions

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License.
