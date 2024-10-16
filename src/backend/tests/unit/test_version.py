from langflow.utils.version import _compute_non_prerelease_version, get_version_info


def test_version():
    info = get_version_info()
    assert info["version"] is not None
    assert info["main_version"] is not None
    assert info["package"] is not None


def test_compute_main():
    assert _compute_non_prerelease_version("1.0.10.post0") == "1.0.10"
    assert _compute_non_prerelease_version("1.0.10.a1") == "1.0.10"
    assert _compute_non_prerelease_version("1.0.10.b112") == "1.0.10"
    assert _compute_non_prerelease_version("1.0.10.rc0") == "1.0.10"
    assert _compute_non_prerelease_version("1.0.10.dev9") == "1.0.10"
    assert _compute_non_prerelease_version("1.0.10") == "1.0.10"
