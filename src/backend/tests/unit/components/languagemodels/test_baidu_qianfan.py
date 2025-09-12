import os

import pytest
from langchain.schema import HumanMessage
from langchain_community.chat_models.baidu_qianfan_endpoint import QianfanChatEndpoint
from lfx.components.baidu.baidu_qianfan_chat import QianfanChatEndpointComponent
from qianfan.errors import APIError


@pytest.fixture
def qianfan_credentials():
    """Fixture to get Qianfan credentials from environment variables."""
    ak = os.getenv("QIANFAN_AK")
    sk = os.getenv("QIANFAN_SK")
    if not ak or not sk:
        pytest.skip("QIANFAN_AK and QIANFAN_SK environment variables are required.")
    return {"ak": ak, "sk": sk}


@pytest.mark.api_key_required
def test_none_endpoint(qianfan_credentials):
    """Test that None endpoint does not raise an exception."""
    component = QianfanChatEndpointComponent(
        model="ERNIE-Bot-turbo-AI",
        qianfan_ak=qianfan_credentials["ak"],
        qianfan_sk=qianfan_credentials["sk"],
        endpoint=None,
        temperature=0.7,
    )
    # should have no error
    model = component.build_model()
    messages = [HumanMessage(content="Say 'Hello' in Chinese")]
    response = model.invoke(messages)
    assert response is not None
    assert len(str(response)) > 0


@pytest.mark.api_key_required
def test_empty_str_endpoint(qianfan_credentials):
    """Test that empty string endpoint does not raise an exception."""
    component = QianfanChatEndpointComponent(
        model="ERNIE-Bot",
        qianfan_ak=qianfan_credentials["ak"],
        qianfan_sk=qianfan_credentials["sk"],
        endpoint="",
        temperature=0.7,
    )

    model = component.build_model()
    messages = [HumanMessage(content="Say 'Hello' in Chinese")]
    response = model.invoke(messages)
    assert response is not None
    assert len(str(response)) > 0


@pytest.mark.api_key_required
def test_invalid_endpoint(qianfan_credentials):
    """Test that invalid endpoint raises an exception."""
    component = QianfanChatEndpointComponent(
        model="ERNIE-Bot",
        qianfan_ak=qianfan_credentials["ak"],
        qianfan_sk=qianfan_credentials["sk"],
        endpoint="https://invalid.endpoint.example",
        temperature=0.7,
    )

    model = component.build_model()
    messages = [HumanMessage(content="Say 'Hello' in Chinese")]

    with pytest.raises(APIError):
        model.invoke(messages)


@pytest.mark.api_key_required
@pytest.mark.parametrize(
    "model_name",
    [
        "EB-turbo-AppBuilder",
        "Llama-2-70b-chat",
        "ERNIE-Bot-turbo-AI",
        "ERNIE-Lite-8K-0308",
        "ERNIE-Speed",
        "Qianfan-Chinese-Llama-2-13B",
        "ERNIE-3.5-8K",
        "BLOOMZ-7B",
        "Qianfan-Chinese-Llama-2-7B",
        "XuanYuan-70B-Chat-4bit",
        "AquilaChat-7B",
        "ERNIE-Bot-4",
        "Llama-2-13b-chat",
        "ChatGLM2-6B-32K",
        "ERNIE-Bot",
        "ERNIE-Speed-128k",
        "ERNIE-4.0-8K",
        "Qianfan-BLOOMZ-7B-compressed",
        "ERNIE Speed",
        "Llama-2-7b-chat",
        "Mixtral-8x7B-Instruct",
        "ERNIE 3.5",
        "ERNIE Speed-AppBuilder",
        "ERNIE-Speed-8K",
        "Yi-34B-Chat",
    ],
)
def test_qianfan_different_models(qianfan_credentials, model_name):
    """Test different Qianfan models with a simple prompt."""
    component = QianfanChatEndpointComponent(
        model=model_name,
        qianfan_ak=qianfan_credentials["ak"],
        qianfan_sk=qianfan_credentials["sk"],
        temperature=0.7,
        top_p=0.8,
        penalty_score=1.0,
    )

    # Build the model
    chat_model = component.build_model()
    assert isinstance(chat_model, QianfanChatEndpoint)

    # Test with a simple prompt
    messages = [HumanMessage(content="Say 'Hello' in Chinese")]

    try:
        response = chat_model(messages)
        assert response is not None
        assert len(str(response)) > 0
    except ValueError as e:
        pytest.fail(f"Model {model_name} failed with error: {e!s}")
