import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CSV_PATH = str(Path('docs/scenarios/data/sales_january.csv').resolve())

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 850})
        page = context.new_page()

        print("[Scenario 2] Step 1: Navigating to studio...")
        page.goto('http://127.0.0.1:8080')
        page.wait_for_load_state('networkidle')

        # 1. New project
        print("[Scenario 2] Creating New project...")
        page.locator('button[aria-label="New project"]').click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_01_new_project_created.png')

        # Rename project to 'Minimal sales report'
        print("[Scenario 2] Renaming project to 'Minimal sales report'...")
        page.locator('button.project-name-button').click()
        page.wait_for_timeout(500)
        name_input = page.locator('fieldset.settings-fields input').first
        name_input.fill('Minimal sales report')
        name_input.press('Tab')
        page.wait_for_timeout(500)
        page.locator('button:has-text("Done")').click()
        page.wait_for_timeout(1000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_02_project_renamed.png')

        # 2. Upload CSV in Data input
        print("[Scenario 2] Navigating to Data input...")
        page.locator('aside.studio-navigation nav button:has-text("Data input")').click()
        page.wait_for_timeout(1000)

        print("[Scenario 2] Uploading sales_january.csv...")
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(CSV_PATH)
        page.wait_for_timeout(3000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_03_csv_uploaded.png')

        # Business context
        print("[Scenario 2] Setting Business context...")
        b_context = (
            "Synthetic invoice-line data. All UnitPrice values use one common currency, CU. "
            "Country is a category, not a currency. A C prefix marks a cancelled invoice. "
            "A valid sale requires a non-cancelled invoice, Quantity > 0, and UnitPrice > 0. "
            "Report positive sales value, not profit or refund-adjusted net revenue. "
            "The discount scenario assumes unchanged quantities."
        )
        bc_textarea = page.locator('textarea.business-context')
        bc_textarea.fill(b_context)
        page.locator('header.studio-header').click()
        page.wait_for_timeout(1000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_04_business_context_saved.png')

        # 3. Chat prompt
        print("[Scenario 2] Opening Chat dock...")
        if page.locator('aside.studio-dock').count() == 0:
            page.locator('button[aria-label="Open side panel"]').click()
            page.wait_for_timeout(500)

        # Explicitly click Project context button if present
        proj_btn = page.locator('.chat-context button:has-text("Project")')
        if proj_btn.count() > 0 and proj_btn.is_visible():
            print("[Scenario 2] Switching chat context to Project...")
            proj_btn.click()
            page.wait_for_timeout(500)

        chat_label = page.locator('.chat-context span').first.text_content()
        print("[Scenario 2] Active chat context label:", chat_label)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_05_chat_project_context.png')

        prompt_text = """Create a minimal reusable sales dashboard from this CSV.

Read InvoiceNo and Country as text, InvoiceDate as datetime, Quantity as integer, and UnitPrice as number. All five columns are required for replacement files.

Use one Data cleaning stage that returns cleaned. Preserve every row and source column. Add is_valid_sale: InvoiceNo does not start with C (case-insensitive), Quantity > 0, and UnitPrice > 0. Do not deduplicate or fill missing prices with zero.

Add two root parameters: country, a select filter on Country in cleaned, default All/null; and discount_pct, a number with label Discount percent, default 0, minimum 0, maximum 30. Filters are controls, not widgets.

Use one Analysis stage taking cleaned. From the currently filtered rows, calculate valid_sales from is_valid_sale and add sales_value = Quantity * UnitPrice. Return exactly five outputs: sales_value (sum of valid sales), excluded_lines (count of invalid rows in the current country selection), scenario_sales_value (sales_value * (1 - discount_pct / 100)), country_totals (all valid sales grouped by Country, columns Country and sales_value, sorted by value descending), and sales_detail (all valid rows with their source columns and sales_value). Return scalar outputs as separate values. Declare parameters_used on the stages.

Create exactly five widgets: Sales value (metric, CU, two decimals), Excluded lines (metric), Scenario sales value (metric, CU, two decimals), Sales by country (standard bar chart bound to country_totals with Country on X and sales_value on Y), and Sales detail (full table bound to sales_detail). Discount affects only Scenario sales value. Keep the saved table complete.

Keep the original CSV unchanged. Save the stages for review; I will select Run."""

        print("[Scenario 2] Pasting prompt and sending to chat...")
        chat_input = page.locator('aside.studio-dock textarea')
        chat_input.fill(prompt_text)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_06_prompt_entered.png')
        
        send_btn = page.locator('aside.studio-dock button[aria-label="Send chat message"]')
        send_btn.click()

        print("[Scenario 2] Waiting for LLM review...")
        start_wait = time.time()
        apply_btn = page.locator('.chat-review button.primary:has-text("Apply")')
        while time.time() - start_wait < 120:
            if apply_btn.count() > 0 and apply_btn.is_visible():
                print(f"[Scenario 2] LLM review arrived in {int(time.time() - start_wait)}s!")
                break
            err = page.locator('.error-banner')
            if err.count() > 0 and err.is_visible():
                print("Chat error detected:", err.text_content())
                break
            time.sleep(2)
        
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_07_review_received.png')

        # Click Apply
        print("[Scenario 2] Applying proposed review...")
        apply_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_08_review_applied.png')

        # Select Run
        print("[Scenario 2] Clicking Run in top bar...")
        run_btn = page.locator('header.studio-header button.primary:has-text("Run")')
        run_btn.click()

        # Wait for run completion
        start_run = time.time()
        run_done = False
        while time.time() - start_run < 40:
            badge = page.locator('.workspace-toolbar .state-badge').text_content() or ''
            if 'Calculations up to date' in badge:
                run_done = True
                break
            time.sleep(1)
        print(f"[Scenario 2] Run completed in {int(time.time() - start_run)}s. Done: {run_done}")
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_09_run_completed.png')

        # Navigate to Data cleaning
        print("[Scenario 2] Checking Data cleaning stage...")
        page.locator('aside.studio-navigation nav button:has-text("Data cleaning")').click()
        page.wait_for_timeout(2000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_10_data_cleaning_stage.png')

        # Navigate to Visualization
        print("[Scenario 2] Checking Visualization stage...")
        page.locator('aside.studio-navigation nav button:has-text("Visualization")').click()
        page.wait_for_timeout(2000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_11_visualization_stage.png')

        vis_content = page.content()
        print("Sales value 800.00 in vis:", "800.00" in vis_content or "800" in vis_content)
        print("Excluded lines 3 in vis:", "3" in vis_content)
        print("India 530 in vis:", "530" in vis_content)
        print("UK 270 in vis:", "270" in vis_content)

        # Open Dashboard
        dash_link = page.locator('a:has-text("Open dashboard")')
        dash_url = dash_link.get_attribute('href')
        print("[Scenario 2] Dashboard URL:", dash_url)

        if dash_url:
            dash_page = context.new_page()
            dash_page.goto(dash_url)
            dash_page.wait_for_load_state('networkidle')
            dash_page.wait_for_timeout(2000)
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_12_dashboard_initial.png')

            # Open Filters and scenarios
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_13_dashboard_controls_open.png')

            # Set Discount percent to 10
            disc_input = dash_page.locator('label:has-text("Discount percent") input')
            if disc_input.count() > 0:
                disc_input.fill('10')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_14_discount_10_applied.png')

            d1_content = dash_page.content()
            print("Scenario sales 720.00:", "720.00" in d1_content or "720" in d1_content)
            print("Original sales 800.00 stays:", "800.00" in d1_content or "800" in d1_content)

            # Filter to India and Discount 10
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            c_select = dash_page.locator('label:has-text("Country") select, label:has-text("country") select')
            if c_select.count() > 0:
                c_select.select_option(label='India')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_15_india_discount_10.png')

            d2_content = dash_page.content()
            print("India sales 530.00:", "530.00" in d2_content or "530" in d2_content)
            print("India scenario sales 477.00:", "477.00" in d2_content or "477" in d2_content)
            print("India excluded lines 1:", "1" in d2_content)

            # Reset
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            if c_select.count() > 0:
                c_select.select_option(index=0)
            if disc_input.count() > 0:
                disc_input.fill('0')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_16_dashboard_reset.png')

        browser.close()

if __name__ == '__main__':
    run()
