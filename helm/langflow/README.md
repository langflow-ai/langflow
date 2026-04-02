# Langflow Helm Chart

사원별 Langflow 인스턴스를 Kubernetes에 배포하기 위한 Helm chart입니다.
Keycloak SSO 연동, NFS 스토리지, SSL 인증서를 지원합니다.

## 사전 요구사항

- Kubernetes 1.24+
- Helm 3.x
- Keycloak 서버 (SSO 인증용)
- NFS 서버 또는 동적 프로비저닝이 가능한 StorageClass

## 빠른 시작

### 1. values 파일 작성

```yaml
empno: "2074795"

keycloak:
  serverUrl: https://keycloak.skhynix.com
  realm: your-realm
  clientId: your-client-id
  clientSecret: your-client-secret

langflow:
  secretKey: your-random-secret-key
  storageClass: sc-nfs-app-retain

nfs:
  enabled: true
  server: 10.0.0.1
  basePath: /nfs/langflow
```

### 2. 배포

```bash
helm install langflow ./helm/langflow \
  --namespace langflow-2074795 \
  --create-namespace \
  -f my-values.yaml
```

배포 후 `https://langflow-2074795.aipp02.skhynix.com`으로 접속할 수 있습니다.

### 3. 업그레이드

```bash
helm upgrade langflow ./helm/langflow \
  --namespace langflow-2074795 \
  -f my-values.yaml
```

### 4. 삭제

```bash
helm uninstall langflow -n langflow-2074795
kubectl delete namespace langflow-2074795
```

## 설정 (values.yaml)

### 필수 설정

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `empno` | 사원번호 (호스트명, 접근 제어에 사용) | `"2074795"` |
| `keycloak.serverUrl` | Keycloak 서버 URL | `https://keycloak.skhynix.com` |
| `keycloak.realm` | Keycloak realm | `your-realm` |
| `keycloak.clientId` | Keycloak client ID | `langflow` |
| `keycloak.clientSecret` | Keycloak client secret | (existingSecret 사용 시 생략 가능) |
| `langflow.secretKey` | Langflow 암호화 키 | (existingSecret 사용 시 생략 가능) |

### 스토리지 설정

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `langflow.storage` | `5Gi` | PVC 크기 |
| `langflow.storageClass` | `""` | StorageClass 이름 (예: `sc-nfs-app-retain`) |
| `nfs.enabled` | `false` | NFS PV 자동 생성 여부 |
| `nfs.server` | `""` | NFS 서버 IP |
| `nfs.basePath` | `""` | NFS 기본 경로 (`/<empno>` 자동 추가) |

`nfs.enabled=true`이면 Helm이 PersistentVolume을 자동 생성합니다.
NFS 경로는 `<basePath>/<empno>` 형태로 설정됩니다 (예: `/nfs/langflow/2074795`).

> NFS 서버에 해당 디렉토리가 미리 존재해야 합니다.

### SSL 인증서

사내 PKI CA 인증서가 필요한 경우:

```yaml
ssl:
  enabled: true
  # 방법 1: PEM 내용 직접 입력
  caCert: |
    -----BEGIN CERTIFICATE-----
    MIIFazCCA1OgAwIBAgIUe...
    -----END CERTIFICATE-----

  # 방법 2: 기존 ConfigMap 사용
  existingConfigMap: my-ca-configmap

  # 방법 3: 기존 Secret 사용
  existingSecret: my-ca-secret
```

### 시크릿 관리

**방법 1**: values에 직접 입력 (테스트용)

```yaml
keycloak:
  clientSecret: my-secret
langflow:
  secretKey: my-langflow-key
```

**방법 2**: 기존 K8s Secret 참조 (운영 권장)

```bash
kubectl create secret generic langflow-keycloak \
  --namespace langflow-2074795 \
  --from-literal=client-secret=YOUR_SECRET \
  --from-literal=langflow-secret-key=YOUR_LANGFLOW_KEY
```

```yaml
keycloak:
  existingSecret: langflow-keycloak
```

### Ingress 설정

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `ingress.enabled` | `true` | Ingress 생성 여부 |
| `ingress.domain` | `aipp02.skhynix.com` | 기본 도메인 |
| `ingress.annotations` | `{}` | 추가 어노테이션 |

호스트명은 `langflow-<empno>.<domain>` 형식으로 자동 생성됩니다.

### 리소스 제한

```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2
    memory: 4Gi
```

## Docker Compose (대안)

Kubernetes 없이 단독 실행하려면 프로젝트 루트의 `docker-compose.yml`을 사용하세요.

```bash
# .env 파일 작성
cat > .env << 'EOF'
EMPNO=2074795
LANGFLOW_SECRET_KEY=your-secret
KEYCLOAK_SERVER_URL=https://keycloak.skhynix.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=your-client-id
KEYCLOAK_CLIENT_SECRET=your-client-secret
KEYCLOAK_REDIRECT_URI=http://localhost:7860/api/v1/keycloak/callback
EOF

# 실행
docker compose up -d
```

## 생성되는 리소스

| 리소스 | 이름 | 조건 |
|-------|------|------|
| Deployment | `langflow-<empno>` | 항상 |
| Service | `langflow-<empno>` | 항상 |
| PVC | `langflow-<empno>-data` | 항상 |
| PV | `langflow-<empno>-data` | `nfs.enabled=true` |
| Secret | `langflow-<empno>-secret` | `existingSecret` 미설정 시 |
| Ingress | `langflow-<empno>` | `ingress.enabled=true` |
| ConfigMap | `langflow-<empno>-ca-cert` | `ssl.enabled=true` + `ssl.caCert` 설정 시 |
