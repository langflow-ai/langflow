## OpenAI

##### Options available:

- **Model name** - typically refers to the name given to a specific pre-trained model or architecture used to perform a particular task. These models are usually developed by training neural networks on large datasets to learn patterns in the data, and then fine-tuning them for specific applications.
    - **text-davinci-003** - is a transformer-based neural network. Most capable GPT-3 model. Can do any task the other models can do, often with higher quality.
    - **text-davinvi-002** - is a transformer-based neural network. The 002 suffix distinguishes it from other versions of the "davinci" model.
    - **text-curie-001** - very capable, faster, and lower cost than Davinci.
    - **text-babbage-001** - capable of straightforward tasks, very fast, and lower cost.
    - **text-ada-001** - capable of very simple tasks, usually the fastest model in the GPT-3 series, and lowest cost.

- **Temperature** - the temperature parameter controls the "softness" of the probability distribution produced by the softmax function. A high-temperature value produces a softer probability distribution, which means that the model will be more uncertain and assign more similar probabilities to multiple classes. A low-temperature value produces a sharper probability distribution, which means that the model will be more confident and assign higher probabilities to the most likely classes.

- **Max tokens** - refers to the maximum number of tokens (i.e., words and symbols) that can be input to the model at once for text generation or other language tasks. The exact value of the max tokens parameter may vary depending on the specific LLM variant being used and the resources available for processing the input text.

- **Model kwargs** - by adjusting the values of the kwargs, it is possible to modify the way the model is trained, how it handles inputs, or how it generates outputs. However, it is important to be careful when modifying model kwargs, as the wrong configuration can lead to poor performance or even failure of the model.

## ChatOpenAI
Wrapper around OpenAI Chat large language model.

##### Options available:

- **Model name**:
    - **gpt-3.5-turbo** - the GPT-3.5-Turbo model has the capability unlocks some interesting features, such as the ability to store prior responses or query with a predefined set of instructions with context.
    - **gpt-4** - the latest milestone in OpenAI’s effort in scaling up deep learning.
    - **gpt-4-32k** - it can process as many as 32,768 tokens, which is about 50 pages of text. 

- **Max tokens** - refers to the maximum number of tokens (i.e., words and symbols) that can be input to the model at once for text generation or other language tasks. The exact value of the max tokens parameter may vary depending on the specific LLM variant being used and the resources available for processing the input text.

- **Model kwargs** - by adjusting the values of the kwargs, it is possible to modify the way the model is trained, how it handles inputs, or how it generates outputs. However, it is important to be careful when modifying model kwargs, as the wrong configuration can lead to poor performance or even failure of the model.

- **Max tokens** - refers to the maximum number of tokens (i.e., words and symbols) that can be input to the model at once for text generation or other language tasks.

## Llama Cpp
A wrapper around the [llama.cpp](https://github.com/ggerganov/llama.cpp){.internal-link target=_blank} model.

Make sure you are following all instructions to [install all necessary model files](https://github.com/ggerganov/llama.cpp){.internal-link target=_blank} model.

There is no need for *API_TOKENS*!

##### Options available:

- **Model path**: insert your model path after you have downloaded the model files.

- **Max tokens** - refers to the maximum number of tokens (i.e., words and symbols) that can be input to the model at once for text generation or other language tasks. The exact value of the max tokens parameter may vary depending on the specific LLM variant being used and the resources available for processing the input text.

- **Temperature** - the temperature parameter controls the "softness" of the probability distribution produced by the softmax function. A high-temperature value produces a softer probability distribution, which means that the model will be more uncertain and assign more similar probabilities to multiple classes. A low-temperature value produces a sharper probability distribution, which means that the model will be more confident and assign higher probabilities to the most likely classes.