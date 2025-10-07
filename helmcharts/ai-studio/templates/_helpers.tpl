{{/*
Expand the name of the chart.
*/}}
{{- define "ai-studio.name" -}}
{{- default .Chart.Name .Values.global.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ai-studio.fullname" -}}
{{- if .Values.global.fullnameOverride }}
{{- .Values.global.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.global.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Frontend full name
*/}}
{{- define "ai-studio.frontend.fullname" -}}
{{- printf "%s-frontend" (include "ai-studio.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Backend full name
*/}}
{{- define "ai-studio.backend.fullname" -}}
{{- printf "%s-backend" (include "ai-studio.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Database full name
*/}}
{{- define "ai-studio.database.fullname" -}}
{{- printf "%s-database" (include "ai-studio.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Cache full name
*/}}
{{- define "ai-studio.cache.fullname" -}}
{{- printf "%s-cache" (include "ai-studio.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ai-studio.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ai-studio.labels" -}}
helm.sh/chart: {{ include "ai-studio.chart" . }}
{{ include "ai-studio.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.global.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ai-studio.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-studio.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "ai-studio.frontend.labels" -}}
{{ include "ai-studio.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "ai-studio.frontend.selectorLabels" -}}
{{ include "ai-studio.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Backend labels
*/}}
{{- define "ai-studio.backend.labels" -}}
{{ include "ai-studio.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "ai-studio.backend.selectorLabels" -}}
{{ include "ai-studio.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Database labels
*/}}
{{- define "ai-studio.database.labels" -}}
{{ include "ai-studio.labels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Database selector labels
*/}}
{{- define "ai-studio.database.selectorLabels" -}}
{{ include "ai-studio.selectorLabels" . }}
app.kubernetes.io/component: database
{{- end }}

{{/*
Cache labels
*/}}
{{- define "ai-studio.cache.labels" -}}
{{ include "ai-studio.labels" . }}
app.kubernetes.io/component: cache
{{- end }}

{{/*
Cache selector labels
*/}}
{{- define "ai-studio.cache.selectorLabels" -}}
{{ include "ai-studio.selectorLabels" . }}
app.kubernetes.io/component: cache
{{- end }}

{{/*
Create the name of the service account to use for frontend
*/}}
{{- define "ai-studio.frontend.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}
{{- default (include "ai-studio.frontend.fullname" .) .Values.global.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.global.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use for backend
*/}}
{{- define "ai-studio.backend.serviceAccountName" -}}
{{- if .Values.backend.serviceAccount.create }}
{{- default (include "ai-studio.backend.fullname" .) .Values.backend.serviceAccount.name }}
{{- else if .Values.global.serviceAccount.create }}
{{- default (include "ai-studio.backend.fullname" .) .Values.global.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.backend.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "ai-studio.frontend.image" -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.frontend.image.repository (.Values.frontend.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "ai-studio.backend.image" -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.backend.image.repository (.Values.backend.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{/*
Database image
*/}}
{{- define "ai-studio.database.image" -}}
{{- printf "%s:%s" .Values.database.postgresql.image.repository .Values.database.postgresql.image.tag }}
{{- end }}

{{/*
Cache image
*/}}
{{- define "ai-studio.cache.image" -}}
{{- printf "%s:%s" .Values.cache.redis.image.repository .Values.cache.redis.image.tag }}
{{- end }}

{{/*
Database connection string
*/}}
{{- define "ai-studio.database.connectionString" -}}
{{- if .Values.database.external }}
{{- printf "postgresql://%s@%s:%d/%s" .Values.database.username .Values.database.host (.Values.database.port | int) .Values.database.database }}
{{- else }}
{{- printf "postgresql://%s@%s:%d/%s" .Values.database.username (include "ai-studio.database.fullname" .) (5432 | int) .Values.database.database }}
{{- end }}
{{- end }}

{{/*
Redis connection string
*/}}
{{- define "ai-studio.cache.connectionString" -}}
{{- if .Values.cache.external }}
{{- printf "redis://%s:%d" .Values.cache.host (.Values.cache.port | int) }}
{{- else }}
{{- printf "redis://%s:%d" (include "ai-studio.cache.fullname" .) (6379 | int) }}
{{- end }}
{{- end }}