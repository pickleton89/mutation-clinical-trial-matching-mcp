"""
Cache warming strategies and smart invalidation for distributed cache.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from clinicaltrials.async_query import query_clinical_trials_async
from utils.distributed_cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class CacheWarmingStrategy:
    """Configuration for cache warming strategy."""

    name: str
    mutations: list[str]
    priority: int = 1
    schedule: str = "startup"  # startup, periodic, on_demand
    max_concurrent: int = 5
    ttl: int | None = None


class CacheWarmer:
    """
    Cache warming system for preloading frequently accessed data.
    """

    def __init__(self):
        self.cache = get_cache()
        self.strategies: dict[str, CacheWarmingStrategy] = {}
        self.warming_stats = {
            "total_warmed": 0,
            "successful": 0,
            "failed": 0,
            "last_warming_time": None,
            "warming_duration": 0,
        }

    def add_strategy(self, strategy: CacheWarmingStrategy):
        """Add a cache warming strategy."""
        self.strategies[strategy.name] = strategy
        logger.info(f"Added cache warming strategy: {strategy.name}")

    def remove_strategy(self, name: str):
        """Remove a cache warming strategy."""
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"Removed cache warming strategy: {name}")

    async def warm_common_mutations(self) -> int:
        """
        Warm cache with common mutations.

        Returns:
            Number of items successfully warmed
        """
        common_mutations = [
            "EGFR L858R",
            "EGFR exon 19 deletion",
            "KRAS G12C",
            "BRAF V600E",
            "ALK EML4",
            "ROS1 CD74",
            "MET exon 14 skipping",
            "NTRK fusion",
            "RET fusion",
            "ERBB2 amplification",
        ]

        strategy = CacheWarmingStrategy(
            name="common_mutations",
            mutations=common_mutations,
            priority=1,
            max_concurrent=5,
            ttl=7200,  # 2 hours for common mutations
        )

        return await self.execute_strategy(strategy)

    async def warm_trending_mutations(self) -> int:
        """
        Warm cache with trending mutations based on recent queries.

        Returns:
            Number of items successfully warmed
        """
        # In a real implementation, this would analyze recent query patterns
        # For now, using a predefined list of trending mutations
        trending_mutations = [
            "PIK3CA H1047R",
            "TP53 R273H",
            "PTEN loss",
            "CDKN2A deletion",
            "FGFR2 fusion",
        ]

        strategy = CacheWarmingStrategy(
            name="trending_mutations",
            mutations=trending_mutations,
            priority=2,
            max_concurrent=3,
            ttl=3600,  # 1 hour for trending mutations
        )

        return await self.execute_strategy(strategy)

    async def execute_strategy(self, strategy: CacheWarmingStrategy) -> int:
        """
        Execute a cache warming strategy.

        Args:
            strategy: The strategy to execute

        Returns:
            Number of items successfully warmed
        """
        start_time = time.time()
        logger.info(f"Starting cache warming strategy: {strategy.name}")

        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(strategy.max_concurrent)

        async def warm_mutation(mutation: str) -> bool:
            async with semaphore:
                try:
                    # Generate cache key
                    cache_key = f"query:{mutation}:1:10"

                    # Check if already cached
                    cached_result = await self.cache.get_async(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Mutation {mutation} already cached")
                        return True

                    # Query and cache result
                    result = await query_clinical_trials_async(mutation)

                    # Cache the result
                    ttl = strategy.ttl if strategy.ttl else self.cache.default_ttl
                    success = await self.cache.set_async(cache_key, result, ttl)

                    if success:
                        logger.debug(f"Successfully warmed cache for mutation: {mutation}")
                        return True
                    else:
                        logger.warning(f"Failed to cache mutation: {mutation}")
                        return False

                except Exception as e:
                    logger.error(f"Error warming cache for mutation {mutation}: {e}")
                    return False

        # Execute warming tasks concurrently
        tasks = [warm_mutation(mutation) for mutation in strategy.mutations]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful warmings
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful

        # Update statistics
        duration = time.time() - start_time
        self.warming_stats["total_warmed"] += len(strategy.mutations)
        self.warming_stats["successful"] += successful
        self.warming_stats["failed"] += failed
        self.warming_stats["last_warming_time"] = time.time()
        self.warming_stats["warming_duration"] = duration

        logger.info(
            f"Cache warming strategy '{strategy.name}' completed: "
            f"{successful}/{len(strategy.mutations)} successful in {duration:.2f}s"
        )

        return successful

    async def warm_all_strategies(self) -> dict[str, int]:
        """
        Execute all registered cache warming strategies.

        Returns:
            Dictionary mapping strategy names to success counts
        """
        results = {}

        # Sort strategies by priority
        sorted_strategies = sorted(self.strategies.values(), key=lambda s: s.priority)

        for strategy in sorted_strategies:
            results[strategy.name] = await self.execute_strategy(strategy)

        return results

    def get_warming_stats(self) -> dict[str, Any]:
        """Get cache warming statistics."""
        return self.warming_stats.copy()


class SmartInvalidator:
    """
    Smart cache invalidation system that tracks dependencies and invalidates related data.
    """

    def __init__(self):
        self.cache = get_cache()
        self.invalidation_rules: dict[str, list[Callable]] = {}
        self.invalidation_stats = {
            "total_invalidations": 0,
            "pattern_invalidations": 0,
            "dependency_invalidations": 0,
            "last_invalidation_time": None,
        }

    def add_invalidation_rule(self, trigger: str, rule: Callable[[str], list[str]]):
        """
        Add a smart invalidation rule.

        Args:
            trigger: The trigger pattern (e.g., "mutation_update")
            rule: Function that returns list of cache keys to invalidate
        """
        if trigger not in self.invalidation_rules:
            self.invalidation_rules[trigger] = []

        self.invalidation_rules[trigger].append(rule)
        logger.info(f"Added invalidation rule for trigger: {trigger}")

    async def invalidate_mutation_data(self, mutation: str) -> int:
        """
        Invalidate all cache entries related to a specific mutation.

        Args:
            mutation: The mutation to invalidate

        Returns:
            Number of cache entries invalidated
        """
        patterns = [f"query:{mutation}:*", f"summary:{mutation}:*", f"batch:*{mutation}*"]

        total_invalidated = 0

        for pattern in patterns:
            invalidated = await self.cache.invalidate_pattern_async(pattern)
            total_invalidated += invalidated
            logger.info(f"Invalidated {invalidated} entries for pattern: {pattern}")

        self.invalidation_stats["pattern_invalidations"] += total_invalidated
        self.invalidation_stats["total_invalidations"] += total_invalidated
        self.invalidation_stats["last_invalidation_time"] = time.time()

        return total_invalidated

    async def invalidate_by_age(self, max_age: int) -> int:
        """
        Invalidate cache entries older than max_age seconds.

        Args:
            max_age: Maximum age in seconds

        Returns:
            Number of cache entries invalidated
        """
        # This would require custom Redis logic or metadata tracking
        # For now, we'll use a simple pattern-based approach
        logger.info(f"Age-based invalidation not fully implemented (max_age: {max_age}s)")
        return 0

    async def invalidate_low_hit_entries(self, min_hit_count: int = 2) -> int:
        """
        Invalidate cache entries with low hit counts.

        Args:
            min_hit_count: Minimum hit count to keep

        Returns:
            Number of cache entries invalidated
        """
        # This would require analyzing hit count metadata
        # For now, we'll use a simple pattern-based approach
        logger.info(f"Hit-based invalidation not fully implemented (min_hits: {min_hit_count})")
        return 0

    async def trigger_invalidation(self, trigger: str, context: str) -> int:
        """
        Trigger smart invalidation based on a trigger and context.

        Args:
            trigger: The trigger type
            context: Context information for the trigger

        Returns:
            Number of cache entries invalidated
        """
        total_invalidated = 0

        if trigger in self.invalidation_rules:
            for rule in self.invalidation_rules[trigger]:
                try:
                    keys_to_invalidate = rule(context)

                    for key in keys_to_invalidate:
                        success = await self.cache.delete_async(key)
                        if success:
                            total_invalidated += 1

                    logger.info(
                        f"Invalidated {len(keys_to_invalidate)} entries for trigger: {trigger}"
                    )

                except Exception as e:
                    logger.error(f"Error in invalidation rule for trigger {trigger}: {e}")

        self.invalidation_stats["dependency_invalidations"] += total_invalidated
        self.invalidation_stats["total_invalidations"] += total_invalidated
        self.invalidation_stats["last_invalidation_time"] = time.time()

        return total_invalidated

    async def invalidate_pattern_async(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Pattern to match cache keys ("*" for all)

        Returns:
            Number of entries invalidated
        """
        # Use the cache's built-in pattern invalidation
        total_invalidated = await self.cache.invalidate_pattern_async(pattern)

        self.invalidation_stats["pattern_invalidations"] += total_invalidated
        self.invalidation_stats["total_invalidations"] += total_invalidated
        self.invalidation_stats["last_invalidation_time"] = time.time()

        return total_invalidated

    def get_invalidation_stats(self) -> dict[str, Any]:
        """Get invalidation statistics."""
        return self.invalidation_stats.copy()


