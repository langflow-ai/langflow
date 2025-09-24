{{/*
Expand the name of the chart.
*/}}
{{- define "genesis-studio-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "genesis-studio-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "genesis-studio-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "genesis-studio-service.labels" -}}
helm.sh/chart: {{ include "genesis-studio-service.chart" . }}
{{ include "genesis-studio-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.extraLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "genesis-studio-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "genesis-studio-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "genesis-studio-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "genesis-studio-service.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}


{{/* Determine selected storage type */}}
{{- define "selectedStorageType" }}
  {{- if .Values.storage.s3.enabled -}}
    {{- printf "s3" -}}
  {{- else if .Values.storage.azureBlob.enabled -}}
    {{- printf "azureBlob" -}}
  {{- else if .Values.storage.gcs.enabled -}}
    {{- printf "gcs" -}}
  {{- else -}}
    {{- printf "none" -}}
  {{- end -}}
{{- end }}

{{/* Determine selected queue type */}}
{{- define "selectedQueueType" }}
  {{- if .Values.queue.kafka.enabled -}}
    {{- printf "kafka" -}}
  {{- else if .Values.queue.sqs.enabled -}}
    {{- printf "sqs" -}}
  {{- else if .Values.queue.rabbitmq.enabled -}}
    {{- printf "rabbitmq" -}}
  {{- else -}}
    {{- printf "none" -}}
  {{- end -}}
{{- end }}

{{/* Kafka Secrets Environment Variables */}}
{{- define "kafka-secrets-env" }}
# check if secretName is present
{{- if .Values.queue.kafka.secretName | trim | quote }}
# Define Kafka secret environment variables here
- name: KAFKA_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.kafka.secretName }}
      key: username
- name: KAFKA_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.kafka.secretName }}
      key: password
{{- end }}
{{- end }}

{{/* SQS Secrets Environment Variables */}}
{{- define "sqs-secrets-env" }}
{{- if .Values.queue.sqs.secretName | trim | quote }}
# Define SQS secret environment variables here
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.sqs.secretName }}
      key: accessKeyId
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.sqs.secretName }}
      key: secretAccessKey
{{- end }}
{{- end }}

{{/* RabbitMQ Secrets Environment Variables */}}
{{- define "rabbitmq-secrets-env" }}
{{- if .Values.queue.rabbitmq.secretName | trim | quote }}
# Define RabbitMQ secret environment variables here
- name: RABBITMQ_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.rabbitmq.secretName }}
      key: username
- name: RABBITMQ_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.queue.rabbitmq.secretName }}
      key: password
{{- end }}
{{- end }}
