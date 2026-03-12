import typer
import pandas as pd
from pathlib import Path
from agent import call_agent
from evaluator import evaluate_correctness
import sys

app = typer.Typer(help="CLI utility to test LLM application with DeepEval.")

@app.command()
def evaluate(
    input_file: Path = typer.Option(
        ..., "--input-file", "-i", 
        help="Path to the input CSV or XLS file", 
        exists=True
    ),
    output_file: Path = typer.Option(
        None, "--output-file", "-o", 
        help="Optional path to save the results. If not provided, overwrites the input file."
    )
):
    """
    Evaluate the input file containing 'Question' and 'Expected answer' columns.
    For each row, calls the dummy agent and evaluates the output via DeepEval.
    """
    typer.echo(f"Reading input file: {input_file}")
    
    try:
        if input_file.suffix.lower() == ".csv":
            df = pd.read_csv(input_file)
        elif input_file.suffix.lower() in [".xls", ".xlsx"]:
            df = pd.read_excel(input_file)
        else:
            typer.echo(f"Error: Unsupported file format {input_file.suffix}. Use CSV or XLS/XLSX.")
            raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error reading file: {e}")
        raise typer.Exit(code=1)
        
    required_columns = ["Question", "Expected answer"]
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        typer.echo(f"Error: Missing required columns: {', '.join(missing)}")
        raise typer.Exit(code=1)
            
    # Add new evaluation columns
    df["Actual Output"] = ""
    df["Correctness Score"] = None
    df["Correctness Reason"] = ""
    df["Eval Success"] = False
    
    total_rows = len(df)
    typer.echo(f"Found {total_rows} rows to evaluate...")
    
    with typer.progressbar(df.iterrows(), length=total_rows, label="Evaluating") as progress:
        for idx, row in progress:
            question = str(row["Question"])
            expected = str(row["Expected answer"])
            
            # 1. Call the dummy agent
            actual_output = call_agent(question)
            df.at[idx, "Actual Output"] = actual_output
            
            # 2. Evaluate using DeepEval
            eval_result = evaluate_correctness(
                input_text=question,
                actual_output=actual_output,
                expected_output=expected
            )
            
            # 3. Populate results
            df.at[idx, "Correctness Score"] = eval_result["score"]
            df.at[idx, "Correctness Reason"] = eval_result["reason"]
            df.at[idx, "Eval Success"] = eval_result["success"]
            
    # Save results
    save_path = output_file if output_file else input_file
    typer.echo(f"\nSaving results to: {save_path}")
    
    try:
        if save_path.suffix.lower() == ".csv":
            df.to_csv(save_path, index=False)
        elif save_path.suffix.lower() in [".xls", ".xlsx"]:
            df.to_excel(save_path, index=False)
    except Exception as e:
        typer.echo(f"Error saving file: {e}")
        raise typer.Exit(code=1)
        
    typer.echo("Done!")

if __name__ == "__main__":
    app()
