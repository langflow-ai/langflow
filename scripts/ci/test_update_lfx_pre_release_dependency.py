from scripts.ci.update_lfx_pre_release_dependency import update_lfx_requirements


def test_preserves_lfx_extras_and_markers():
    content = """
dependencies = ["lfx~=1.11.0"]
cassandra = ["lfx[cassandra]~=1.11.0"]
toolguard = ["lfx[toolguard]>=1.11.0; sys_platform != 'win32'"]
provider = ["lfx-openai>=0.1.0,<1.0.0"]
"""

    result = update_lfx_requirements(content, "1.11.0rc2")

    assert '"lfx>=1.11.0rc2,<1.12.dev0"' in result
    assert '"lfx[cassandra]>=1.11.0rc2,<1.12.dev0"' in result
    assert "\"lfx[toolguard]>=1.11.0rc2,<1.12.dev0; sys_platform != 'win32'\"" in result
    assert '"lfx-openai>=0.1.0,<1.0.0"' in result


def test_rewrites_an_existing_release_range_idempotently():
    content = 'dependencies = ["lfx[toolguard]>=1.11.0rc1,<1.12.dev0"]\n'

    result = update_lfx_requirements(content, "1.11.0rc2")

    assert result == 'dependencies = ["lfx[toolguard]>=1.11.0rc2,<1.12.dev0"]\n'
