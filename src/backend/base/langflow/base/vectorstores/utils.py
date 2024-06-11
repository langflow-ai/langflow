from langflow.schema import Record


def chroma_collection_to_records(collection_dict: dict):
    """
    Converts a collection of chroma vectors into a list of records.

    Args:
        collection_dict (dict): A dictionary containing the collection of chroma vectors.

    Returns:
        list: A list of records, where each record represents a document in the collection.
    """
    records = []
    for i, doc in enumerate(collection_dict["documents"]):
        record_dict = {
            "id": collection_dict["ids"][i],
            "text": doc,
        }
        if "metadatas" in collection_dict:
            for key, value in collection_dict["metadatas"][i].items():
                record_dict[key] = value
        records.append(Record(**record_dict))
    return records
