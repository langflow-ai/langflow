from langchain_core.vectorstores import VectorStore

from langflow.io import Output


def vector_store_connection(cls):
    """A decorator that adds vector store connection functionality to a class.

    This decorator performs the following actions:
    1. Adds a `decorated` attribute to the class and sets it to True.
    2. Checks if the class has an `outputs` attribute:
        - If it does, it makes a copy of the `outputs` attribute to avoid modifying the base class attribute.
        - It then checks if "vectorstoreconnection" is not already in the output names.
        - If not, it adds a new `Output` entry for "Vector Store Connection" to the `outputs` attribute.
    3. Adds an `as_vector_store` method to the class, which returns the result of the `build_vector_store` method.

    Args:
        cls (type): The class to be decorated.

    Returns:
        type: The decorated class with added vector store connection functionality.
    """
    cls.decorated = True  # Add an attribute to the class

    if hasattr(cls, "outputs"):
        cls.outputs = cls.outputs.copy()  # Make a copy to avoid modifying the base class attribute
        output_names = [output.name for output in cls.outputs]

        if "vectorstoreconnection" not in output_names:
            cls.outputs.extend(
                [
                    Output(
                        display_name="Vector Store Connection",
                        hidden=True,
                        name="vectorstoreconnection",
                        method="as_vector_store",
                    )
                ]
            )

    def as_vector_store(self) -> VectorStore:
        """Converts the current instance to a VectorStore object.

        Returns:
            VectorStore: The resulting VectorStore object.
        """
        return self.build_vector_store()

    cls.as_vector_store = as_vector_store  # Ensures that the method is added to the class

    return cls
