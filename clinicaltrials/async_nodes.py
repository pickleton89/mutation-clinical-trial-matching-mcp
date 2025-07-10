"""
Async implementation of clinical trials nodes using the PocketFlow pattern.
"""

import logging
from typing import Any

from clinicaltrials.async_query import query_clinical_trials_async, query_multiple_mutations_async
from utils.async_call_llm import call_llm_async
from utils.node import AsyncBatchNode, AsyncNode

logger = logging.getLogger(__name__)


class AsyncQueryTrialsNode(AsyncNode):
    """
    Async node that queries clinicaltrials.gov for trials matching a mutation.
    """

    def __init__(self):
        super().__init__()

    async def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        """
        Extract mutation from shared context.

        Args:
            shared: Shared context containing mutation information

        Returns:
            Dictionary containing mutation for the exec phase
        """
        mutation = shared.get("mutation")
        if not mutation:
            raise ValueError("Mutation not found in shared context")

        logger.info(f"Async querying trials for mutation: {mutation}", extra={
            "mutation": mutation,
            "node": self.__class__.__name__,
            "action": "prep"
        })

        return {
            "mutation": mutation,
            "min_rank": shared.get("min_rank", 1),
            "max_rank": shared.get("max_rank", 10),
            "timeout": shared.get("timeout", 10)
        }

    async def exec(self, prep_result: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the async clinical trials query.

        Args:
            prep_result: Result from prep phase containing mutation

        Returns:
            Dictionary containing the API response
        """
        mutation = prep_result["mutation"]
        min_rank = prep_result.get("min_rank", 1)
        max_rank = prep_result.get("max_rank", 10)
        timeout = prep_result.get("timeout", 10)

        logger.info(f"Async executing query for mutation: {mutation}", extra={
            "mutation": mutation,
            "min_rank": min_rank,
            "max_rank": max_rank,
            "timeout": timeout,
            "node": self.__class__.__name__,
            "action": "exec"
        })

        # Query clinical trials asynchronously
        result = await query_clinical_trials_async(
            mutation=mutation,
            min_rank=min_rank,
            max_rank=max_rank,
            timeout=timeout
        )

        return result

    async def post(self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: dict[str, Any]) -> str | None:
        """
        Update shared context with query results.

        Args:
            shared: Shared context
            prep_result: Result from prep phase
            exec_result: Result from exec phase

        Returns:
            Next node ID or None if this is the last node
        """
        mutation = prep_result["mutation"]

        # Update shared context with results
        shared["trials_data"] = exec_result
        shared["studies"] = exec_result.get("studies", [])

        study_count = len(shared["studies"])
        logger.info(f"Async query completed for {mutation}: {study_count} studies found", extra={
            "mutation": mutation,
            "study_count": study_count,
            "node": self.__class__.__name__,
            "action": "post"
        })

        # Return next node ID using new chaining logic
        return self.get_next_node_id()


class AsyncBatchQueryTrialsNode(AsyncBatchNode):
    """
    Async batch node that queries clinical trials for multiple mutations concurrently.
    """

    def __init__(self):
        super().__init__()

    async def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        """
        Extract mutations from shared context.

        Args:
            shared: Shared context containing mutations information

        Returns:
            Dictionary containing mutations for the exec phase
        """
        mutations = shared.get("mutations", [])
        if not mutations:
            raise ValueError("Mutations not found in shared context")

        logger.info(f"Async batch querying trials for {len(mutations)} mutations", extra={
            "mutations": mutations,
            "batch_size": len(mutations),
            "node": self.__class__.__name__,
            "action": "prep"
        })

        return {
            "mutations": mutations,
            "min_rank": shared.get("min_rank", 1),
            "max_rank": shared.get("max_rank", 10),
            "timeout": shared.get("timeout", 10),
            "max_concurrent": shared.get("max_concurrent", 5)
        }

    async def exec(self, prep_result: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the async batch clinical trials query.

        Args:
            prep_result: Result from prep phase containing mutations

        Returns:
            Dictionary containing the batch API response
        """
        mutations = prep_result["mutations"]
        min_rank = prep_result.get("min_rank", 1)
        max_rank = prep_result.get("max_rank", 10)
        timeout = prep_result.get("timeout", 10)
        max_concurrent = prep_result.get("max_concurrent", 5)

        logger.info(f"Async batch executing query for {len(mutations)} mutations", extra={
            "mutations": mutations,
            "batch_size": len(mutations),
            "min_rank": min_rank,
            "max_rank": max_rank,
            "timeout": timeout,
            "max_concurrent": max_concurrent,
            "node": self.__class__.__name__,
            "action": "exec"
        })

        # Query clinical trials for multiple mutations concurrently
        results = await query_multiple_mutations_async(
            mutations=mutations,
            min_rank=min_rank,
            max_rank=max_rank,
            timeout=timeout,
            max_concurrent=max_concurrent
        )

        return results

    async def post(self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: dict[str, Any]) -> str | None:
        """
        Update shared context with batch query results.

        Args:
            shared: Shared context
            prep_result: Result from prep phase
            exec_result: Result from exec phase

        Returns:
            Next node ID or None if this is the last node
        """
        mutations = prep_result["mutations"]

        # Update shared context with results
        shared["batch_trials_data"] = exec_result

        # Aggregate studies from all mutations
        all_studies = []
        for mutation, result in exec_result.items():
            studies = result.get("studies", [])
            # Add mutation info to each study
            for study in studies:
                study["source_mutation"] = mutation
            all_studies.extend(studies)

        shared["studies"] = all_studies

        total_studies = len(all_studies)
        successful_mutations = sum(1 for result in exec_result.values() if "error" not in result)

        logger.info(f"Async batch query completed: {successful_mutations}/{len(mutations)} mutations, {total_studies} total studies", extra={
            "mutations": mutations,
            "batch_size": len(mutations),
            "successful_mutations": successful_mutations,
            "total_studies": total_studies,
            "node": self.__class__.__name__,
            "action": "post"
        })

        # Return next node ID using new chaining logic
        return self.get_next_node_id()


class AsyncSummarizeTrialsNode(AsyncNode):
    """
    Async node that summarizes clinical trials using LLM.
    """

    def __init__(self):
        super().__init__()

    async def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        """
        Extract studies from shared context.

        Args:
            shared: Shared context containing studies information

        Returns:
            Dictionary containing studies for the exec phase
        """
        studies = shared.get("studies", [])
        mutation = shared.get("mutation", "unknown")

        if not studies:
            logger.warning("No studies found for summarization", extra={
                "mutation": mutation,
                "node": self.__class__.__name__,
                "action": "prep"
            })

        logger.info(f"Async preparing to summarize {len(studies)} studies for mutation: {mutation}", extra={
            "mutation": mutation,
            "study_count": len(studies),
            "node": self.__class__.__name__,
            "action": "prep"
        })

        return {
            "studies": studies,
            "mutation": mutation
        }

    async def exec(self, prep_result: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the async summarization using LLM.

        Args:
            prep_result: Result from prep phase containing studies

        Returns:
            Dictionary containing the summary
        """
        studies = prep_result["studies"]
        mutation = prep_result["mutation"]

        if not studies:
            return {"summary": f"No clinical trials found for mutation: {mutation}"}

        logger.info(f"Async executing summarization for {len(studies)} studies", extra={
            "mutation": mutation,
            "study_count": len(studies),
            "node": self.__class__.__name__,
            "action": "exec"
        })

        # Create prompt for LLM
        prompt = f"""Please summarize the following clinical trials for the mutation {mutation}:

Studies:
"""

        for i, study in enumerate(studies[:10], 1):  # Limit to first 10 studies
            title = study.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "Unknown Title")
            nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "Unknown ID")
            status = study.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", "Unknown Status")

            prompt += f"""
{i}. {title}
   NCT ID: {nct_id}
   Status: {status}
"""

        prompt += """

Please provide a concise summary in markdown format including:
1. Overview of available trials
2. Key findings about trial phases and status
3. Notable institutions or sponsors
4. Recommendations for patients

Keep the summary focused and actionable."""

        # Call LLM asynchronously
        summary = await call_llm_async(prompt)

        return {"summary": summary}

    async def post(self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: dict[str, Any]) -> str | None:
        """
        Update shared context with summary.

        Args:
            shared: Shared context
            prep_result: Result from prep phase
            exec_result: Result from exec phase

        Returns:
            Next node ID or None if this is the last node
        """
        mutation = prep_result["mutation"]
        summary = exec_result["summary"]

        # Update shared context with summary
        shared["summary"] = summary

        logger.info(f"Async summarization completed for mutation: {mutation}", extra={
            "mutation": mutation,
            "summary_length": len(summary),
            "node": self.__class__.__name__,
            "action": "post"
        })

        # This is typically the last node in the flow
        return None
