import { RemovalPolicy } from 'aws-cdk-lib'
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
    const backendPath = path.join(__dirname, "../../../../", "docker")
    const excludeDir = ['node_modules','.git', 'cdk.out']
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
    // LifecycleRule作成
    this.ecrBackEndRepository.addLifecycleRule(LifecycleRule)

    // Create Docker Image Asset
    const dockerBackEndImageAsset = new DockerImageAsset(this, "DockerBackEndImageAsset", {
      directory: backendPath,
      file:"cdk.Dockerfile",
      exclude: excludeDir,
      platform: imagePlatform,
    });

    // Deploy Docker Image to ECR Repository
    new ecrdeploy.ECRDeployment(this, "DeployBackEndImage", {
      src: new ecrdeploy.DockerImageName(dockerBackEndImageAsset.imageUri),
      dest: new ecrdeploy.DockerImageName(this.ecrBackEndRepository.repositoryUri)
    });

  }
}
