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
