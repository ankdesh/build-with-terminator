import os
import io
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
import sys

def evaluate_correctness(input_text: str, actual_output: str, expected_output: str) -> dict:
    """
    Evaluates the actual output against the expected output using DeepEval's GEval configured for Correctness.
    Requires OPENAI_API_KEY environment variable.
    """
    # Standard evaluator setup using GEval
    try:
        metric = GEval(
            name="Correctness",
            criteria="Determine whether the actual output is factually correct based on the expected output.",
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
            threshold=0.5
        )
        
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            expected_output=expected_output
        )
        
        # Suppress prints from deepeval.measure if desired, but we leave it default
        metric.measure(test_case)
        return {
            "score": metric.score,
            "reason": metric.reason,
            "success": metric.is_successful()
        }
    except Exception as e:
        return {
            "score": None,
            "reason": f"Evaluation failed: {str(e)}",
            "success": False
        }