class CacheAnalytics:
    """
    Cache analytics system for monitoring and optimizing cache performance.
    """

    def __init__(self):
        self.cache = get_cache()
        self.warmer = CacheWarmer()
        self.invalidator = SmartInvalidator()

    async def get_comprehensive_stats(self) -> dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with all cache analytics
        """
        cache_stats = self.cache.get_stats()
        warming_stats = self.warmer.get_warming_stats()
        invalidation_stats = self.invalidator.get_invalidation_stats()

        return {
            "cache": cache_stats,
            "warming": warming_stats,
            "invalidation": invalidation_stats,
            "timestamp": time.time(),
        }

    async def analyze_cache_efficiency(self) -> dict[str, Any]:
        """
        Analyze cache efficiency and provide recommendations.

        Returns:
            Dictionary with efficiency analysis and recommendations
        """
        stats = await self.get_comprehensive_stats()
        cache_stats = stats["cache"]

        # Calculate efficiency metrics
        hit_rate = cache_stats.get("hit_rate", 0)
        error_rate = cache_stats.get("errors", 0) / max(cache_stats.get("total_requests", 1), 1)

        # Generate recommendations
        recommendations = []

        if hit_rate < 0.6:
            recommendations.append("Consider increasing cache TTL or implementing cache warming")

        if error_rate > 0.05:
            recommendations.append("High error rate detected, check Redis connectivity")

        if cache_stats.get("total_requests", 0) < 100:
            recommendations.append("Low cache usage, consider promoting cache usage")

        return {
            "hit_rate": hit_rate,
            "error_rate": error_rate,
            "recommendations": recommendations,
            "efficiency_score": (hit_rate * 100) - (error_rate * 100),
        }

    async def generate_cache_report(self) -> str:
        """
        Generate a formatted cache performance report.

        Returns:
            Formatted report string
        """
        stats = await self.get_comprehensive_stats()
        efficiency = await self.analyze_cache_efficiency()

        report = f"""
