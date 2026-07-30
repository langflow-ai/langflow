import base64

import pytest


@pytest.fixture
def elastic_module():
    return pytest.importorskip("lfx_bundles.elastic.elasticsearch")


def test_cloud_id_elasticsearch_url_handles_unpadded_cloud_id(elastic_module):
    encoded = base64.b64encode(b"example.elastic-cloud.com:9243$es-uuid$kibana-uuid").decode().rstrip("=")

    url = elastic_module._cloud_id_elasticsearch_url(f"deployment:{encoded}")

    assert url == "https://es-uuid.example.elastic-cloud.com:9243"


def test_cloud_id_elasticsearch_url_rejects_malformed_cloud_id(elastic_module):
    with pytest.raises(ValueError, match="Cloud ID is not properly formatted"):
        elastic_module._cloud_id_elasticsearch_url("deployment:not-base64")
