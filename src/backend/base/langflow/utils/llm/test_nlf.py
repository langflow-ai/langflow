from pydantic import BaseModel
from nlf import backend
from langchain_openai import ChatOpenAI
import json
from typing import List

# Define a simple Pydantic model for the output
class Entity(BaseModel):
    name: str
    type: str
    context: str

class EntityExtractionResult(BaseModel):
    entities: List[Entity]

# Create a function that will be powered by the LLM
@backend("gpt-3.5-turbo", debug=True)
def extract_entities(text: str) -> EntityExtractionResult:
    """Extract all entities from the following text: {{ text }}"""
    pass

# Test the function
if __name__ == "__main__":
    sample_text = "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum and first released in 1991. Python supports multiple programming paradigms, including procedural, object-oriented, and functional programming."
    
    try:
        result = extract_entities(sample_text)
        print("\nRaw result:")
        print(result)
        
        if isinstance(result, dict) and "_debug" in result:
            print("\nDebug info:")
            print(json.dumps(result["_debug"], indent=2))
            
        if isinstance(result, EntityExtractionResult):
            print("\nExtracted Entities:")
            for entity in result.entities:
                print(f"\n- {entity.name} ({entity.type})")
                print(f"  Context: {entity.context}")
    except Exception as e:
        print(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc() 