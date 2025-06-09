from langflow.schema.data import Data


def chroma_collection_to_data(collection_dict: dict):
    """Converts a collection of chroma vectors into a list of data.

    Args:
        collection_dict (dict): A dictionary containing the collection of chroma vectors.

    Returns:
        list: A list of data, where each record represents a document in the collection.
    """
    data = []
    for i, doc in enumerate(collection_dict["documents"]):
        data_dict = {
            "id": collection_dict["ids"][i],
            "text": doc,
        }
        if ("metadatas" in collection_dict) and collection_dict["metadatas"][i]:
            data_dict.update(collection_dict["metadatas"][i].items())
        data.append(Data(**data_dict))
    return data
