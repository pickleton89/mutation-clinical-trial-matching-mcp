"""
Unified Clinical Trials nodes using the new service layer.

This module provides unified node implementations that replace the duplicated
clinicaltrials/nodes.py and clinicaltrials/async_nodes.py files, using the
new ClinicalTrialsService and LLMService for all operations.
"""

import logging
from typing import Any

from clinicaltrials.service import ClinicalTrialsService
from utils.llm_service import LLMService
from utils.unified_node import UnifiedBatchNode, UnifiedNode

logger = logging.getLogger(__name__)


class QueryTrialsNode(UnifiedNode[str, dict[str, Any]]):
    """
    Unified node for querying clinical trials.

    This node replaces both QueryTrialsNode (sync) and AsyncQueryTrialsNode (async)
    by using the unified ClinicalTrialsService underneath.
    """

    def __init__(
        self,
        async_mode: bool | None = None,
        min_rank: int = 1,
        max_rank: int = 10,
        timeout: float | None = None,
        **kwargs
    ):
        """
        Initialize the query trials node.

        Args:
            async_mode: Force sync/async mode
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            timeout: Custom timeout for requests
            **kwargs: Additional arguments for base class
        """
        super().__init__(async_mode=async_mode, **kwargs)
        self.min_rank = min_rank
        self.max_rank = max_rank
        self.timeout = timeout

        # Initialize the service with the appropriate mode
        detected_async = self._detect_async_mode()
        self.trials_service = ClinicalTrialsService(async_mode=detected_async)

        logger.info(
            f"Initialized QueryTrialsNode in {'async' if detected_async else 'sync'} mode",
            extra={
                "action": "query_trials_node_initialized",
                "node_id": self.node_id,
                "async_mode": detected_async,
                "min_rank": min_rank,
                "max_rank": max_rank,
                "timeout": timeout
            }
        )

    def prep(self, shared: dict[str, Any]) -> str:
        """
        Extract mutation from shared context.

        Args:
            shared: Shared context containing mutation data

        Returns:
            Mutation string to query
        """
        mutation = shared.get("mutation")
        if not mutation:
            raise ValueError("No mutation found in shared context")

        logger.debug(
            f"Prepared mutation for query: {mutation}",
            extra={
                "action": "query_trials_prep",
                "node_id": self.node_id,
                "mutation": mutation
            }
        )

        return mutation

    def exec(self, prep_result: str) -> dict[str, Any]:
        """
        Query clinical trials for the mutation (sync).

        Args:
            prep_result: Mutation string from prep

        Returns:
            Clinical trials query results
        """
        mutation = prep_result

        logger.info(
            f"Querying trials for mutation: {mutation}",
            extra={
                "action": "query_trials_exec_start",
                "node_id": self.node_id,
                "mutation": mutation,
                "min_rank": self.min_rank,
                "max_rank": self.max_rank
            }
        )

        # Use the unified service
        result = self.trials_service.query_trials(
            mutation=mutation,
            min_rank=self.min_rank,
            max_rank=self.max_rank,
            custom_timeout=self.timeout
        )

        study_count = len(result.get("studies", []))
        has_error = "error" in result

        logger.info(
            f"Query completed for mutation {mutation}: {study_count} studies found",
            extra={
                "action": "query_trials_exec_complete",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": study_count,
                "has_error": has_error
            }
        )

        return result

    async def aexec(self, prep_result: str) -> dict[str, Any]:
        """
        Query clinical trials for the mutation (async).

        Args:
            prep_result: Mutation string from prep

        Returns:
            Clinical trials query results
        """
        mutation = prep_result

        logger.info(
            f"Async querying trials for mutation: {mutation}",
            extra={
                "action": "query_trials_aexec_start",
                "node_id": self.node_id,
                "mutation": mutation,
                "min_rank": self.min_rank,
                "max_rank": self.max_rank
            }
        )

        # Use the unified service in async mode
        result = await self.trials_service.aquery_trials(
            mutation=mutation,
            min_rank=self.min_rank,
            max_rank=self.max_rank
        )

        study_count = len(result.get("studies", []))
        has_error = "error" in result

        logger.info(
            f"Async query completed for mutation {mutation}: {study_count} studies found",
            extra={
                "action": "query_trials_aexec_complete",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": study_count,
                "has_error": has_error
            }
        )

        return result

    def post(
        self,
        shared: dict[str, Any],
        prep_result: str,
        exec_result: dict[str, Any]
    ) -> str | None:
        """
        Store results in shared context and determine next node.

        Args:
            shared: Shared context
            prep_result: Mutation string
            exec_result: Query results

        Returns:
            Next node ID or None
        """
        # Store both the raw result and extracted studies
        shared["trials_data"] = exec_result
        shared["studies"] = exec_result.get("studies", [])

        # Store mutation for reference
        shared["queried_mutation"] = prep_result

        # Check for errors
        if "error" in exec_result:
            shared["query_error"] = exec_result["error"]
            logger.warning(
                f"Query error stored: {exec_result['error']}",
                extra={
                    "action": "query_trials_post_error",
                    "node_id": self.node_id,
                    "mutation": prep_result,
                    "error": exec_result["error"]
                }
            )

        return self.get_next_node_id(exec_result)