# Cache Performance Report

## Cache Statistics
- Hit Rate: {stats["cache"]["hit_rate"]:.2%}
- Total Requests: {stats["cache"]["total_requests"]:,}
- Cache Hits: {stats["cache"]["hits"]:,}
- Cache Misses: {stats["cache"]["misses"]:,}
- Cache Sets: {stats["cache"]["sets"]:,}
- Errors: {stats["cache"]["errors"]:,}

## Cache Warming
- Total Warmed: {stats["warming"]["total_warmed"]:,}
- Successful: {stats["warming"]["successful"]:,}
- Failed: {stats["warming"]["failed"]:,}
- Last Warming: {stats["warming"]["last_warming_time"]}

## Cache Invalidation
- Total Invalidations: {stats["invalidation"]["total_invalidations"]:,}
- Pattern Invalidations: {stats["invalidation"]["pattern_invalidations"]:,}
- Dependency Invalidations: {stats["invalidation"]["dependency_invalidations"]:,}

## Efficiency Analysis
- Efficiency Score: {efficiency["efficiency_score"]:.1f}
- Error Rate: {efficiency["error_rate"]:.2%}

## Recommendations
"""

        for rec in efficiency["recommendations"]:
            report += f"- {rec}\n"

        return report


# Global instances
_cache_warmer: CacheWarmer | None = None
_smart_invalidator: SmartInvalidator | None = None
_cache_analytics: CacheAnalytics | None = None


def get_cache_warmer() -> CacheWarmer:
    """Get global cache warmer instance."""
    global _cache_warmer
    if _cache_warmer is None:
        _cache_warmer = CacheWarmer()
    assert _cache_warmer is not None  # Type narrowing
    return _cache_warmer


def get_smart_invalidator() -> SmartInvalidator:
    """Get global smart invalidator instance."""
    global _smart_invalidator
    if _smart_invalidator is None:
        _smart_invalidator = SmartInvalidator()
    assert _smart_invalidator is not None  # Type narrowing
    return _smart_invalidator


def get_cache_analytics() -> CacheAnalytics:
    """Get global cache analytics instance."""
    global _cache_analytics
    if _cache_analytics is None:
        _cache_analytics = CacheAnalytics()
    assert _cache_analytics is not None  # Type narrowing
    return _cache_analytics
