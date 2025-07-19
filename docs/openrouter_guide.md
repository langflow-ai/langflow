# OpenRouter Integration in Langflow

OpenRouter provides unified access to multiple AI models from different providers through a single API. Langflow includes comprehensive support for OpenRouter, allowing you to easily switch between different AI models and providers.

## Features

- **Unified API Access**: Access models from OpenAI, Anthropic, Google, Meta, and many other providers through a single interface
- **Dynamic Model Discovery**: Automatically fetch and display available models organized by provider
- **Real-time Model Selection**: Provider and model dropdowns update dynamically based on current availability
- **Comprehensive Configuration**: Support for temperature, max tokens, and other model parameters
- **Error Handling**: Robust error handling with informative error messages
- **Usage Tracking**: Optional site URL and app name for OpenRouter usage analytics

## Getting Started

### 1. Obtain an OpenRouter API Key

1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up for an account
3. Navigate to the API Keys section
4. Generate a new API key

### 2. Using OpenRouter in Langflow

1. **Add OpenRouter Component**: In the Langflow interface, add an "OpenRouter" component from the Models section
2. **Configure API Key**: Enter your OpenRouter API key in the "OpenRouter API Key" field
3. **Select Provider**: Choose from available providers (e.g., OpenAI, Anthropic, Google, etc.)
4. **Select Model**: Choose a specific model from the selected provider
5. **Configure Parameters**: Adjust temperature, max tokens, and other settings as needed

### 3. Component Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| **OpenRouter API Key** | Your OpenRouter API key | Yes | - |
| **Provider** | AI model provider (e.g., OpenAI, Anthropic) | Yes | - |
| **Model** | Specific model to use | Yes | - |
| **Temperature** | Controls randomness (0.0 to 2.0) | No | 0.7 |
| **Max Tokens** | Maximum tokens to generate | No | - |
| **Site URL** | Your site URL for OpenRouter rankings | No | - |
| **App Name** | Your app name for OpenRouter rankings | No | - |

## Available Providers and Models

OpenRouter supports models from many providers including:

- **OpenAI**: GPT-4, GPT-3.5 Turbo, and other OpenAI models
- **Anthropic**: Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku
- **Google**: Gemini Pro, Gemini Pro Vision
- **Meta**: Llama 2, Llama 3 variants
- **Mistral**: Mistral 7B, Mixtral 8x7B
- **And many more**: Including models from Cohere, AI21, Together AI, and other providers

The exact list of available models is fetched dynamically from OpenRouter's API, ensuring you always have access to the latest models.

## Example Usage

### Basic Chat Completion

```python
from langflow.components.openrouter.openrouter import OpenRouterComponent

# Create and configure the component
openrouter = OpenRouterComponent()
openrouter.api_key = "your-openrouter-api-key"
openrouter.provider = "OpenAI"
openrouter.model_name = "openai/gpt-4"
openrouter.temperature = 0.7

# Build the model
model = openrouter.build_model()

# Use the model for chat completion
response = model.invoke("Hello, how are you?")
print(response.content)
```

### Advanced Configuration

```python
from langflow.components.openrouter.openrouter import OpenRouterComponent

# Create component with advanced settings
openrouter = OpenRouterComponent()
openrouter.api_key = "your-openrouter-api-key"
openrouter.provider = "Anthropic"
openrouter.model_name = "anthropic/claude-3-opus"
openrouter.temperature = 0.3
openrouter.max_tokens = 1000
openrouter.site_url = "https://myapp.com"
openrouter.app_name = "My AI Application"

# Build and use the model
model = openrouter.build_model()
```

## Best Practices

### 1. API Key Security
- Store your OpenRouter API key securely
- Use environment variables or secure configuration management
- Never commit API keys to version control

### 2. Model Selection
- Different models have different strengths and pricing
- Test multiple models to find the best fit for your use case
- Consider context length requirements for your application

### 3. Parameter Tuning
- **Temperature**: Lower values (0.1-0.3) for factual tasks, higher values (0.7-1.0) for creative tasks
- **Max Tokens**: Set appropriate limits based on your use case and budget
- **Provider Selection**: Different providers may have different latencies and capabilities

### 4. Error Handling
- Implement proper error handling for API failures
- Consider fallback models or providers
- Monitor usage and rate limits

## Troubleshooting

### Common Issues

1. **"API key is required" Error**
   - Ensure you've entered a valid OpenRouter API key
   - Check that the API key has sufficient credits

2. **"Please select a model" Error**
   - Make sure you've selected both a provider and a model
   - Try refreshing the model list if it appears empty

3. **Network/Connection Errors**
   - Check your internet connection
   - Verify OpenRouter service status
   - Consider implementing retry logic

4. **Model Not Available**
   - Some models may have limited availability
   - Try selecting a different model from the same provider
   - Check OpenRouter documentation for model status

### Getting Help

- Check the [OpenRouter Documentation](https://openrouter.ai/docs)
- Review the [Langflow Documentation](https://docs.langflow.org/)
- Join the Langflow community for support

## Pricing and Usage

OpenRouter uses a pay-per-use model with different pricing for different models and providers. Check the [OpenRouter Pricing](https://openrouter.ai/models) page for current rates.

### Usage Tracking

If you provide a `site_url` and `app_name`, OpenRouter will track usage for your application, which can help with:
- Usage analytics
- Ranking in OpenRouter's model directory
- Better understanding of your application's AI usage patterns

## Advanced Features

### Dynamic Model Loading

The OpenRouter component automatically fetches the latest available models from OpenRouter's API, ensuring you always have access to new models as they become available.

### Provider-Based Organization

Models are automatically organized by provider, making it easy to:
- Compare models from the same provider
- Switch between providers while maintaining similar model capabilities
- Understand the source of each model

### Context Length Information

Each model displays its context length, helping you choose the right model for your specific use case requirements.

## Integration with Langflow Workflows

The OpenRouter component integrates seamlessly with other Langflow components:

- **Prompt Templates**: Use with prompt components for structured inputs
- **Memory Components**: Combine with memory for conversational AI
- **Output Parsers**: Parse and structure model responses
- **Chains**: Build complex workflows with multiple AI interactions

This makes OpenRouter a powerful choice for building sophisticated AI applications in Langflow.