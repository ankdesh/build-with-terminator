import asyncio
import os
import re
import yaml
from typing import Any, List, Dict

from orchestrator import Orchestrator
from utils.llm_client import execute_llm


class AnalysisAgent:
    def __init__(self, log_path: str, query: str, output_path: str = None):
        self.log_path = os.path.abspath(log_path)
        self.query = query
        self.output_path = output_path
        self.templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_templates")
        self.default_workflows_dir = ".workflows"
        os.makedirs(self.default_workflows_dir, exist_ok=True)
        self.orchestrator = None

    def _list_templates(self) -> List[Dict[str, Any]]:
        """Lists available workflow templates and parses them."""
        templates = []
        if not os.path.exists(self.templates_dir):
            return templates

        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.templates_dir, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        content = yaml.safe_load(f)
                        templates.append({
                            "name": filename,
                            "path": filepath,
                            "content": content
                        })
                except Exception as e:
                    print(f"[!] Warning: Failed to load template {filename}: {e}")
        return templates

    def _resolve_template(self, template: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Resolves template parameters such as {{ query }} and {{ log_file }}."""
        resolved = []
        for step in template:
            new_step = {}
            for k, v in step.items():
                if isinstance(v, str):
                    val = v.replace("{{ query }}", query)
                    val = val.replace("{{ log_file }}", self.log_path)
                    new_step[k] = val
                elif isinstance(v, dict):
                    new_step[k] = {
                        sk: (sv.replace("{{ query }}", query).replace("{{ log_file }}", self.log_path) if isinstance(sv, str) else sv)
                        for sk, sv in v.items()
                    }
                else:
                    new_step[k] = v
            resolved.append(new_step)
        return resolved

    async def run(self):
        """Runs the interactive conversational analysis loop."""
        print(f"\n[*] Starting Analysis Agent")
        print(f"[*] Target Log: {self.log_path}")
        print(f"[*] User Request: '{self.query}'")

        # 1. Load templates
        templates = self._list_templates()
        
        # 2. Let the LLM choose the best template or synthesize a custom plan
        print("[*] Selecting optimal workflow template...")
        selected_template_name, resolved_instructions = self._select_and_resolve_workflow(templates)

        if selected_template_name:
            print(f"[*] Selected Template: '{selected_template_name}'")
        else:
            print("[*] Synthesized custom workflow trace.")

        # 3. Start persistent Orchestrator
        self.orchestrator = Orchestrator(self.log_path)
        await self.orchestrator.start()

        conversational_history = []
        current_instructions = resolved_instructions

        try:
            while True:
                # Run instructions on the persistent Orchestrator
                print("\n[*] Executing candidate workflow...")
                results = []
                for instruction in current_instructions:
                    # Run on orchestrator
                    await self.orchestrator.send_instruction(instruction)
                
                await self.orchestrator.wait_until_idle()

                # Gather execution summary
                exec_summary = self._gather_execution_summary()
                print("\n" + "=" * 50)
                print(" ANALYSIS OUTCOME ")
                print("=" * 50)
                print(exec_summary)
                print("=" * 50)

                # Ask the user if it's correct
                print("\nAnalysis Agent> Does this look correct, or would you like to refine the query?")
                print("Analysis Agent> (Type 'y' or 'yes' to approve and save, or enter feedback to refine):")
                user_feedback = input("User> ").strip()

                if user_feedback.lower() in ("y", "yes"):
                    await self._save_resolved_trace(current_instructions)
                    break
                elif user_feedback.lower() in ("exit", "quit"):
                    print("[*] Aborting analysis mode.")
                    break
                else:
                    # User wants to refine the query or python code
                    print("[*] Processing feedback and regenerating plan...")
                    conversational_history.append({"user": user_feedback, "summary": exec_summary})
                    current_instructions = self._refine_workflow(current_instructions, conversational_history)

        finally:
            if self.orchestrator:
                await self.orchestrator.stop()

    def _select_and_resolve_workflow(self, templates: List[Dict[str, Any]]) -> (str, List[Dict[str, Any]]):
        """LLM decides whether to use a template or dynamically synthesize instructions."""
        templates_desc = ""
        for idx, t in enumerate(templates):
            templates_desc += f"\nTemplate {idx + 1}: Name={t['name']}\nContent:\n{yaml.dump(t['content'])}\n"

        prompt = f"""You are a log analysis planner. Your job is to select the most appropriate workflow template or dynamically synthesize a custom sequence of instructions to answer the user's query.

User Query: "{self.query}"

### Predefined Templates
{templates_desc}

### Available Actions and Executors
1. stats:
   - get_stats
2. template_extractor:
   - parse_templates (requires 'log_format' string)
   - get_templates (requires 'limit', 'sort_by', 'order')
   - get_parsed_info
3. cpp_scanner:
   - scan (requires 'pattern')
4. llm:
   - gen_pycode_fromtemplate (requires 'df_schema', 'templates', 'query')
5. python_runner:
   - execute_python (requires 'code' and optionally 'inputs')

### Rules
- Answer ONLY in the following format:
Best Template: <name_of_template_or_NONE>
Instructions:
```yaml
<list_of_instructions_resolved_with_placeholders>
```
- If a template fits, pick it and substitute `{{ query }}` with "{self.query}" in the output instructions.
- If no template fits, output 'Best Template: NONE' and dynamically synthesize the instructions under 'Instructions:'. Do not hardcode 'target_file' as the Orchestrator injects the global log path automatically.
"""
        response = execute_llm(prompt)
        
        best_template = "NONE"
        template_match = re.search(r"Best Template:\s*(\S+)", response, re.IGNORECASE)
        if template_match:
            best_template = template_match.group(1).strip()

        code_match = re.search(r"```yaml\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if code_match:
            instructions_str = code_match.group(1).strip()
        else:
            instructions_str = response.strip()

        try:
            instructions = yaml.safe_load(instructions_str)
            if not isinstance(instructions, list):
                raise ValueError("Parsed instructions is not a list")
            # Ensure placeholders are resolved
            instructions = self._resolve_template(instructions, self.query)
        except Exception:
            # Fallback to llm_analysis if failure
            print("[!] Warning: LLM failed to parse instructions, falling back to default llm_analysis template.")
            default_t = [t for t in templates if t["name"] == "llm_analysis.yaml"]
            if default_t:
                return "llm_analysis.yaml", self._resolve_template(default_t[0]["content"], self.query)
            return None, []

        return (None if best_template.upper() == "NONE" else best_template), instructions

    def _refine_workflow(self, current_instructions: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM refines the instructions based on conversational feedback."""
        history_desc = ""
        for idx, h in enumerate(history):
            history_desc += f"\nRound {idx + 1}:\nUser Feedback: {h['user']}\nExecution Outcome:\n{h['summary']}\n"

        prompt = f"""You are a log analysis planner. The execution of the previous workflow did not fully satisfy the user.
Your job is to refine the workflow instructions or generate updated python code parameters to address the user's feedback.

### User Request
"{self.query}"

### Conversational History & Feedback
{history_desc}

### Current Workflow
```yaml
{yaml.dump(current_instructions)}
```

### Refinement Instructions
- Adjust the python code query parameter, change grep patterns, or change stats fields based on feedback.
- Return ONLY the updated list of instructions in valid YAML format under ```yaml ... ``` blocks.
"""
        response = execute_llm(prompt)
        code_match = re.search(r"```yaml\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if code_match:
            instructions_str = code_match.group(1).strip()
        else:
            instructions_str = response.strip()

        try:
            instructions = yaml.safe_load(instructions_str)
            if isinstance(instructions, list):
                return instructions
        except Exception:
            pass
        return current_instructions

    def _gather_execution_summary(self) -> str:
        """Gathers key intermediate outputs from the Orchestrator's context."""
        summary = ""
        # 1. Check if RESULT exists
        if "RESULT" in self.orchestrator.context:
            summary += f"Final Result (from RESULT):\n{self.orchestrator.context['RESULT']}\n"
        
        # 2. Check for intermediate stdout / executor results
        for k, v in self.orchestrator.context.items():
            if k == "RESULT":
                continue
            if isinstance(v, dict):
                if "result" in v and v["result"] is not None:
                    summary += f"\n[{k}] result:\n{v['result']}\n"
                if v.get("stdout"):
                    summary += f"\n[{k}] stdout:\n{v['stdout']}\n"
                if v.get("stderr"):
                    summary += f"\n[{k}] error:\n{v['stderr']}\n"
        
        if not summary:
            summary = "No execution outputs found in context. Check if executors completed successfully."
        return summary

    async def _save_resolved_trace(self, current_instructions: List[Dict[str, Any]]):
        """Compiles the approved workflow trace, making it 100% deterministic."""
        print("[*] Compiling 100% deterministic workflow trace...")
        resolved_trace = []

        for step in current_instructions:
            action = step.get("action")
            executor = step.get("executor")

            if executor == "llm" and action == "gen_pycode_fromtemplate":
                # Convert this dynamic LLM step into a static python_runner action!
                output_key = step.get("output_key")
                # Retrieve the generated code from orchestrator context
                generated_result = self.orchestrator.context.get(output_key)
                if isinstance(generated_result, dict) and "code" in generated_result:
                    code = generated_result["code"]
                    print(f"[*] Embedding generated Python code block into saved trace.")
                else:
                    # Fallback code
                    code = "# Failed to retrieve code during analysis compilation."

                # We don't save the LLM executor step itself. Instead, the downstream
                # python_runner step is what executes it. Wait!
                # If the template had:
                # 1. gen_pycode_fromtemplate (llm) -> saved to output_key 'analysis_code'
                # 2. execute_python (python_runner) using '$analysis_code.code'
                #
                # In the compiled deterministic trace, we replace step 1 with a static assignment or
                # simply write step 2 with the code directly inline!
                # Let's write execute_python directly with the code inline!
                # This is extremely clean and eliminates the llm step entirely!
                continue
            
            elif executor == "python_runner" and action == "execute_python":
                # If code is referencing '$analysis_code.code', replace it with the actual statically generated code!
                code_ref = step.get("code")
                if isinstance(code_ref, str) and code_ref.startswith("$"):
                    parts = code_ref[1:].split(".")
                    # Resolve from context
                    current = self.orchestrator.context
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            current = None
                            break
                    
                    if current:
                        # Static code replacement!
                        step["code"] = current
                        print(f"[*] Inlined static python script inside trace.")

            # Append the resolved step (without target_file as orchestrator handles it globally)
            clean_step = {k: v for k, v in step.items() if k != "target_file"}
            resolved_trace.append(clean_step)

        # Generate a descriptive filename via LLM
        prompt = f"Given user query '{self.query}', suggest a short, descriptive filename in kebab-case with '.yaml' extension (e.g. 'hdfs-level-counts.yaml'). Output ONLY the filename."
        suggested_name = execute_llm(prompt).strip()
        # Clean any markdown or quotes
        suggested_name = re.sub(r'["\'`\s]', '', suggested_name)
        if not suggested_name.endswith(".yaml"):
            suggested_name += ".yaml"

        default_out = os.path.join(self.default_workflows_dir, suggested_name)
        
        target_path = self.output_path if self.output_path else default_out
        
        print(f"[*] Saving deterministic trace to: {target_path}")
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(resolved_trace, f, sort_keys=False)
            print(f"[✓] Trace successfully saved.")
        except Exception as e:
            print(f"[!] Error: Failed to save trace: {e}")
