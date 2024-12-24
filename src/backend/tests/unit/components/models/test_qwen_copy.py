
from openai import OpenAI

from langchain_community.llms import Tongyi

if __name__ == "__main__":
    client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key="sk-623e6c2faa9f4d84afce1ee5388f8247", 
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    model = Tongyi(
        model="qwen-turbo",
        api_key="sk-623e6c2faa9f4d84afce1ee5388f8247",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    response = Tongyi().invoke("What NFL team won the Super Bowl in the year Justin Bieber was born?")


    print(response)
    # completion = client.chat.completions.create(
    #     model="qwen-long", # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    #     messages=[
    #         {'role': 'system', 'content': 'You are a helpful assistant.'},
    #         {'role': 'user', 'content': '你是谁？'}],
    #     )
        
    # print(completion.model_dump_json())