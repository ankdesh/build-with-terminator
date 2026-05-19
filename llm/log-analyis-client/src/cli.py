import argparse
import asyncio
import os
import sys
import yaml

from orchestrator import Orchestrator

def parse_yaml_workflow(file_path: str) -> list[dict]:
    """Parse a YAML workflow trace and validate schema."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Workflow file not found: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            trace = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file: {e}")
            
    if not isinstance(trace, list):
        raise ValueError("Workflow trace must be a YAML list of instructions.")
        
    for idx, instruction in enumerate(trace):
        if not isinstance(instruction, dict):
            raise ValueError(f"Instruction at index {idx} must be a dictionary.")
        if "action" not in instruction:
            raise ValueError(f"Instruction at index {idx} missing required key: 'action'")
        if "executor" not in instruction:
            raise ValueError(f"Instruction at index {idx} missing required key: 'executor'")
            
    return trace

async def handle_execute(args):
    workflow_path = args.workflow
    log_path = args.log
    
    try:
        instructions = parse_yaml_workflow(workflow_path)
    except Exception as e:
        print(f"[!] Error parsing workflow: {e}", file=sys.stderr)
        sys.exit(1)
        
    orchestrator = Orchestrator(log_path)
    await orchestrator.start()
    
    for instruction in instructions:
        await orchestrator.send_instruction(instruction)
        
    await orchestrator.stop()

async def handle_analysis(args):
    request_str = args.request
    log_path = args.log
    
    print(f"[*] Analysis Mode (Placeholder)")
    print(f"[*] Request: '{request_str}'")
    print(f"[*] Target Log: {log_path}")
    print("[*] Note: LLM Planner integration will be implemented in a future change.")
    print("[*] Exiting analysis mode.")

def main():
    parser = argparse.ArgumentParser(description="Log Analysis Client CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # execute subparser
    execute_parser = subparsers.add_parser("execute", help="Execute a predefined YAML workflow trace")
    execute_parser.add_argument("--workflow", required=True, help="Path to the YAML workflow file")
    execute_parser.add_argument("--log", required=True, help="Path to the target log file")
    
    # analysis subparser
    analysis_parser = subparsers.add_parser("analysis", help="Generate a workflow trace using LLM Planner (placeholder)")
    analysis_parser.add_argument("--request", required=True, help="Text request for the LLM Planner")
    analysis_parser.add_argument("--log", required=True, help="Path to the target log file")
    
    args = parser.parse_args()
    
    if args.command == "execute":
        asyncio.run(handle_execute(args))
    elif args.command == "analysis":
        asyncio.run(handle_analysis(args))

if __name__ == "__main__":
    main()
