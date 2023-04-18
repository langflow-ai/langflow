## Nodes used:

We used `OpenAI` as the LLM, but you can use any LLM that has an API. Make sure to get the API key from the LLM provider. For example, [OpenAI](https://platform.openai.com/account/api-keys){.internal-link target=_blank} requires you to create an account to get your API key.

The `ConversationSummaryMemory` is a simple memory that stores the conversation summary. The memory of this type creates a record of the conversation over time. You can use this to condense information over time from the conversation.

With `SeriesCharacterChain`, you can chat with the characters in the series you like most. You can just type the name of the character and the series, and the bot will start chatting with the character.

Character:
    
``` txt
Gandalf
```

Series:
    
``` txt
The Lord of the Rings
```

Play around with it and see how it works!

### ⛓️LangFlow example:

![!Description](img/series-character-chain.png#only-dark)
![!Description](img/series-character-chain.png#only-light)

[Get json file](data/Series-character-chain.json){: series-character-chain}