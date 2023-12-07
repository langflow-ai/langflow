import { RemovalPolicy } from 'aws-cdk-lib'
import * as ecr from 'aws-cdk-lib/aws-ecr'
import * as ecrdeploy from 'cdk-ecr-deployment'
import * as ecs from 'aws-cdk-lib/aws-ecs'
import * as servicediscovery from 'aws-cdk-lib/aws-servicediscovery'
import { DockerImageAsset, Platform } from 'aws-cdk-lib/aws-ecr-assets'
import * as path from "path";
import { Construct } from 'constructs'


interface ECRProps {
  cloudmapNamespace: servicediscovery.PrivateDnsNamespace;
  arch:ecs.CpuArchitecture;
}

export class EcrRepository extends Construct {
  readonly ecrFrontEndRepository: ecr.Repository
  readonly ecrBackEndRepository: ecr.Repository

  constructor(scope: Construct, id: string, props: ECRProps) {
    super(scope, id)

    const imagePlatform = props.arch == ecs.CpuArchitecture.ARM64 ? Platform.LINUX_ARM64 : Platform.LINUX_AMD64
    const backendPath = path.join(__dirname, "../../../../../", "langflow")
    const frontendPath = path.join(__dirname, "../../../../src/", "frontend")
    const excludeDir = ['node_modules','.git', 'cdk.out']
    const LifecycleRule = {
      tagStatus: ecr.TagStatus.ANY,
      description: 'Delete more than 30 image',
      maxImageCount: 30,
    }

    // リポジトリ作成
    this.ecrFrontEndRepository = new ecr.Repository(scope, 'LangflowFrontEndRepository', {
      repositoryName: 'langflow-frontend-repository',
      removalPolicy: RemovalPolicy.RETAIN,
      imageScanOnPush: true,
    })
    this.ecrBackEndRepository = new ecr.Repository(scope, 'LangflowBackEndRepository', {
      repositoryName: 'langflow-backend-repository',
      removalPolicy: RemovalPolicy.RETAIN,
      imageScanOnPush: true,
    })
    // LifecycleRule作成
    this.ecrFrontEndRepository.addLifecycleRule(LifecycleRule)
    this.ecrBackEndRepository.addLifecycleRule(LifecycleRule)

    // Create Docker Image Asset
    const dockerFrontEndImageAsset = new DockerImageAsset(this, "DockerFrontEndImageAsset", {
      directory: frontendPath,
      file:"cdk.Dockerfile",
      buildArgs:{
        "BACKEND_URL":`http://backend.${props.cloudmapNamespace.namespaceName}:7860`
      },
      exclude: excludeDir,
      platform: imagePlatform,
    });
    const dockerBackEndImageAsset = new DockerImageAsset(this, "DockerBackEndImageAsset", {
      directory: backendPath,
      file:"cdk.Dockerfile",
      exclude: excludeDir,
      platform: imagePlatform,
    });

    // Deploy Docker Image to ECR Repository
    new ecrdeploy.ECRDeployment(this, "DeployFrontEndImage", {
      src: new ecrdeploy.DockerImageName(dockerFrontEndImageAsset.imageUri),
      dest: new ecrdeploy.DockerImageName(this.ecrFrontEndRepository.repositoryUri)
    });

    // Deploy Docker Image to ECR Repository
    new ecrdeploy.ECRDeployment(this, "DeployBackEndImage", {
      src: new ecrdeploy.DockerImageName(dockerBackEndImageAsset.imageUri),
      dest: new ecrdeploy.DockerImageName(this.ecrBackEndRepository.repositoryUri)
    });

  }
}
