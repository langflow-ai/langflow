from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import SecretStrInput
from twelvelabs import TwelveLabs
import time
from typing import List
import os
import datetime

class TwelveLabsVideoEmbeddings(Embeddings):
    def __init__(self, api_key: str):
        self.client = TwelveLabs(api_key=api_key)
        self.model_name = "Marengo-retrieval-2.7"
        self.log_file = os.path.join(os.path.expanduser("~"), "twelvelabs_debug.log")
        self._file_log(f"Initialized TwelveLabsVideoEmbeddings with model {self.model_name}")
        
    def _file_log(self, message):
        """Log to a file in the user's home directory"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
        
    def _wait_for_task_completion(self, task_id: str):
        self._file_log(f"Waiting for task {task_id} to complete")
        while True:
            result = self.client.embed.task.retrieve(id=task_id)
            self._file_log(f"Task status: {result.status}")
            if result.status == "ready":
                self._file_log(f"Task {task_id} completed")
                return result
            time.sleep(5)
            
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._file_log(f"Embedding {len(texts)} documents")
        embeddings = []
        for i, text in enumerate(texts):
            self._file_log(f"Processing document {i+1}/{len(texts)}")
            video_path = text.page_content if hasattr(text, 'page_content') else str(text)
            self._file_log(f"Video path: {video_path}")
            result = self.embed_video(video_path)
            
            # First try to use video embedding, then fall back to clip embedding if available
            if result['video_embedding']:
                self._file_log(f"Using video-level embedding for document {i+1}")
                embeddings.append(result['video_embedding'])
            elif result['clip_embeddings'] and len(result['clip_embeddings']) > 0:
                self._file_log(f"Using clip-level embedding for document {i+1}")
                embeddings.append(result['clip_embeddings'][0])
            else:
                self._file_log(f"No embeddings found for document {i+1}")
                # If neither is available, raise an error
                raise ValueError("No embeddings were generated for the video")
        
        self._file_log(f"Successfully embedded {len(embeddings)} documents")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        self._file_log("Embedding query")
        video_path = text.page_content if hasattr(text, 'page_content') else str(text)
        self._file_log(f"Video path: {video_path}")
        result = self.embed_video(video_path)
        
        # First try to use video embedding, then fall back to clip embedding if available
        if result['video_embedding']:
            self._file_log("Using video-level embedding for query")
            return result['video_embedding']
        elif result['clip_embeddings'] and len(result['clip_embeddings']) > 0:
            self._file_log("Using clip-level embedding for query")
            return result['clip_embeddings'][0]
        else:
            self._file_log("No embeddings found for query")
            # If neither is available, raise an error
            raise ValueError("No embeddings were generated for the video")

    def embed_video(self, video_path: str) -> dict:
        self._file_log(f"Embedding video: {video_path}")
        
        try:
            with open(video_path, 'rb') as video_file:
                self._file_log("Creating embedding task")
                task = self.client.embed.task.create(
                    model_name=self.model_name,
                    video_file=video_file,
                    video_embedding_scopes=["clip", "video"]
                )
                self._file_log(f"Task created with ID: {task.id}")
            
            result = self._wait_for_task_completion(task.id)
            
            video_embedding = {'video_embedding': None, 'clip_embeddings': []}
            
            # Log the structure of the result
            self._file_log(f"Result attributes: {dir(result)}")
            self._file_log(f"Video embedding attributes: {dir(result.video_embedding)}")
            
            if hasattr(result.video_embedding, 'segments') and result.video_embedding.segments:
                self._file_log(f"Found {len(result.video_embedding.segments)} segments")
                
                for i, seg in enumerate(result.video_embedding.segments):
                    self._file_log(f"Segment {i} scope: {seg.embedding_scope}")
                    self._file_log(f"Segment {i} attributes: {dir(seg)}")
                    
                    # Check for embeddings_float attribute (this is the correct attribute name)
                    if hasattr(seg, 'embeddings_float'):
                        if seg.embedding_scope == "video":
                            self._file_log("Found video embedding in 'embeddings_float' attribute")
                            # Convert to list of floats
                            video_embedding['video_embedding'] = [float(x) for x in seg.embeddings_float]
                        elif seg.embedding_scope == "clip":
                            self._file_log("Found clip embedding in 'embeddings_float' attribute")
                            # Convert to list of floats
                            video_embedding['clip_embeddings'].append([float(x) for x in seg.embeddings_float])
                    else:
                        self._file_log(f"No embeddings_float attribute found in segment {i}")
            else:
                self._file_log("No segments found in video embedding")
            
            self._file_log(f"Video embedding present: {video_embedding['video_embedding'] is not None}")
            self._file_log(f"Clip embeddings count: {len(video_embedding['clip_embeddings'])}")
            
            return video_embedding
            
        except Exception as e:
            self._file_log(f"Error in embed_video: {str(e)}")
            # Re-raise the exception
            raise

class TwelveLabsVideoEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "TwelveLabs Video Embeddings"
    name = "TwelveLabsVideoEmbeddings"
    inputs = [SecretStrInput(name="api_key", display_name="API Key", required=True)]

    def build_embeddings(self) -> Embeddings:
        return TwelveLabsVideoEmbeddings(api_key=self.api_key)
