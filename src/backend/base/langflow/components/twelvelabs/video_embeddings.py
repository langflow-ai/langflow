from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import SecretStrInput, IntInput
from twelvelabs import TwelveLabs
import time
from typing import List
import os

class TwelveLabsVideoEmbeddings(Embeddings):
    def __init__(self, api_key: str, video_clip_length: int):
        self.client = TwelveLabs(api_key=api_key)
        self.model_name = "Marengo-retrieval-2.7"
        self.video_clip_length = video_clip_length
        
    def _wait_for_task_completion(self, task_id: str):
        while True:
            result = self.client.embed.task.retrieve(id=task_id)
            if result.status == "ready":
                return result
            time.sleep(5)
            
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            video_path = text.page_content if hasattr(text, 'page_content') else str(text)
            result = self.embed_video(video_path)
            
            # First try to use video embedding, then fall back to clip embedding if available
            if result['video_embedding']:
                embeddings.append(result['video_embedding'])
            elif result['clip_embeddings'] and len(result['clip_embeddings']) > 0:
                embeddings.append(result['clip_embeddings'][0])
            else:
                # If neither is available, raise an error
                raise ValueError("No embeddings were generated for the video")
        
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        video_path = text.page_content if hasattr(text, 'page_content') else str(text)
        result = self.embed_video(video_path)
        
        # First try to use video embedding, then fall back to clip embedding if available
        if result['video_embedding']:
            return result['video_embedding']
        elif result['clip_embeddings'] and len(result['clip_embeddings']) > 0:
            return result['clip_embeddings']
        else:
            # If neither is available, raise an error
            raise ValueError("No embeddings were generated for the video")

    def embed_video(self, video_path: str) -> dict:

        clip_length = 6
        if self.video_clip_length is not None:
            clip_length = self.video_clip_length
        with open(video_path, 'rb') as video_file:
            task = self.client.embed.task.create(
                model_name=self.model_name,
                video_file=video_file,
                video_embedding_scopes=["clip", "video"],
                video_clip_length=clip_length
            )
        
        result = self._wait_for_task_completion(task.id)
        
        video_embedding = {'video_embedding': None, 'clip_embeddings': []}
        
        if hasattr(result.video_embedding, 'segments') and result.video_embedding.segments:
            for seg in result.video_embedding.segments:
                # Check for embeddings_float attribute (this is the correct attribute name)
                if hasattr(seg, 'embeddings_float'):
                    if seg.embedding_scope == "video":
                        # Convert to list of floats
                        video_embedding['video_embedding'] = [float(x) for x in seg.embeddings_float]
                    elif seg.embedding_scope == "clip":
                        # Convert to list of floats
                        video_embedding['clip_embeddings'].append([float(x) for x in seg.embeddings_float])
        
        return video_embedding

class TwelveLabsVideoEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "TwelveLabs Video Embeddings"
    name = "TwelveLabsVideoEmbeddings"
    inputs = [
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        IntInput(
            name="video_clip_length",
            display_name="Clip Length",
            info="Length of each video clip in seconds (default: 6s).",
            required=False
        )
    ]

    def build_embeddings(self) -> Embeddings:
        return TwelveLabsVideoEmbeddings(api_key=self.api_key,video_clip_length=self.video_clip_length)
