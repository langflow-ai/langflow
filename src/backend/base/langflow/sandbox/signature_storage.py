"""
Component signature storage using local JSON file.
This file maintains a historical record of component signatures to prevent
breaking existing flows when components are updated.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger

from .signature import ComponentSignature


class ComponentSignatureStorage:
    """Manages persistent storage of component signatures in a local JSON file."""
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            # Default to sandbox folder
            sandbox_dir = Path(__file__).parent
            storage_path = sandbox_dir / "component_signatures.json"
        
        self.storage_path = Path(storage_path)
        self.signatures_data: Dict[str, List[Dict]] = {}
        self._load_signatures()
    
    def _load_signatures(self) -> None:
        """Load signatures from JSON file."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.signatures_data = json.load(f)
                logger.info(f"Loaded {len(self.signatures_data)} component signature histories from {self.storage_path}")
            else:
                logger.info(f"No existing signature file found at {self.storage_path}, starting fresh")
                self.signatures_data = {}
        except Exception as e:
            logger.error(f"Failed to load signatures from {self.storage_path}: {e}")
            self.signatures_data = {}
    
    def _save_signatures(self) -> None:
        """Save signatures to JSON file."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.signatures_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved signatures to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save signatures to {self.storage_path}: {e}")
    
    def upsert_signature(self, component_path: str, signature: ComponentSignature) -> None:
        """
        Add or update a signature for a component.
        If the signature already exists, it won't be duplicated.
        """
        if component_path not in self.signatures_data:
            self.signatures_data[component_path] = []
        
        signature_dict = signature.to_dict()
        
        # Check if this exact signature already exists
        for existing in self.signatures_data[component_path]:
            if existing.get('signature') == signature_dict['signature']:
                logger.debug(f"Signature for {component_path} already exists, skipping")
                return
        
        # Add new signature
        self.signatures_data[component_path].append(signature_dict)
        logger.debug(f"Added new signature for {component_path}")
        
        # Save immediately to persist changes
        self._save_signatures()
    
    def get_signatures(self, component_path: str) -> List[ComponentSignature]:
        """Get all signatures for a component, sorted by timestamp (newest first)."""
        if component_path not in self.signatures_data:
            return []
        
        signatures = []
        for sig_data in self.signatures_data[component_path]:
            try:
                signature = ComponentSignature.from_dict(sig_data)
                signatures.append(signature)
            except Exception as e:
                logger.warning(f"Failed to parse signature for {component_path}: {e}")
        
        # Sort by timestamp, newest first
        signatures.sort(key=lambda s: s.timestamp, reverse=True)
        return signatures
    
    def get_latest_signature(self, component_path: str) -> Optional[ComponentSignature]:
        """Get the most recent signature for a component."""
        signatures = self.get_signatures(component_path)
        return signatures[0] if signatures else None
    
    def get_all_component_paths(self) -> List[str]:
        """Get all component paths that have signatures."""
        return list(self.signatures_data.keys())
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about stored signatures."""
        total_signatures = sum(len(sigs) for sigs in self.signatures_data.values())
        return {
            "components": len(self.signatures_data),
            "total_signatures": total_signatures,
            "avg_signatures_per_component": total_signatures / len(self.signatures_data) if self.signatures_data else 0
        }