# Code Deduplication Refactoring Plan

## Executive Summary

This document outlines a comprehensive plan to eliminate **40-50% code duplication** found in the mutation clinical trial matching MCP codebase. The duplication primarily exists between sync and async implementations of the same functionality.

**Key Metrics:**
- **~1,000 lines** of duplicated code identified
- **60% code reduction** potential through refactoring
- **4 major component pairs** requiring consolidation
- **Zero breaking changes** to external APIs

## Problem Analysis

### Root Causes of Duplication

1. **HTTP Library Migration**: Parallel `requests` (sync) and `httpx` (async) implementations
2. **Missing Abstraction Layer**: No unified HTTP client interface
3. **Async Transition Strategy**: Created parallel implementations instead of unified abstractions
4. **Node Pattern Duplication**: Separate hierarchies for sync/async execution

### Major Duplication Areas

| Component Pair | Duplication % | Lines Affected |
|---|---|---|
| `query.py` ↔ `async_query.py` | 95% | ~300 lines |
| `call_llm.py` ↔ `async_call_llm.py` | 95% | ~250 lines |
| `nodes.py` ↔ `async_nodes.py` | 85% | ~200 lines |
| `sync_server.py` ↔ `primary.py` | 70% | ~250 lines |

## Refactoring Strategy

### Core Design Principles

1. **Unified Abstraction**: Single implementation supporting both sync/async
2. **Polymorphic Execution**: Runtime mode selection without code duplication
3. **Interface Preservation**: Zero breaking changes to external APIs
4. **Dependency Injection**: Configurable execution patterns
5. **Backward Compatibility**: Gradual migration path

### Architecture Overview

```
┌─────────────────────────────────────────┐
│           Unified Server                │
│         (servers/main.py)               │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│        Unified Node Framework          │
│      (utils/unified_node.py)           │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│       Service Abstraction Layer        │
│   ┌─────────────┬─────────────────────┐ │
│   │ HTTP Client │  LLM Service        │ │
│   │ Abstraction │  Abstraction        │ │
│   └─────────────┴─────────────────────┘ │
└─────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Foundation Layer (Week 1)

#### 1.1 Create Unified HTTP Client (`utils/http_client.py`)

**New Component:**
```python
class UnifiedHttpClient:
    """HTTP client supporting both sync and async execution"""
    
    def __init__(self, async_mode: bool = False, **config):
        self.async_mode = async_mode
        self._setup_client(**config)
    
    def request(self, method: str, url: str, **kwargs) -> Response:
        """Unified request method - sync or async based on mode"""
        if self.async_mode:
            return self._async_request(method, url, **kwargs)
        return self._sync_request(method, url, **kwargs)
    
    async def arequest(self, method: str, url: str, **kwargs) -> Response:
        """Explicit async request method"""
        return await self._async_request(method, url, **kwargs)
```

**Features:**
- Automatic sync/async detection
- Unified error handling and retry logic
- Shared metrics collection
- Circuit breaker integration
- Connection pooling for both modes

#### 1.2 Create Shared Utilities (`utils/shared.py`)

**Components:**
- Input validation functions
- Error handling decorators  
- Metrics collection utilities
- Configuration access patterns
- Response processing functions

**Implementation:**
```python
# Shared validation
def validate_mutation_input(mutation: str, min_rank: int = None, max_rank: int = None) -> dict:
    """Unified input validation for all query functions"""

# Shared error handling
def handle_api_error(error: Exception, metrics_prefix: str = "") -> dict:
    """Unified error handling with metrics"""

# Shared metrics
class MetricsCollector:
    """Unified metrics collection for sync/async operations"""
```

### Phase 2: Service Layer Consolidation (Week 2)

#### 2.1 Unified LLM Service (`utils/llm_service.py`)

**Replace:** `utils/call_llm.py` + `utils/async_call_llm.py`

```python
class LLMService:
    """Unified LLM service supporting sync/async execution"""
    
    def __init__(self, async_mode: bool = False):
        self.client = UnifiedHttpClient(async_mode=async_mode)
        self.async_mode = async_mode
    
    def call_llm(self, messages: list, **kwargs) -> str:
        """Unified LLM calling - sync or async based on mode"""
        
    async def acall_llm(self, messages: list, **kwargs) -> str:
        """Explicit async LLM calling"""
```

**Migration Steps:**
1. Create `LLMService` class
2. Move shared logic from both files
3. Add backward compatibility wrappers
4. Update imports in dependent modules
5. Remove old files after verification

#### 2.2 Unified Clinical Trials Service (`clinicaltrials/service.py`)

**Replace:** `clinicaltrials/query.py` + `clinicaltrials/async_query.py`

```python
class ClinicalTrialsService:
    """Unified clinical trials querying service"""
    
    def __init__(self, async_mode: bool = False):
        self.client = UnifiedHttpClient(async_mode=async_mode)
        self.async_mode = async_mode
    
    def query_trials(self, mutation: str, **kwargs) -> dict:
        """Unified trial querying - sync or async based on mode"""
        
    async def aquery_trials(self, mutation: str, **kwargs) -> dict:
        """Explicit async trial querying"""
