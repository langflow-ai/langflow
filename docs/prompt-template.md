A prompt template refers to a reproducible way to generate a prompt. It contains a text string (“the template”), that can take in a set of parameters from the end user and generate a prompt.

The prompt template may contain:

* instructions to the language model,

* a set of few shot examples to help the language model generate a better response,

* a question to the language model.

Template:
    
``` txt
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy and easy to remember.

What is a good name for a company that makes {product}?
```

![!Description](img/prompt-template.png#only-dark)
![!Description](img/prompt-template.png#only-light)

