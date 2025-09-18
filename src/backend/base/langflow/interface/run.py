from lfx.log.logger import logger


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


def update_memory_keys(langchain_object, possible_new_mem_key) -> None:
    """Update the memory keys in the LangChain object's memory attribute.

    Given a LangChain object and a possible new memory key, this function updates the input and output keys in the
    object's memory attribute to exclude the current memory key and the possible new key. It then sets the memory key
    to the possible new key.
    """
    input_key = next(
        key
        for key in langchain_object.input_keys
        if key not in {langchain_object.memory.memory_key, possible_new_mem_key}
    )

    output_key = next(
        key
        for key in langchain_object.output_keys
        if key not in {langchain_object.memory.memory_key, possible_new_mem_key}
    )

    for key, attr in [(input_key, "input_key"), (output_key, "output_key"), (possible_new_mem_key, "memory_key")]:
        try:
            setattr(langchain_object.memory, attr, key)
        except ValueError as exc:
            logger.debug(f"{langchain_object.memory} has no attribute {attr} ({exc})")
