"""Strategy Registry — Dynamic strategy loading and management.

NO execution logic.
Pure plugin registry.
"""
from typing import Dict, Optional, List, Callable, Any
from core.registry.registry_models import StrategyMetadata, StrategyEntry


class StrategyRegistry:
    """
    Central registry for all trading strategies.
    
    Supports:
    - Dynamic registration
    - Metadata query
    - Strategy instantiation
    - Enable/disable
    """
    
    def __init__(self):
        self._strategies: Dict[str, StrategyEntry] = {}
    
    def register(
        self,
        name: str,
        factory: Callable,
        metadata: StrategyMetadata,
        enabled: bool = True
    ) -> None:
        """Register a strategy."""
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' already registered")
        
        entry = StrategyEntry(
            metadata=metadata,
            factory=factory,
            enabled=enabled
        )
        self._strategies[name] = entry
    
    def unregister(self, name: str) -> None:
        """Remove a strategy from registry."""
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not found")
        del self._strategies[name]
    
    def get(self, name: str) -> Optional[StrategyEntry]:
        """Get strategy entry by name."""
        return self._strategies.get(name)
    
    def list_all(self) -> List[str]:
        """List all registered strategy names."""
        return list(self._strategies.keys())
    
    def list_enabled(self) -> List[str]:
        """List enabled strategy names."""
        return [name for name, entry in self._strategies.items() if entry.enabled]
    
    def enable(self, name: str) -> None:
        """Enable a strategy."""
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not found")
        self._strategies[name].enabled = True
    
    def disable(self, name: str) -> None:
        """Disable a strategy."""
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not found")
        self._strategies[name].enabled = False
    
    def instantiate(self, name: str, **kwargs) -> Any:
        """Create instance of strategy."""
        entry = self.get(name)
        if not entry:
            raise ValueError(f"Strategy '{name}' not found")
        
        if not entry.enabled:
            raise RuntimeError(f"Strategy '{name}' is disabled")
        
        return entry.factory(**kwargs)
    
    def get_metadata(self, name: str) -> Optional[StrategyMetadata]:
        """Get strategy metadata."""
        entry = self.get(name)
        return entry.metadata if entry else None
    
    def search(
        self,
        symbol: Optional[str] = None,
        session: Optional[str] = None,
        min_balance: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> List[str]:
        """Search strategies by criteria."""
        results = []
        
        for name, entry in self._strategies.items():
            if not entry.enabled:
                continue
            
            meta = entry.metadata
            
            # Symbol filter
            if symbol and symbol not in meta.supported_symbols:
                continue
            
            # Session filter
            if session and session not in meta.supported_sessions:
                continue
            
            # Balance filter
            if min_balance and meta.min_balance > min_balance:
                continue
            
            # Tag filter
            if tags and not any(tag in meta.tags for tag in tags):
                continue
            
            results.append(name)
        
        return results


# Global registry instance
_global_registry: Optional[StrategyRegistry] = None


def get_strategy_registry() -> StrategyRegistry:
    """Get or create global strategy registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = StrategyRegistry()
    return _global_registry


def register_strategy(
    name: str,
    factory: Callable,
    metadata: StrategyMetadata,
    enabled: bool = True
) -> None:
    """Convenience function to register strategy."""
    registry = get_strategy_registry()
    registry.register(name, factory, metadata, enabled)