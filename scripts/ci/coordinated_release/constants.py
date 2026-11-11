"""Contract v1 identities and dependency graph."""

REPOSITORIES = {
    "oss": "https://github.com/langflow-ai/langflow",
    "ibm": "https://github.ibm.com/WatsonOrchestrate/IBM-Langflow",
    "control_plane": "https://github.ibm.com/WatsonOrchestrate/langflow-control-plane",
    "operator": "https://github.ibm.com/WatsonOrchestrate/langflow-operator",
}
VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
SHA = r"[0-9a-f]{40}"
DIGEST = r"sha256:[0-9a-f]{64}"
PLATFORM = r"linux/(?:amd64|arm64|s390x|ppc64le)(?:/v[0-9]+)?"
DEPENDENCIES = {
    "oss": (),
    "ibm": ("oss",),
    "control_plane": ("oss",),
    "operator": ("ibm", "control_plane"),
}
