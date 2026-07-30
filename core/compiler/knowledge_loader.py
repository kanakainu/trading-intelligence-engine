import os
import yaml
import logging
from typing import Dict, Any, Type, Optional
from collections import defaultdict
from hashlib import md5

# Import SchemaValidator from the correct relative path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..' )))
from core.schema.schema_validator import SchemaValidator

log = logging.getLogger(__name__)

# Base class for all Knowledge Objects
class KnowledgeObject:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.category = kwargs.get('category')
        self.version = kwargs.get('version')
        self.status = kwargs.get('status')
        self.description = kwargs.get('description', '')
        self.tags = kwargs.get('tags', [])
        self.references = kwargs.get('references', [])
        self.metadata = kwargs.get('metadata', {})
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"<{self.category}:{self.id} {self.name}>"

# Registries for each category
class KnowledgeRegistry:
    def __init__(self):
        self._data: Dict[str, Dict[str, KnowledgeObject]] = defaultdict(dict)
        self._checksums: Dict[str, str] = {}

    def add(self, obj: KnowledgeObject, file_path: str, checksum: str):
        if obj.category not in self._data:
            log.warning(f"Category {obj.category} not explicitly defined in registry, creating new entry.")
        self._data[obj.category][obj.id] = obj
        self._checksums[file_path] = checksum

    def get_by_id(self, category: str, obj_id: str) -> Optional[KnowledgeObject]:
        return self._data.get(category, {}).get(obj_id)

    def get_all(self, category: str) -> Dict[str, KnowledgeObject]:
        return self._data.get(category, {})
    
    def get_checksum(self, file_path: str) -> Optional[str]:
        return self._checksums.get(file_path)

    @property
    def total_objects(self) -> int:
        return sum(len(cat_data) for cat_data in self._data.values())

    def count_by_category(self, category: str) -> int:
        return len(self._data.get(category, {}))


class KnowledgeLoader:
    def __init__(self, base_path: str, schema_path: str):
        self.base_path = base_path
        self.validator = SchemaValidator(schema_path)
        self.registry = KnowledgeRegistry()
        self.cache_checksums: Dict[str, str] = {}

    def _calculate_checksum(self, file_path: str) -> str:
        with open(file_path, 'rb') as f:
            return md5(f.read()).hexdigest()

    def load_knowledge_pack(self, pack_path: str) -> None:
        log.info(f"Scanning knowledge pack: {pack_path}")
        # Fresh validator per pack — prevents name collision across packs
        pack_validator = SchemaValidator(self.validator.schema_path)
        # Seed with already-known ids/names to still catch cross-pack duplicates
        pack_validator.known_ids = set(self.validator.known_ids)
        pack_validator.known_names = set(self.validator.known_names)
        for root, _, files in os.walk(pack_path):
            for file in files:
                if file.endswith('.yaml'):
                    file_path = os.path.join(root, file)
                    checksum = self._calculate_checksum(file_path)

                    if self.cache_checksums.get(file_path) == checksum:
                        log.debug(f"Skipping {file_path} (unchanged)")
                        continue

                    log.debug(f"Loading and validating {file_path}")
                    with open(file_path, 'r') as f:
                        try:
                            obj_data = yaml.safe_load(f)
                            if not obj_data:
                                log.warning(f"Empty YAML file: {file_path}")
                                continue

                            # Use pack-scoped validator to avoid cross-pack name dedup
                            is_valid, msg = pack_validator.validate_object(obj_data)
                            if not is_valid:
                                # If validation fails due to duplicate ID, check if it's a cache reload
                                if "Duplicate ID" in msg:
                                    # Remove old object from registry to allow update
                                    existing_obj = self.registry.get_by_id(obj_data.get('category', ''), obj_data.get('id', ''))
                                    if existing_obj:
                                        log.info(f"Updating existing object: {existing_obj}")
                                        self._remove_from_registry(existing_obj, pack_validator)
                                        # Retry validation
                                        is_valid, msg = pack_validator.validate_object(obj_data)
                                
                                if not is_valid:
                                    log.error(f"Validation failed for {file_path}: {msg}")
                                    continue
                            
                            obj = KnowledgeObject(**obj_data)
                            self.registry.add(obj, file_path, checksum)
                            self.cache_checksums[file_path] = checksum
                            log.info(f"Loaded {obj}")

                        except yaml.YAMLError as e:
                            log.error(f"YAML parsing error in {file_path}: {e}")
                        except Exception as e:
                            log.error(f"Error processing {file_path}: {e}")
        # Sync pack_validator state back so next pack inherits known IDs/names
        self.validator.known_ids = set(pack_validator.known_ids)
        self.validator.known_names = set(pack_validator.known_names)

    def _remove_from_registry(self, obj: KnowledgeObject, extra_validator=None):
        """Remove object from registry by ID"""
        if obj.category in self.registry._data and obj.id in self.registry._data[obj.category]:
            del self.registry._data[obj.category][obj.id]
            # Remove from both validators
            for v in [self.validator, extra_validator]:
                if v:
                    v.known_ids.discard(obj.id)
                    v.known_names.discard(obj.name)

    def load_all(self) -> KnowledgeRegistry:
        knowledge_base_path = os.path.join(self.base_path, 'knowledge')
        for pack_name in os.listdir(knowledge_base_path):
            pack_path = os.path.join(knowledge_base_path, pack_name)
            if os.path.isdir(pack_path):
                self.load_knowledge_pack(pack_path)
        
        log.info(f"Loaded {self.registry.total_objects} Knowledge Objects in total.")
        for category in self.validator.schema['objects'].keys():
            log.info(f"Loaded {self.registry.count_by_category(category)} {category}s.")
        
        log.info("Knowledge Loader: Validation Success for all loaded objects.")
        return self.registry

