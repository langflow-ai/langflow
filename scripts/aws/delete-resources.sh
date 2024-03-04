# aws cloudformation delete-stack --stack-name LangflowAppStack
aws ecr delete-repository --repository-name langflow-backend-repository --force
# aws ecr delete-repository --repository-name langflow-frontend-repository --force
# aws ecr describe-repositories --output json | jq -re ".repositories[].repositoryName"