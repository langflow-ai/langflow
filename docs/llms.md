# OpenAI

## Inputs available:

- **Model name** - typically refers to the name given to a specific pre-trained model or architecture used to perform a particular task. These models are usually developed by training neural networks on large datasets to learn patterns in the data, and then fine-tuning them for specific applications.
    - **text-davinci-003** - is a transformer-based neural network. Most capable GPT-3 model. Can do any task the other models can do, often with higher quality.
    - **text-davinvi-002** - is a transformer-based neural network. The 002 suffix distinguishes it from other versions of the "davinci" model.
    - **text-curie-001** - Very capable, faster and lower cost than Davinci.
    - **text-babbage-001** - Capable of straightforward tasks, very fast, and lower cost.
    - **text-ada-001** - Capable of very simple tasks, usually the fastest model in the GPT-3 series, and lowest cost.

- **Temperature** - refer to a parameter used in a softmax function, which is a mathematical function that is commonly used in artificial neural networks to convert a vector of real numbers into a probability distribution. The temperature parameter controls the "softness" of the probability distribution produced by the softmax function. A high temperature value produces a softer probability distribution, which means that the model will be more uncertain and assign more similar probabilities to multiple classes. A low temperature value produces a sharper probability distribution, which means that the model will be more confident and assign higher probabilities to the most likely classes.

- **Max tokens** - refers to the maximum number of tokens (i.e., words and symbols) that can be input to the model at once for text generation or other language tasks. The exact value of the max tokens parameter may vary depending on the specific LLM variant being used and the resources available for processing the input text.

- **Model kwargs** - can be used to fine-tune the behavior of a machine learning model and optimize its performance for a specific task. By adjusting the values of the kwargs, it is possible to modify the way the model is trained, how it handles inputs, or how it generates outputs. However, it is important to be careful when modifying model kwargs, as the wrong configuration can lead to poor performance or even failure of the model.