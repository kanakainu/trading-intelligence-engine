"""Query Engine — reads KnowledgeGraph only. No YAML, no trading logic."""
import os, yaml, logging
from typing import Any, Dict, List, Set
from core.query.query_result import QueryResult
from core.query.query_cache import QueryCache

log = logging.getLogger(__name__)

BYSTRA_PACKS = [
    "knowledge/bystra/concepts",
    "knowledge/bystra/structures",
    "knowledge/bystra/locations",
    "knowledge/bystra/confirmations",
    "knowledge/bystra/risks",
    "knowledge/bystra/entry_patterns",
    "knowledge/bystra/setups",
]


class QueryEngine:
    """
    Abstraction layer over Knowledge Graph.
    Builds index once from loaded objects, never re-reads YAML.
    """

    def __init__(self):
        self._by_id:   Dict[str, Dict] = {}
        self._by_name: Dict[str, str]  = {}   # name → id
        self._by_cat:  Dict[str, List[str]] = {}
        self._cache = QueryCache()
        self._built = False

    # ── Build ─────────────────────────────────────────────────────────────

    def build_from_objects(self, objects: List[Dict]) -> None:
        """Load pre-parsed objects (no YAML I/O)."""
        for obj in objects:
            oid  = obj.get("id", "")
            name = obj.get("name", "")
            cat  = obj.get("category", "")
            if oid:
                self._by_id[oid] = obj
            if name:
                self._by_name[name.lower()] = oid
            if cat:
                self._by_cat.setdefault(cat, []).append(oid)
        self._built = True
        log.info(f"QueryEngine built: {len(self._by_id)} objects")

    def build_from_dirs(self, base_path: str, pack_dirs: List[str] = None) -> None:
        """Convenience: load from YAML dirs. Call once at startup."""
        dirs = pack_dirs or BYSTRA_PACKS
        objects = []
        for rel in dirs:
            path = os.path.join(base_path, rel)
            if not os.path.isdir(path):
                continue
            for f in os.listdir(path):
                if f.endswith(".yaml"):
                    with open(os.path.join(path, f)) as fh:
                        obj = yaml.safe_load(fh)
                        if obj:
                            objects.append(obj)
        self.build_from_objects(objects)

    # ── Core API ──────────────────────────────────────────────────────────

    def find_by_id(self, id: str) -> QueryResult:
        cached = self._cache.get(f"id:{id}")
        if cached:
            return cached
        obj = self._by_id.get(id)
        r = QueryResult(success=bool(obj), object=obj,
                        message="" if obj else f"Not found: {id}")
        self._cache.set(f"id:{id}", r)
        return r

    def find_by_name(self, name: str) -> QueryResult:
        oid = self._by_name.get(name.lower())
        if not oid:
            return QueryResult(success=False, message=f"Not found: {name}")
        return self.find_by_id(oid)

    def find_by_category(self, category: str) -> List[QueryResult]:
        cached = self._cache.get(f"cat:{category}")
        if cached:
            return cached
        ids = self._by_cat.get(category, [])
        results = [self.find_by_id(oid) for oid in ids]
        self._cache.set(f"cat:{category}", results)
        return results

    def exists(self, id: str) -> bool:
        return id in self._by_id

    def dependencies(self, id: str) -> List[str]:
        cached = self._cache.get(f"dep:{id}")
        if cached is not None:
            return cached
        obj = self._by_id.get(id, {})
        deps: Set[str] = set()
        for field in ["requires", "related_objects", "strengthens",
                      "required_structures", "required_concepts", "invalid_if"]:
            for ref in obj.get(field, []):
                if isinstance(ref, str) and ref.startswith("BYS-"):
                    deps.add(ref)
        result = sorted(deps)
        self._cache.set(f"dep:{id}", result)
        return result

    def reverse_dependencies(self, id: str) -> List[str]:
        cached = self._cache.get(f"rdep:{id}")
        if cached is not None:
            return cached
        result = [oid for oid, obj in self._by_id.items()
                  if id in self.dependencies(oid) and oid != id]
        self._cache.set(f"rdep:{id}", result)
        return result

    def related(self, id: str) -> List[str]:
        obj = self._by_id.get(id, {})
        return [ref for ref in obj.get("related_objects", [])
                if isinstance(ref, str)]

    def search(self, keyword: str) -> List[QueryResult]:
        cached = self._cache.get(f"search:{keyword.lower()}")
        if cached:
            return cached
        kw = keyword.lower()
        results = []
        for obj in self._by_id.values():
            text = " ".join([
                obj.get("name", ""),
                obj.get("definition", ""),
                obj.get("description", ""),
                " ".join(obj.get("aliases", [])),
                " ".join(obj.get("tags", [])),
            ]).lower()
            if kw in text:
                results.append(QueryResult(success=True, object=obj))
        self._cache.set(f"search:{keyword.lower()}", results)
        return results

    def explain(self, id: str) -> QueryResult:
        obj = self._by_id.get(id)
        if not obj:
            return QueryResult(success=False, message=f"Not found: {id}")
        deps = self.dependencies(id)
        rdeps = self.reverse_dependencies(id)
        refs = obj.get("references", [])
        related = [self._by_id.get(r, {}).get("name", r)
                   for r in obj.get("related_objects", [])[:5]]
        return QueryResult(
            success=True,
            object=obj,
            dependencies=deps,
            related_objects=[{"id": r, "name": self._by_id.get(r, {}).get("name", r)}
                             for r in rdeps[:10]],
            references=refs,
        )
