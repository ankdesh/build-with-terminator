# Practical scenarios

Use these short guides to learn the studio, then demonstrate a useful result. Each guide has a question, numbered steps, result checks, and a short demonstration script.

## Choose a scenario

| Order | Scenario | What you will learn | Approximate time | Model needed? |
| --- | --- | --- | --- | --- |
| 1 | [Compare energy costs](01-energy-costs.md) | Inspect an existing pipeline and change a cost assumption | 10 minutes | No |
| 2 | [Build a small sales report](02-sales-report.md) | Turn a business rule into a dashboard through chat | 15–20 minutes | Yes, to create the stages |
| 3 | [Find a demand trend](03-demand-trend.md) | Compare daily values with a moving average | 15–20 minutes | Yes, to create stages and answer a question |
| 4 | [Reuse and hand over a report](04-reuse-and-handoff.md) | Run the sales report on new data and recover from an invalid file | 10 minutes; Windows export adds setup time | No, after scenario 2 |

Start with scenario 1. Use a new project for scenarios 2 and 3. Scenario 4 uses the project from scenario 2.

## Prepare once

1. Open a terminal in the repository root. Follow the [installation steps](../../README.md#start-the-linux-builder) if dependencies are not installed.
2. Activate the project's Python environment, then start the builder:

   ```bash
   source .venv/bin/activate
   python launcher.py
   ```

3. Use the Builder URL printed in the terminal. Keep the terminal open while you use the live dashboards.
4. For scenarios 2 and 3, check that `config.json` names your model endpoint and model. Set `OPENAI_API_KEY` in the launch environment before starting the builder. See the [model setup notes](../../README.md#start-the-linux-builder). Scenario 1 works without model credentials.
5. Use a desktop browser window. The builder needs at least 1100 CSS pixels of width; the dashboard needs at least 1000.

No data download is required. The sales CSVs in [data](data/) are synthetic examples. The demand example uses a CSV already in [tutorials/data](../../tutorials/data/). Its source and licence are recorded in [the tutorial attribution file](../../tutorials/ATTRIBUTION.txt).

## Use chat and Run

- Before you paste a prompt that creates a complete report, set the chat context to **Project**. If a stage is selected, use the **Project** button above the composer.
- Read the proposed changes. Select **Apply** to save the stages. Then select **Run** in the top bar to calculate results.
- **Apply** on a chat review saves an edit. **Apply controls** in a dashboard runs the saved calculations with your selected values.
- The builder is where you design the report. **Open dashboard** opens a separate page where a report user can change controls and upload a CSV.

The prompts specify small reports. Generated code and wording can vary. Compare your results with the checks before you demonstrate the report. The numeric checks were calculated from the supplied CSVs; these new prompts have not been validated through a live model session.

## If a step fails

| Symptom | Next action |
| --- | --- |
| Chat cannot reach the model | Check the endpoint and launch environment. Restart the builder after a configuration change. |
| The review says the workspace changed | Send the prompt again to get a fresh review. |
| Run fails | Open **Run output** and read the error. In Project chat, ask: `Fix the latest failed run using its logs. Keep the requested business rules. Save the repair; I will select Run.` Review, Apply, and Run again. |
| Run succeeds but a number is wrong | State the expected number and business rule in chat. Review the proposed calculation change, then Run again. |
| The dashboard says calculation changes are pending | Return to the builder and select **Run**. |

## Prepare a short demonstration

Use scenarios 2 and 4 for one continuous demonstration:

1. Show the ten input rows and state the sales rule.
2. Show the 800.00 sales total and the three excluded lines.
3. Apply a 10% discount and show 720.00.
4. Upload the next month's file and show 500.00 with the saved report.
5. Upload the file with a missing price column. Show the error and the retained 500.00 result.

Build and check the project before the demonstration. Keep chat creation as a separate part if the audience wants to see how you made the report.

For broader examples, open the existing [guided tutorials](../../tutorials/index.html).
