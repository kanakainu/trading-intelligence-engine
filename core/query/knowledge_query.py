"""KnowledgeQuery — thin wrapper around QueryEngine with named methods."""
from typing import List
from core.query.query_engine import QueryEngine
from core.query.query_result import QueryResult


class KnowledgeQuery:
    def __init__(self, engine: QueryEngine):
        self._e = engine

    def find_by_id(self, id: str) -> QueryResult:
        return self._e.find_by_id(id)

    def find_by_name(self, name: str) -> QueryResult:
        return self._e.find_by_name(name)

    def find_by_category(self, category: str) -> List[QueryResult]:
        return self._e.find_by_category(category)

    def find_all(self, category: str) -> List[QueryResult]:
        return self._e.find_by_category(category)

    def exists(self, id: str) -> bool:
        return self._e.exists(id)

    def dependencies(self, id: str) -> List[str]:
        return self._e.dependencies(id)

    def reverse_dependencies(self, id: str) -> List[str]:
        return self._e.reverse_dependencies(id)

    def related(self, id: str) -> List[str]:
        return self._e.related(id)

    def search(self, keyword: str) -> List[QueryResult]:
        return self._e.search(keyword)

    def explain(self, id: str) -> QueryResult:
        return self._e.explain(id)