```

### Phase 3: Node Layer Unification (Week 3)

#### 3.1 Enhanced Node Framework (`utils/unified_node.py`)

**Replace:** Current node duplications

```python
class UnifiedNode:
    """Base node class supporting both sync and async execution"""
    
    def __init__(self, async_mode: bool = False, **services):
        self.async_mode = async_mode
        self.services = services
    
    def process(self, shared: dict) -> str | None:
        """Main processing method - delegates to sync or async"""
        if self.async_mode:
            return asyncio.run(self.aprocess(shared))
        return self._sync_process(shared)
    
    async def aprocess(self, shared: dict) -> str | None:
        """Async processing pipeline"""
        prep_result = await self.aprep(shared)
        exec_result = await self.aexec(prep_result)
        return await self.apost(shared, prep_result, exec_result)
    
    def _sync_process(self, shared: dict) -> str | None:
        """Sync processing pipeline"""
        prep_result = self.prep(shared)
        exec_result = self.exec(prep_result)
        return self.post(shared, prep_result, exec_result)
```

#### 3.2 Unified Clinical Trials Nodes (`clinicaltrials/unified_nodes.py`)

**Replace:** `clinicaltrials/nodes.py` + `clinicaltrials/async_nodes.py`

```python
class QueryTrialsNode(UnifiedNode):
    """Unified query trials node"""
    
    def __init__(self, async_mode: bool = False):
        service = ClinicalTrialsService(async_mode=async_mode)
        super().__init__(async_mode=async_mode, trials_service=service)
    
    def prep(self, shared: dict) -> dict:
        """Extract mutation from shared context"""
        # Single implementation - no duplication
    
    def exec(self, prep_result: dict) -> dict:
        """Query clinical trials"""
        return self.services['trials_service'].query_trials(**prep_result)
    
    async def aexec(self, prep_result: dict) -> dict:
        """Async query clinical trials"""
        return await self.services['trials_service'].aquery_trials(**prep_result)

class SummarizeTrialsNode(UnifiedNode):
    """Unified summarize trials node"""
    
    def __init__(self, async_mode: bool = False):
        service = LLMService(async_mode=async_mode)
        super().__init__(async_mode=async_mode, llm_service=service)
```

### Phase 4: Server Consolidation (Week 4)

#### 4.1 Unified Server Architecture (`servers/main.py`)

**Replace:** `servers/primary.py` + `servers/legacy/sync_server.py`

```python
class UnifiedMCPServer:
    """Single MCP server supporting both sync and async execution"""
    
    def __init__(self, async_mode: bool = True):
        self.async_mode = async_mode
        self.app = FastMCP("clinical-trials-mcp")
        self._setup_tools()
    
    @mcp.tool()
    def summarize_trials(self, mutation: str) -> str:
        """Unified tool supporting both execution modes"""
        
        # Create nodes with appropriate mode
        query_node = QueryTrialsNode(async_mode=self.async_mode)
        summarize_node = SummarizeTrialsNode(async_mode=self.async_mode)
        
        # Execute flow
        flow = Flow([query_node, summarize_node], async_mode=self.async_mode)
        return flow.execute({"mutation": mutation})
```

#### 4.2 Runtime Mode Selection

**Configuration-Based Mode:**
```python
# Environment-based mode selection
ASYNC_MODE = os.getenv("MCP_ASYNC_MODE", "true").lower() == "true"

# Server initialization
server = UnifiedMCPServer(async_mode=ASYNC_MODE)
```

**Dynamic Mode Detection:**
```python
# Auto-detect based on event loop
try:
    asyncio.get_running_loop()
    async_mode = True
except RuntimeError:
    async_mode = False
```

## Migration Strategy

### Rollout Phases

#### Phase 1: Parallel Development (Safe)
- Create new unified components alongside existing ones
- No changes to existing functionality
- Comprehensive testing of new components
- **Risk Level: None**

#### Phase 2: Gradual Migration (Low Risk)
- Update imports to use new unified components
- Keep old components as deprecated wrappers
- Monitor performance and functionality
- **Risk Level: Low**

#### Phase 3: Legacy Cleanup (Medium Risk)
- Remove deprecated components after validation
- Update documentation and tests
- Final performance optimization
- **Risk Level: Medium**

### Backward Compatibility Strategy

```python
# Deprecated wrapper for old query.py
def query_trials_sync(mutation: str, **kwargs) -> dict:
    """DEPRECATED: Use ClinicalTrialsService instead"""
    warnings.warn("query_trials_sync is deprecated", DeprecationWarning)
    service = ClinicalTrialsService(async_mode=False)
    return service.query_trials(mutation, **kwargs)

