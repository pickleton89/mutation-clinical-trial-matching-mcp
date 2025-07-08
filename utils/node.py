"""
Base Node classes for PocketFlow pattern implementation.

This module provides the core Node and BatchNode abstractions used in the PocketFlow pattern.
Each node has three main methods:
- prep: Prepare data from the shared context
- exec: Execute the main functionality
- post: Process results and update the shared context
"""

from typing import Any, Dict, List, Optional, TypeVar, Generic
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Input type
R = TypeVar('R')  # Result type


class Node(Generic[T, R]):
    """
    Base Node class for PocketFlow pattern.
    
    A Node processes a single input and produces a single output.
    """
    
    def prep(self, shared: Dict[str, Any]) -> T:
        """
        Prepare data from the shared context.
        
        Args:
            shared: The shared context dictionary
            
        Returns:
            Data to be processed by exec
        """
        raise NotImplementedError("prep method must be implemented by subclasses")
    
    def exec(self, prep_result: T) -> R:
        """
        Execute the main functionality of the node.
        
        Args:
            prep_result: Result from the prep method
            
        Returns:
            Result of the execution
        """
        raise NotImplementedError("exec method must be implemented by subclasses")
    
    def post(self, shared: Dict[str, Any], prep_result: T, exec_result: R) -> Optional[str]:
        """
        Process results and update the shared context.
        
        Args:
            shared: The shared context dictionary
            prep_result: Result from the prep method
            exec_result: Result from the exec method
            
        Returns:
            Optional next node ID or None
        """
        raise NotImplementedError("post method must be implemented by subclasses")
    
    def process(self, shared: Dict[str, Any]) -> Optional[str]:
        """
        Process the node by calling prep, exec, and post in sequence.
        
        Args:
            shared: The shared context dictionary
            
        Returns:
            Optional next node ID or None
        """
        try:
            prep_result = self.prep(shared)
            exec_result = self.exec(prep_result)
            return self.post(shared, prep_result, exec_result)
        except Exception as e:
            logger.error(f"Error in node processing: {e}")
            # Store error in shared context for upstream handling
            shared["error"] = str(e)
            shared["error_type"] = type(e).__name__
            return None


class BatchNode(Node[List[T], List[R]]):
    """
    Node for batch processing multiple items.
    
    A BatchNode processes a list of inputs and produces a list of outputs.
    The exec method is called for each item in the list.
    """
    
    def exec_single(self, item: T) -> R:
        """
        Execute for a single item in the batch.
        
        Args:
            item: A single item from the prep result list
            
        Returns:
            Result for this item
        """
        raise NotImplementedError("exec_single method must be implemented by subclasses")
    
    def exec(self, prep_result: List[T]) -> List[R]:
        """
        Execute for all items in the batch by calling exec_single for each.
        
        Args:
            prep_result: List of items from the prep method
            
        Returns:
            List of results from exec_single
        """
        return [self.exec_single(item) for item in prep_result]


class Flow:
    """
    Flow class to orchestrate execution of nodes.
    """
    
    def __init__(self, start: Node):
        """
        Initialize a flow with a starting node.
        
        Args:
            start: The starting node
        """
        self.start = start
        self.nodes = {}
    
    def add_node(self, node_id: str, node: Node):
        """
        Add a node to the flow.
        
        Args:
            node_id: ID for the node
            node: The node instance
        """
        self.nodes[node_id] = node
    
    def run(self, shared: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the flow starting from the start node.
        
        Args:
            shared: Initial shared context (will be created if None)
            
        Returns:
            The final shared context
        """
        if shared is None:
            shared = {}
        
        try:
            current_node = self.start
            next_node_id = current_node.process(shared)
            
            # Check if initial node had an error
            if "error" in shared:
                logger.error(f"Error in start node: {shared['error']}")
                return shared
            
            while next_node_id:
                if next_node_id not in self.nodes:
                    error_msg = f"Node with ID '{next_node_id}' not found in flow"
                    logger.error(error_msg)
                    shared["error"] = error_msg
                    shared["error_type"] = "NodeNotFoundError"
                    return shared
                
                current_node = self.nodes[next_node_id]
                next_node_id = current_node.process(shared)
                
                # Check if current node had an error
                if "error" in shared:
                    logger.error(f"Error in node '{next_node_id}': {shared['error']}")
                    return shared
            
            return shared
            
        except Exception as e:
            logger.error(f"Unexpected error in flow execution: {e}", exc_info=True)
            shared["error"] = str(e)
            shared["error_type"] = type(e).__name__
            return shared
