def get_memory_key(langchain_object):
    """Get the memory key from the LangChain object's memory attribute.

    Given a LangChain object, this function retrieves the current memory key from the object's memory attribute.
    It then checks if the key exists in a dictionary of known memory keys and returns the corresponding key,
    or None if the current key is not recognized.
    """
    mem_key_dict = {
        "chat_history": "history",
        "history": "chat_history",
    }
    # Check if memory_key attribute exists
    if hasattr(langchain_object.memory, "memory_key"):
        memory_key = langchain_object.memory.memory_key
        return mem_key_dict.get(memory_key)
    return None  # or some other default value or action