# Deprecated wrapper for old async_query.py  
async def query_trials_async(mutation: str, **kwargs) -> dict:
    """DEPRECATED: Use ClinicalTrialsService instead"""
    warnings.warn("query_trials_async is deprecated", DeprecationWarning)
    service = ClinicalTrialsService(async_mode=True)
    return await service.aquery_trials(mutation, **kwargs)
```

## Testing Strategy

### Unified Test Framework

```python
class UnifiedTestCase:
    """Base test class supporting both sync and async testing"""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_functionality(self, async_mode: bool):
        """Test both sync and async modes with single test"""
        
        component = ComponentClass(async_mode=async_mode)
        
        if async_mode:
            result = asyncio.run(component.aprocess(input_data))
        else:
            result = component.process(input_data)
            
        assert result == expected_result
```

### Test Coverage Plan

1. **Unit Tests**: Each unified component tested in both modes
2. **Integration Tests**: End-to-end flows in both modes  
3. **Performance Tests**: Benchmark sync vs async performance
4. **Compatibility Tests**: Verify existing interfaces still work
5. **Migration Tests**: Validate gradual migration steps

## Benefits and ROI

### Immediate Benefits

- **60% Code Reduction**: ~1,000 lines eliminated
- **Single Point of Truth**: Unified business logic
- **Reduced Maintenance**: One codebase to maintain instead of two
- **Improved Testing**: Unified test suites
- **Better Documentation**: Single set of docs to maintain

### Long-term Benefits

- **Easier Feature Development**: Add features once, get both modes
- **Reduced Bug Risk**: No sync/async inconsistencies
- **Performance Optimization**: Optimized execution paths
- **Future-Proofing**: Easy to add new execution patterns
- **Developer Experience**: Simpler codebase to understand

### Performance Impact

**Expected Improvements:**
- **Memory Usage**: 30-40% reduction due to code deduplication
- **Startup Time**: 20-30% faster due to reduced module loading
- **Maintenance Overhead**: 60% reduction in code to maintain
- **Testing Time**: 50% reduction in test execution

## Risk Assessment

### Low Risk Elements
- ✅ New component creation (parallel to existing)
- ✅ Unified utility functions
- ✅ Configuration-based mode selection
- ✅ Backward compatibility wrappers

### Medium Risk Elements
- ⚠️ Server consolidation (requires careful testing)
- ⚠️ Node framework changes (affects core logic)
- ⚠️ Import path updates (potential breaking changes)

### Mitigation Strategies

1. **Comprehensive Testing**: Both modes tested extensively
2. **Gradual Rollout**: Phase-by-phase implementation
3. **Rollback Plan**: Keep deprecated components until verified
4. **Monitoring**: Performance and error monitoring during migration
5. **Documentation**: Clear migration guides and examples

## Success Metrics

### Code Quality Metrics
- [ ] **Code Duplication**: Reduce from 40% to <5%
- [ ] **Lines of Code**: Reduce by 1,000+ lines
- [ ] **Cyclomatic Complexity**: Reduce average complexity by 20%
- [ ] **Test Coverage**: Maintain >90% coverage

### Performance Metrics  
- [ ] **Memory Usage**: Reduce by 30-40%
- [ ] **Startup Time**: Improve by 20-30%
- [ ] **Response Time**: Maintain or improve current performance
- [ ] **Error Rate**: Maintain current low error rates

### Development Metrics
- [ ] **Time to Add Features**: Reduce by 50% (implement once vs twice)
- [ ] **Bug Fix Time**: Reduce by 60% (fix once vs twice)
- [ ] **Onboarding Time**: Reduce by 40% (simpler codebase)

## Implementation Timeline

| Week | Phase | Deliverables | Risk Level |
|------|-------|-------------|------------|
| 1 | Foundation | HTTP Client, Shared Utilities | None |
| 2 | Services | LLM Service, Trials Service | Low |  
| 3 | Nodes | Unified Node Framework | Medium |
| 4 | Server | Unified Server, Migration Complete | Medium |

**Total Estimated Effort:** 4 weeks  
**Team Size:** 1-2 developers  
**Review Points:** End of each week

## Next Steps

1. **Review and Approve Plan**: Stakeholder review of this document
2. **Create Feature Branch**: `feature/code-deduplication`
3. **Begin Phase 1**: Start with foundation layer implementation
4. **Set Up Monitoring**: Track metrics during migration
5. **Schedule Reviews**: Weekly progress reviews

---

*This plan provides a comprehensive roadmap for eliminating code duplication while maintaining system stability and performance. The phased approach ensures minimal risk while achieving significant code quality improvements.*