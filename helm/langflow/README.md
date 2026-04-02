# Langflow Helm Chart

사원별 Langflow 인스턴스를 Kubernetes에 배포하기 위한 Helm chart입니다.

## 사전 요구사항

- Kubernetes 1.24+
- Helm 3.x
- Keycloak 서버 (SSO 인증용)
- NFS 서버 또는 동적 프로비저닝 StorageClass
- Wildcard DNS: `*.aipp02.skhynix.com` → Ingress controller

## 빠른 시작

### 1. 시크릿 생성 (운영 권장)

```bash
kubectl create namespace langflow-2074795

kubectl create secret generic langflow-keycloak \
  --namespace langflow-2074795 \
  --from-literal=client-secret=YOUR_KEYCLOAK_SECRET \
  --from-literal=langflow-secret-key=YOUR_LANGFLOW_KEY
```

### 2. Harbor 레지스트리 인증 (private registry 사용 시)

```bash
kubectl create secret docker-registry harbor-cred \
  --namespace langflow-2074795 \
  --docker-server=harbor-aipp01.skhynix.com \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD
```

### 3. values 파일 작성

```yaml
# my-values.yaml
empno: "2074795"

keycloak:
  serverUrl: https://keycloak.skhynix.com
  realm: company
  clientId: langflow
  existingSecret: langflow-keycloak

ssl:
  enabled: true
  caCert: |
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----

nfs:
  enabled: true
  server: 10.0.0.1
  basePath: /nfs/data
  mountOptions:
    - nfsvers=3
  initImage: harbor-aipp01.skhynix.com/busybox/busybox:latest

langflow:
  storageClass: sc-nfs-app-retain

imagePullSecrets:
  - name: harbor-cred
```

### 4. 배포

```bash
helm install langflow ./helm/langflow \
  --namespace langflow-2074795 \
  --create-namespace \
  -f my-values.yaml
```

접속: `http://langflow-2074795.aipp02.skhynix.com`

### 5. 업그레이드

```bash
helm upgrade langflow ./helm/langflow \
  --namespace langflow-2074795 \
  -f my-values.yaml
```

### 6. 삭제

```bash
helm uninstall langflow -n langflow-2074795
kubectl delete namespace langflow-2074795
```

## 전체 설정 (values.yaml)

### 기본

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `empno` | 사원번호 (필수, 호스트명/접근제어에 사용) | `""` |
| `image.repository` | Docker 이미지 | `dk02315/langflow-hynix` |
| `image.tag` | 이미지 태그 | `v1.8.0-hynix-rc2` |
| `image.pullPolicy` | 이미지 pull 정책 | `IfNotPresent` |
| `imagePullSecrets` | Private registry 인증 | `[]` |
| `resources` | CPU/메모리 제한 | `{}` |

### Ingress

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `ingress.enabled` | Ingress 생성 여부 | `true` |
| `ingress.domain` | 기본 도메인 | `aipp02.skhynix.com` |
| `ingress.annotations` | 추가 어노테이션 | `kubernetes.io/ingress.class: nginx` |

호스트명: `langflow-<empno>.<domain>` (예: `langflow-2074795.aipp02.skhynix.com`)

### Keycloak SSO

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `keycloak.serverUrl` | Keycloak 서버 URL (필수) | `""` |
| `keycloak.realm` | Realm (필수) | `""` |
| `keycloak.clientId` | Client ID (필수) | `""` |
| `keycloak.clientSecret` | Client secret (`existingSecret` 설정 시 무시) | `""` |
| `keycloak.existingSecret` | 기존 K8s Secret 이름 | `""` |
| `keycloak.existingSecretKeys.clientSecret` | Secret 내 client-secret 키 | `client-secret` |
| `keycloak.existingSecretKeys.langflowSecretKey` | Secret 내 langflow-secret-key 키 | `langflow-secret-key` |
| `keycloak.employeeClaim` | 사원번호 추출 토큰 클레임 | `preferred_username` |
| `keycloak.buttonText` | 로그인 버튼 텍스트 | `SK하이닉스 SSO 로그인` |

### Langflow

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `langflow.secretKey` | 암호화 키 (`existingSecret` 설정 시 무시) | `""` |
| `langflow.storage` | PVC 크기 | `5Gi` |
| `langflow.storageClass` | StorageClass 이름 | `""` |
| `langflow.refreshSecure` | refresh token 쿠키 Secure 플래그 | `"false"` |
| `langflow.refreshSameSite` | refresh token 쿠키 SameSite 속성 | `"lax"` |

> HTTP 환경에서는 `refreshSecure: "false"`, `refreshSameSite: "lax"` 사용.
> HTTPS 환경에서는 `refreshSecure: "true"`, `refreshSameSite: "none"` 으로 변경.

### NFS 스토리지

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `nfs.enabled` | NFS PV 자동 생성 | `false` |
| `nfs.server` | NFS 서버 IP | `""` |
| `nfs.basePath` | NFS 기본 경로 | `""` |
| `nfs.mountOptions` | NFS 마운트 옵션 | `[]` |
| `nfs.initImage` | 디렉토리 생성용 initContainer 이미지 | `busybox:1.36` |

`nfs.enabled=true`이면:
- PV가 `basePath`를 마운트
- initContainer가 `langflow-<empno>` 하위 디렉토리를 자동 생성
- 메인 컨테이너는 `subPath: langflow-<empno>`로 해당 디렉토리만 사용

> `basePath`는 NFS 서버에 이미 존재해야 합니다. 하위 디렉토리(`langflow-<empno>`)는 자동 생성됩니다.

### SSL 인증서

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `ssl.enabled` | CA 인증서 마운트 | `false` |
| `ssl.caCert` | PEM 내용 직접 입력 | `""` |
| `ssl.existingConfigMap` | 기존 ConfigMap 사용 | `""` |
| `ssl.existingSecret` | 기존 Secret 사용 | `""` |
| `ssl.key` | ConfigMap/Secret 내 키 이름 | `ca.crt` |

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

## 여러 사원 일괄 배포

공통 values 파일 하나로 여러 사원을 배포할 수 있습니다:

```bash
for EMPNO in 2074795 2073215 2071234; do
  helm install langflow ./helm/langflow \
    --namespace langflow-${EMPNO} \
    --create-namespace \
    -f values-common.yaml \
    --set empno=${EMPNO}
done
```