class SummarizeTrialsNode(UnifiedNode[list[dict[str, Any]], str]):
    """
    Unified node for summarizing clinical trials using LLM.

    This node replaces both SummarizeTrialsNode (sync) and AsyncSummarizeTrialsNode (async)
    by using the unified LLMService underneath.
    """

    def __init__(
        self,
        async_mode: bool | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs
    ):
        """
        Initialize the summarize trials node.

        Args:
            async_mode: Force sync/async mode
            model: LLM model to use
            max_tokens: Maximum tokens for summary
            **kwargs: Additional arguments for base class
        """
        super().__init__(async_mode=async_mode, **kwargs)
        self.model = model
        self.max_tokens = max_tokens

        # Initialize the LLM service with the appropriate mode
        detected_async = self._detect_async_mode()
        self.llm_service = LLMService(
            async_mode=detected_async,
            model=model,
            max_tokens=max_tokens
        )

        logger.info(
            f"Initialized SummarizeTrialsNode in {'async' if detected_async else 'sync'} mode",
            extra={
                "action": "summarize_trials_node_initialized",
                "node_id": self.node_id,
                "async_mode": detected_async,
                "model": model,
                "max_tokens": max_tokens
            }
        )

    def prep(self, shared: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract studies data from shared context.

        Args:
            shared: Shared context containing studies data

        Returns:
            List of studies to summarize
        """
        studies = shared.get("studies", [])
        mutation = shared.get("mutation", "unknown mutation")

        if not studies:
            logger.warning(
                "No studies found for summarization",
                extra={
                    "action": "summarize_trials_prep_empty",
                    "node_id": self.node_id,
                    "mutation": mutation
                }
            )

        logger.debug(
            f"Prepared {len(studies)} studies for summarization",
            extra={
                "action": "summarize_trials_prep",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": len(studies)
            }
        )

        return studies

    def _build_summarization_prompt(self, studies: list[dict[str, Any]], mutation: str) -> str:
        """
        Build the prompt for LLM summarization.

        Args:
            studies: List of study data
            mutation: Mutation being queried

        Returns:
            Formatted prompt for the LLM
        """
        if not studies:
            return f"No clinical trials were found for the mutation {mutation}. Please provide a brief explanation of what this means and suggest alternative approaches for finding relevant trials."

        # Build a structured prompt with study information
        prompt_parts = [
            f"Please summarize the following clinical trials for the genetic mutation {mutation}.",
            f"Found {len(studies)} clinical trials:",
            ""
        ]

        for i, study in enumerate(studies[:10], 1):  # Limit to first 10 studies
            try:
                protocol = study.get("protocolSection", {})
                identification = protocol.get("identificationModule", {})
                status = protocol.get("statusModule", {})
                design = protocol.get("designModule", {})

                nct_id = identification.get("nctId", "Unknown ID")
                title = identification.get("briefTitle", "No title available")
                overall_status = status.get("overallStatus", "Unknown status")
                phases = design.get("phases", [])

                prompt_parts.append(f"{i}. **{nct_id}**: {title}")
                prompt_parts.append(f"   - Status: {overall_status}")
                if phases:
                    prompt_parts.append(f"   - Phase: {', '.join(phases)}")
                prompt_parts.append("")

            except Exception as e:
                logger.warning(f"Failed to process study {i}: {str(e)}")
                prompt_parts.append(f"{i}. Study data incomplete")
                prompt_parts.append("")

        prompt_parts.extend([
            "Please provide:",
            "1. A brief overview of the trials",
            "2. Key information about trial phases and status",
            "3. Any notable patterns or insights",
            "4. Guidance for patients or researchers interested in these trials",
            "",
            "Format the response in clear, readable markdown."
        ])

        return "\n".join(prompt_parts)

    def exec(self, prep_result: list[dict[str, Any]]) -> str:
        """
        Generate summary using LLM (sync).

        Args:
            prep_result: List of studies from prep

        Returns:
            Generated summary text
        """
        studies = prep_result

        # Get mutation from the service's context (we'll need to pass this through shared context)
        # For now, we'll use a placeholder - this will be fixed in post method
        mutation = "the specified mutation"

        logger.info(
            f"Generating summary for {len(studies)} studies",
            extra={
                "action": "summarize_trials_exec_start",
                "node_id": self.node_id,
                "study_count": len(studies)
            }
        )

        # Build prompt
        prompt = self._build_summarization_prompt(studies, mutation)

        # Generate summary using LLM service
        summary = self.llm_service.call_llm(prompt)

        logger.info(
            f"Summary generated: {len(summary)} characters",
            extra={
                "action": "summarize_trials_exec_complete",
                "node_id": self.node_id,
                "summary_length": len(summary),
                "study_count": len(studies)
            }
        )

        return summary

    async def aexec(self, prep_result: list[dict[str, Any]]) -> str:
        """
        Generate summary using LLM (async).

        Args:
            prep_result: List of studies from prep

        Returns:
            Generated summary text
        """
        studies = prep_result

        # Get mutation from the service's context (we'll need to pass this through shared context)
        mutation = "the specified mutation"

        logger.info(
            f"Async generating summary for {len(studies)} studies",
            extra={
                "action": "summarize_trials_aexec_start",
                "node_id": self.node_id,
                "study_count": len(studies)
            }
        )

        # Build prompt
        prompt = self._build_summarization_prompt(studies, mutation)

        # Generate summary using LLM service
        summary = await self.llm_service.acall_llm(prompt)

        logger.info(
            f"Async summary generated: {len(summary)} characters",
            extra={
                "action": "summarize_trials_aexec_complete",
                "node_id": self.node_id,
                "summary_length": len(summary),
                "study_count": len(studies)
            }
        )

        return summary

    def prep(self, shared: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract studies and store mutation reference for later use.

        Args:
            shared: Shared context containing studies data

        Returns:
            List of studies to summarize
        """
        studies = shared.get("studies", [])
        mutation = shared.get("mutation", "unknown mutation")

        # Store mutation for use in exec method
        self._current_mutation = mutation

        if not studies:
            logger.warning(
                f"No studies found for summarization of {mutation}",
                extra={
                    "action": "summarize_trials_prep_empty",
                    "node_id": self.node_id,
                    "mutation": mutation
                }
            )

        logger.debug(
            f"Prepared {len(studies)} studies for summarization of {mutation}",
            extra={
                "action": "summarize_trials_prep",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": len(studies)
            }
        )

        return studies

    def exec(self, prep_result: list[dict[str, Any]]) -> str:
        """Generate summary using LLM (sync) - updated to use stored mutation."""
        studies = prep_result
        mutation = getattr(self, '_current_mutation', 'the specified mutation')

        logger.info(
            f"Generating summary for {len(studies)} studies for {mutation}",
            extra={
                "action": "summarize_trials_exec_start",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": len(studies)
            }
        )

        prompt = self._build_summarization_prompt(studies, mutation)
        summary = self.llm_service.call_llm(prompt)

        logger.info(
            f"Summary generated for {mutation}: {len(summary)} characters",
            extra={
                "action": "summarize_trials_exec_complete",
                "node_id": self.node_id,
                "mutation": mutation,
                "summary_length": len(summary),
                "study_count": len(studies)
            }
        )

        return summary

    async def aexec(self, prep_result: list[dict[str, Any]]) -> str:
        """Generate summary using LLM (async) - updated to use stored mutation."""
        studies = prep_result
        mutation = getattr(self, '_current_mutation', 'the specified mutation')

        logger.info(
            f"Async generating summary for {len(studies)} studies for {mutation}",
            extra={
                "action": "summarize_trials_aexec_start",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": len(studies)
            }
        )

        prompt = self._build_summarization_prompt(studies, mutation)
        summary = await self.llm_service.acall_llm(prompt)

        logger.info(
            f"Async summary generated for {mutation}: {len(summary)} characters",
            extra={
                "action": "summarize_trials_aexec_complete",
                "node_id": self.node_id,
                "mutation": mutation,
                "summary_length": len(summary),
                "study_count": len(studies)
            }
        )

        return summary

    def post(
        self,
        shared: dict[str, Any],
        prep_result: list[dict[str, Any]],
        exec_result: str
    ) -> str | None:
        """
        Store summary in shared context.

        Args:
            shared: Shared context
            prep_result: Studies that were summarized
            exec_result: Generated summary

        Returns:
            Next node ID or None
        """
        # Store the summary
        shared["summary"] = exec_result

        mutation = shared.get("mutation", "unknown")
        study_count = len(prep_result)

        logger.info(
            f"Summary stored for {mutation}: {study_count} studies, {len(exec_result)} characters",
            extra={
                "action": "summarize_trials_post",
                "node_id": self.node_id,
                "mutation": mutation,
                "study_count": study_count,
                "summary_length": len(exec_result)
            }
        )

        return self.get_next_node_id(exec_result)


class BatchQueryTrialsNode(UnifiedBatchNode[str, dict[str, Any]]):
    """
    Unified batch node for querying multiple mutations concurrently.

    This node can process multiple mutations either sequentially (sync mode)
    or concurrently (async mode) using the unified ClinicalTrialsService.
    """

    def __init__(
        self,
        async_mode: bool | None = None,
        min_rank: int = 1,
        max_rank: int = 10,
        max_concurrent: int = 5,
        **kwargs
    ):
        """
        Initialize the batch query trials node.

        Args:
            async_mode: Force sync/async mode
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            max_concurrent: Maximum concurrent queries in async mode
            **kwargs: Additional arguments for base class
        """
        super().__init__(async_mode=async_mode, max_concurrent=max_concurrent, **kwargs)
        self.min_rank = min_rank
        self.max_rank = max_rank

        # Initialize the service with the appropriate mode
        detected_async = self._detect_async_mode()
        self.trials_service = ClinicalTrialsService(async_mode=detected_async)

        logger.info(
            f"Initialized BatchQueryTrialsNode in {'async' if detected_async else 'sync'} mode",
            extra={
                "action": "batch_query_trials_node_initialized",
                "node_id": self.node_id,
                "async_mode": detected_async,
                "min_rank": min_rank,
                "max_rank": max_rank,
                "max_concurrent": max_concurrent
            }
        )

    def prep(self, shared: dict[str, Any]) -> list[str]:
        """
        Extract list of mutations from shared context.

        Args:
            shared: Shared context containing mutations list

        Returns:
            List of mutations to query
        """
        mutations = shared.get("mutations", [])
        if not mutations:
            # Fallback to single mutation
            single_mutation = shared.get("mutation")
            if single_mutation:
                mutations = [single_mutation]

        if not mutations:
            raise ValueError("No mutations found in shared context")

        logger.info(
            f"Prepared {len(mutations)} mutations for batch query",
            extra={
                "action": "batch_query_trials_prep",
                "node_id": self.node_id,
                "mutation_count": len(mutations),
                "mutations": mutations[:5]  # Log first 5 mutations
            }
        )

        return mutations

    def exec_single(self, mutation: str) -> dict[str, Any]:
        """
        Query clinical trials for a single mutation.

        Args:
            mutation: Mutation to query

        Returns:
            Query results for the mutation
        """
        logger.debug(f"Querying single mutation: {mutation}")

        result = self.trials_service.query_trials(
            mutation=mutation,
            min_rank=self.min_rank,
            max_rank=self.max_rank
        )

        # Add mutation identifier to result
        result["mutation"] = mutation
        return result

    async def aexec_single(self, mutation: str) -> dict[str, Any]:
        """
        Async query clinical trials for a single mutation.

        Args:
            mutation: Mutation to query

        Returns:
            Query results for the mutation
        """
        logger.debug(f"Async querying single mutation: {mutation}")

        result = await self.trials_service.aquery_trials(
            mutation=mutation,
            min_rank=self.min_rank,
            max_rank=self.max_rank
        )

        # Add mutation identifier to result
        result["mutation"] = mutation
        return result

    def post(
        self,
        shared: dict[str, Any],
        prep_result: list[str],
        exec_result: list[dict[str, Any]]
    ) -> str | None:
        """
        Store batch results in shared context.

        Args:
            shared: Shared context
            prep_result: List of mutations that were queried
            exec_result: List of query results

        Returns:
            Next node ID or None
        """
        # Store batch results
        shared["batch_results"] = exec_result
        shared["queried_mutations"] = prep_result

        # Aggregate statistics
        total_studies = 0
        successful_queries = 0
        errors = []

        for result in exec_result:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif "error" in result:
                errors.append(result["error"])
            else:
                successful_queries += 1
                total_studies += len(result.get("studies", []))

        # Store aggregated information
        shared["batch_stats"] = {
            "total_mutations": len(prep_result),
            "successful_queries": successful_queries,
            "total_studies": total_studies,
            "errors": errors
        }

        logger.info(
            f"Batch query completed: {successful_queries}/{len(prep_result)} successful, {total_studies} total studies",
            extra={
                "action": "batch_query_trials_post",
                "node_id": self.node_id,
                "total_mutations": len(prep_result),
                "successful_queries": successful_queries,
                "total_studies": total_studies,
                "error_count": len(errors)
            }
        )

        return self.get_next_node_id(exec_result)
