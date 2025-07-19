#!/usr/bin/env python3
"""
OpenRouter Example for Langflow

This example demonstrates how to use the OpenRouter component in Langflow
to access multiple AI models through a unified interface.
"""

import os
import sys
from typing import Optional

# Add the backend path to sys.path for direct execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'backend', 'base'))

from langflow.components.openrouter.openrouter import OpenRouterComponent


class OpenRouterExample:
    """Example class demonstrating OpenRouter usage in Langflow."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenRouter API key."""
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable "
                "or pass it directly to the constructor."
            )
    
    def list_available_providers(self) -> dict:
        """List all available providers and their models."""
        print("Fetching available providers and models from OpenRouter...")
        
        component = OpenRouterComponent()
        models = component.fetch_models()
        
        print(f"\nFound {len(models)} providers:")
        for provider, provider_models in models.items():
            print(f"\n📁 {provider} ({len(provider_models)} models)")
            for model in provider_models[:3]:  # Show first 3 models
                print(f"  • {model['id']}: {model['name']}")
                if model.get('context_length'):
                    print(f"    Context: {model['context_length']:,} tokens")
            if len(provider_models) > 3:
                print(f"  ... and {len(provider_models) - 3} more models")
        
        return models
    
    def create_openai_model(self) -> OpenRouterComponent:
        """Create an OpenRouter component configured for OpenAI GPT-4."""
        print("\n🤖 Creating OpenAI GPT-4 model via OpenRouter...")
        
        component = OpenRouterComponent()
        component.api_key = self.api_key
        component.provider = "OpenAI"
        component.model_name = "openai/gpt-4"
        component.temperature = 0.7
        component.max_tokens = 500
        component.site_url = "https://langflow.org"
        component.app_name = "Langflow OpenRouter Example"
        
        return component
    
    def create_anthropic_model(self) -> OpenRouterComponent:
        """Create an OpenRouter component configured for Anthropic Claude."""
        print("\n🧠 Creating Anthropic Claude model via OpenRouter...")
        
        component = OpenRouterComponent()
        component.api_key = self.api_key
        component.provider = "Anthropic"
        component.model_name = "anthropic/claude-3-sonnet"
        component.temperature = 0.5
        component.max_tokens = 500
        component.site_url = "https://langflow.org"
        component.app_name = "Langflow OpenRouter Example"
        
        return component
    
    def test_model_creation(self, component: OpenRouterComponent) -> bool:
        """Test that a model can be created successfully."""
        try:
            model = component.build_model()
            print(f"✅ Successfully created {component.model_name} model")
            print(f"   Model type: {type(model).__name__}")
            print(f"   API base: {model.openai_api_base}")
            print(f"   Temperature: {component.temperature}")
            return True
        except Exception as e:
            print(f"❌ Failed to create model: {e}")
            return False
    
    def demonstrate_model_switching(self):
        """Demonstrate switching between different models."""
        print("\n" + "="*60)
        print("🔄 DEMONSTRATING MODEL SWITCHING")
        print("="*60)
        
        models_to_test = [
            ("OpenAI GPT-4", self.create_openai_model),
            ("Anthropic Claude", self.create_anthropic_model),
        ]
        
        successful_models = []
        
        for model_name, create_func in models_to_test:
            print(f"\n--- Testing {model_name} ---")
            try:
                component = create_func()
                if self.test_model_creation(component):
                    successful_models.append((model_name, component))
            except Exception as e:
                print(f"❌ Failed to create {model_name}: {e}")
        
        print(f"\n✅ Successfully created {len(successful_models)} out of {len(models_to_test)} models")
        return successful_models
    
    def demonstrate_dynamic_config(self):
        """Demonstrate dynamic configuration updates."""
        print("\n" + "="*60)
        print("⚙️  DEMONSTRATING DYNAMIC CONFIGURATION")
        print("="*60)
        
        component = OpenRouterComponent()
        
        # Mock the fetch_models method for demonstration
        def mock_fetch_models():
            return {
                "OpenAI": [
                    {"id": "openai/gpt-4", "name": "GPT-4", "description": "Most capable GPT-4 model", "context_length": 8192},
                    {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "Fast and efficient", "context_length": 4096}
                ],
                "Anthropic": [
                    {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "description": "Most powerful Claude model", "context_length": 200000},
                    {"id": "anthropic/claude-3-sonnet", "name": "Claude 3 Sonnet", "description": "Balanced performance", "context_length": 200000}
                ]
            }
        
        # Replace the method temporarily
        original_fetch = component.fetch_models
        component.fetch_models = mock_fetch_models
        
        try:
            print("\n1. Initial configuration:")
            build_config = {
                "provider": {"options": [], "value": ""},
                "model_name": {"options": [], "value": "", "tooltips": {}}
            }
            
            print("   Empty provider and model options")
            
            print("\n2. Updating configuration for OpenAI provider:")
            updated_config = component.update_build_config(build_config, "OpenAI", "provider")
            
            print(f"   Available providers: {updated_config['provider']['options']}")
            print(f"   Available models: {updated_config['model_name']['options']}")
            print(f"   Selected model: {updated_config['model_name']['value']}")
            
            print("\n3. Model tooltips (showing context length and description):")
            for model_id, tooltip in updated_config['model_name']['tooltips'].items():
                print(f"   {model_id}: {tooltip[:100]}...")
            
        finally:
            # Restore original method
            component.fetch_models = original_fetch
    
    def run_complete_example(self):
        """Run the complete OpenRouter example."""
        print("🚀 LANGFLOW OPENROUTER EXAMPLE")
        print("="*60)
        print("This example demonstrates OpenRouter integration in Langflow")
        print("OpenRouter provides unified access to multiple AI model providers")
        
        try:
            # 1. List available providers
            self.list_available_providers()
            
            # 2. Demonstrate model switching
            self.demonstrate_model_switching()
            
            # 3. Demonstrate dynamic configuration
            self.demonstrate_dynamic_config()
            
            print("\n" + "="*60)
            print("✅ EXAMPLE COMPLETED SUCCESSFULLY!")
            print("="*60)
            print("\nKey takeaways:")
            print("• OpenRouter provides access to 50+ AI models from multiple providers")
            print("• Langflow's OpenRouter component handles dynamic model discovery")
            print("• Easy switching between providers and models")
            print("• Comprehensive configuration options")
            print("• Robust error handling and validation")
            
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function to run the OpenRouter example."""
    # Check for API key
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("⚠️  OpenRouter API Key not found!")
        print("\nTo run this example with actual API calls:")
        print("1. Get an API key from https://openrouter.ai/")
        print("2. Set the environment variable: export OPENROUTER_API_KEY='your-key-here'")
        print("3. Run this script again")
        print("\nRunning example with mock data for demonstration...")
        
        # Create a mock API key for demonstration
        api_key = "demo-key-for-testing"
    
    try:
        example = OpenRouterExample(api_key)
        example.run_complete_example()
    except Exception as e:
        print(f"Failed to run example: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()