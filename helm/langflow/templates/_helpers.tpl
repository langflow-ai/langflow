{{- define "langflow.fullname" -}}
langflow-{{ required "empno is required" .Values.empno }}
{{- end }}

{{- define "langflow.labels" -}}
app.kubernetes.io/name: langflow
app.kubernetes.io/instance: {{ include "langflow.fullname" . }}
empno: {{ .Values.empno | quote }}
{{- end }}

{{- define "langflow.selectorLabels" -}}
app.kubernetes.io/name: langflow
app.kubernetes.io/instance: {{ include "langflow.fullname" . }}
{{- end }}

{{- define "langflow.secretName" -}}
{{- if .Values.keycloak.existingSecret -}}
{{ .Values.keycloak.existingSecret }}
{{- else -}}
{{ include "langflow.fullname" . }}-secret
{{- end }}
{{- end }}

{{- define "langflow.host" -}}
langflow-{{ .Values.empno }}.{{ .Values.ingress.domain }}
{{- end }}

{{/* SSL CA cert volume source */}}
{{- define "langflow.sslVolume" -}}
{{- if .Values.ssl.existingConfigMap -}}
configMap:
  name: {{ .Values.ssl.existingConfigMap }}
{{- else if .Values.ssl.existingSecret -}}
secret:
  secretName: {{ .Values.ssl.existingSecret }}
{{- else -}}
configMap:
  name: {{ include "langflow.fullname" . }}-ca-cert
{{- end }}
{{- end }}
