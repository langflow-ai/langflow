import { RemovalPolicy, CfnOutput } from 'aws-cdk-lib'
import * as ecr from 'aws-cdk-lib/aws-ecr'
import * as ecrdeploy from 'cdk-ecr-deployment'
import * as ecs from 'aws-cdk-lib/aws-ecs'
import * as servicediscovery from 'aws-cdk-lib/aws-servicediscovery'
import { DockerImageAsset, Platform } from 'aws-cdk-lib/aws-ecr-assets'
import * as path from "path";
import { Construct } from 'constructs'


interface ECRProps {
  arch:ecs.CpuArchitecture;
}

export class EcrRepository extends Construct {
  readonly ecrBackEndRepository: ecr.Repository

  constructor(scope: Construct, id: string, props: ECRProps) {
    super(scope, id)

    const imagePlatform = props.arch == ecs.CpuArchitecture.ARM64 ? Platform.LINUX_ARM64 : Platform.LINUX_AMD64
    const dockerfilePath = path.join(__dirname, "../../../docker/cdk.Dockerfile")
    const excludeDir = [
      'node_modules',
      '.git', 
      '**/cdk.out',
      '.venv',
      '**/__pycache__',
      '**/dist',
      '**/build',
      '**/tmp',
      '.mypy_cache'
    ]
    const LifecycleRule = {
      tagStatus: ecr.TagStatus.ANY,
      description: 'Delete more than 30 image',
      maxImageCount: 30,
    }

    // Backend ECR リポジトリ作成
    this.ecrBackEndRepository = new ecr.Repository(scope, 'LangflowBackEndRepository', {
      repositoryName: 'langflow-backend-repository',
      removalPolicy: RemovalPolicy.RETAIN,
      imageScanOnPush: true,
    })
    
    // Add output to see the repository URI
    new CfnOutput(this, 'RepositoryUri', {
      value: this.ecrBackEndRepository.repositoryUri,
      description: 'The URI of the ECR repository'
    })

    // LifecycleRule作成
    this.ecrBackEndRepository.addLifecycleRule(LifecycleRule)

    // Create Docker Image Asset
    const dockerBackEndImageAsset = new DockerImageAsset(this, "DockerBackEndImageAsset", {
      directory: path.join(__dirname, "../../../.."),
      file: "docker/cdk.Dockerfile",
      exclude: excludeDir,
      platform: imagePlatform,
    });

    // Add output to see the Docker image URI
    new CfnOutput(this, 'DockerImageUri', {
      value: dockerBackEndImageAsset.imageUri,
      description: 'The URI of the Docker image'
    })

    // Deploy Docker Image to ECR Repository
    new ecrdeploy.ECRDeployment(this, "DeployBackEndImage", {
      src: new ecrdeploy.DockerImageName(dockerBackEndImageAsset.imageUri),
      dest: new ecrdeploy.DockerImageName(this.ecrBackEndRepository.repositoryUri)
    });
  }
}
