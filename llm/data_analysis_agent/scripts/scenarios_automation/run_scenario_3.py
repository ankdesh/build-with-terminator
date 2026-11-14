import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SCREENSHOTS_DIR, ensure_temp_dirs

CSV_PATH = str(Path('tutorials/data/bike_daily.csv').resolve())

def run():
    ensure_temp_dirs()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 850})
        page = context.new_page()

        print("[Scenario 3] Step 1: Navigating to studio...")
        page.goto('http://127.0.0.1:8080')
        page.wait_for_load_state('networkidle')

        # 1. New project
        print("[Scenario 3] Creating New project...")
        page.locator('button[aria-label="New project"]').click()
        page.wait_for_timeout(2000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_01_new_project_created.png'))

        # Rename project to 'Daily rental demand'
        print("[Scenario 3] Renaming project to 'Daily rental demand'...")
        page.locator('button.project-name-button').click()
        page.wait_for_timeout(500)
        name_input = page.locator('fieldset.settings-fields input').first
        name_input.fill('Daily rental demand')
        name_input.press('Tab')
        page.wait_for_timeout(500)
        page.locator('button:has-text("Done")').click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_02_project_renamed.png'))

        # 2. Upload CSV in Data input
        print("[Scenario 3] Navigating to Data input...")
        page.locator('aside.studio-navigation nav button:has-text("Data input")').click()
        page.wait_for_timeout(1000)

        print("[Scenario 3] Uploading bike_daily.csv...")
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(CSV_PATH)
        page.wait_for_timeout(3000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_03_csv_uploaded.png'))

        # Check profile
        content = page.content()
        print("Profile check 731 rows:", "731" in content)

        # Business context
        print("[Scenario 3] Setting Business context...")
        b_context = (
            "Historical daily bike rental data. dteday is the date. cnt is the total rental count for that day, "
            "equal to casual + registered. One row represents one day. Use the supplied observations to "
            "describe historical demand. A moving average summarizes observed values; it is not a forecast."
        )
        bc_textarea = page.locator('textarea.business-context')
        bc_textarea.fill(b_context)
        page.locator('header.studio-header').click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_04_business_context_saved.png'))

        # 3. Chat prompt
        print("[Scenario 3] Opening Chat dock...")
        if page.locator('aside.studio-dock').count() == 0:
            page.locator('button[aria-label="Open side panel"]').click()
            page.wait_for_timeout(500)

        # Explicitly switch chat context to Project
        proj_btn = page.locator('.chat-context button:has-text("Project")')
        if proj_btn.count() > 0 and proj_btn.is_visible():
            print("[Scenario 3] Switching chat context to Project...")
            proj_btn.click()
            page.wait_for_timeout(500)

        prompt_text = """Create a small daily rental demand dashboard.

Use one Data cleaning stage returning cleaned. Parse dteday as datetime, read cnt as integer, sort by dteday ascending, and add calendar_year from the parsed date. Retain all rows and source columns. Do not fill values or deduplicate.

Add a root select parameter calendar_year, label Calendar year, default All/null, choices 2011 and 2012 as numbers. It filters calendar_year in cleaned before Analysis. It is a control, not a widget.

Use one Analysis stage taking cleaned. After filtering and date sorting, calculate rolling_mean_7 = cnt.rolling(7, min_periods=1).mean(). This is a trailing average using the current day and up to six preceding days. Return exactly four outputs: days (row count), total_rentals (sum cnt), average_daily_rentals (mean cnt), and daily_demand (DataFrame with date formatted YYYY-MM-DD, cnt, and rolling_mean_7). Declare parameters_used on the stages.

Create exactly four widgets: Days (metric), Total rentals (metric), Average daily rentals (metric, two decimals), and Daily demand (standard line chart bound to daily_demand; date on X and cnt plus rolling_mean_7 on Y). Label rental units and distinguish the two series. Do not add forecasting, extra controls, or extra widgets.

Keep the original CSV unchanged. Save the stages for review; I will select Run."""

        print("[Scenario 3] Pasting prompt and sending to chat...")
        chat_input = page.locator('aside.studio-dock textarea')
        chat_input.fill(prompt_text)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_05_prompt_entered.png'))
        
        send_btn = page.locator('aside.studio-dock button[aria-label="Send chat message"]')
        send_btn.click()

        print("[Scenario 3] Waiting for LLM review...")
        start_wait = time.time()
        apply_btn = page.locator('.chat-review button.primary:has-text("Apply")').last
        applied = False
        while time.time() - start_wait < 120:
            if apply_btn.count() > 0 and apply_btn.is_visible() and not apply_btn.is_disabled():
                print(f"[Scenario 3] LLM review arrived in {int(time.time() - start_wait)}s!")
                page.screenshot(path=str(SCREENSHOTS_DIR / 's3_06_review_received.png'))
                apply_btn.click()
                applied = True
                break
            time.sleep(2)

        if not applied:
            print("[Scenario 3] ERROR: Apply button did not appear!")
            page.screenshot(path=str(SCREENSHOTS_DIR / 's3_06_error_review.png'))
            browser.close()
            return

        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_07_review_applied.png'))

        # Select Run
        print("[Scenario 3] Clicking Run in top bar...")
        run_btn = page.locator('header.studio-header button.primary:has-text("Run")')
        run_btn.click()

        # Wait for run completion
        start_run = time.time()
        run_done = False
        while time.time() - start_run < 50:
            badge = page.locator('.workspace-toolbar .state-badge').text_content() or ''
            if 'Calculations up to date' in badge:
                run_done = True
                break
            time.sleep(1)
        print(f"[Scenario 3] Run completed in {int(time.time() - start_run)}s. Done: {run_done}")
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_08_run_completed.png'))

        # If run failed, check logs and repair if needed
        if not run_done:
            print("[Scenario 3] Run failed or pending, checking run drawer...")
            drawer_btn = page.locator('button.run-drawer-toggle')
            if drawer_btn.count() > 0:
                drawer_btn.click()
                page.wait_for_timeout(1000)
                page.screenshot(path=str(SCREENSHOTS_DIR / 's3_08a_run_drawer_error.png'))
            
            # Send repair prompt
            print("[Scenario 3] Sending repair prompt...")
            chat_input.fill("Fix the latest failed run using its logs. Keep the requested business rules. Save the repair; I will select Run.")
            send_btn.click()
            
            # Wait for repair
            start_rep = time.time()
            rep_applied = False
            while time.time() - start_rep < 120:
                rep_apply = page.locator('.chat-review button.primary:has-text("Apply")').last
                if rep_apply.count() > 0 and rep_apply.is_visible() and not rep_apply.is_disabled():
                    rep_apply.click()
                    rep_applied = True
                    break
                time.sleep(2)
            
            if rep_applied:
                page.wait_for_timeout(2000)
                page.locator('header.studio-header button.primary:has-text("Run")').click()
                time.sleep(10)
                page.screenshot(path=str(SCREENSHOTS_DIR / 's3_08b_repaired_run.png'))

        # Navigate to Visualization
        print("[Scenario 3] Navigating to Visualization...")
        page.locator('aside.studio-navigation nav button:has-text("Visualization")').click()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_09_visualization_view.png'))

        vis_content = page.content()
        print("Visualization check Days 731:", "731" in vis_content)
        print("Visualization check Total rentals 3,292,679:", "3,292,679" in vis_content or "3292679" in vis_content)
        print("Visualization check Avg daily rentals 4,504.35:", "4,504.35" in vis_content or "4504.35" in vis_content)

        # Open Dashboard
        dash_link = page.locator('a:has-text("Open dashboard")')
        dash_url = dash_link.get_attribute('href')
        print("[Scenario 3] Dashboard URL:", dash_url)

        if dash_url:
            dash_page = context.new_page()
            dash_page.goto(dash_url)
            dash_page.wait_for_load_state('networkidle')
            dash_page.wait_for_timeout(2000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's3_10_dashboard_initial_all.png'))

            # Open Filters and scenarios
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's3_11_filters_open.png'))

            # Filter Calendar year to 2011
            print("[Scenario 3] Selecting Calendar year 2011...")
            year_select = dash_page.locator('label:has-text("Calendar year") select, label:has-text("calendar_year") select')
            if year_select.count() > 0:
                year_select.select_option(label='2011')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's3_12_dashboard_2011.png'))

            d2011_content = dash_page.content()
            print("2011 check Days 365:", "365" in d2011_content)
            print("2011 check Total 1,243,103:", "1,243,103" in d2011_content or "1243103" in d2011_content)
            print("2011 check Avg 3,405.76:", "3,405.76" in d2011_content or "3405.76" in d2011_content)

            # Filter Calendar year to 2012
            print("[Scenario 3] Selecting Calendar year 2012...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            if year_select.count() > 0:
                year_select.select_option(label='2012')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's3_13_dashboard_2012.png'))

            d2012_content = dash_page.content()
            print("2012 check Days 366:", "366" in d2012_content)
            print("2012 check Total 2,049,576:", "2,049,576" in d2012_content or "2049576" in d2012_content)
            print("2012 check Avg 5,599.93:", "5,599.93" in d2012_content or "5599.93" in d2012_content)

            # Reset year to All
            print("[Scenario 3] Resetting year to All...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            if year_select.count() > 0:
                year_select.select_option(index=0)
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's3_14_dashboard_reset_all.png'))

        # 4. Ask a question about saved evidence in Builder
        print("[Scenario 3] Returning to Builder to ask evidence question...")
        page.bring_to_front()
        # Ensure project context
        proj_btn = page.locator('.chat-context button:has-text("Project")')
        if proj_btn.count() > 0 and proj_btn.is_visible():
            proj_btn.click()
            page.wait_for_timeout(500)

        q_prompt = (
            "Explain how Daily demand calculates its trailing 7-day average. "
            "Why is the first value equal to the first day's count? Use the saved calculation "
            "and run evidence. Answer only; do not edit the report or run new calculations."
        )
        print("[Scenario 3] Sending evidence explanation question to chat...")
        page.locator('aside.studio-dock textarea').fill(q_prompt)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_15_qa_prompt_entered.png'))
        page.locator('aside.studio-dock button[aria-label="Send chat message"]').click()

        # Wait for answer
        start_ans = time.time()
        ans_found = False
        while time.time() - start_ans < 60:
            messages = page.locator('.studio-message.assistant')
            if messages.count() > 0:
                last_msg = messages.last.text_content() or ''
                if "min_periods" in last_msg or "trailing" in last_msg or "average" in last_msg:
                    print(f"[Scenario 3] LLM explanation answer received in {int(time.time() - start_ans)}s!")
                    print("Answer excerpt:", last_msg[:200])
                    ans_found = True
                    break
            time.sleep(2)
        
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's3_16_qa_answer_received.png'))

        browser.close()

if __name__ == '__main__':
    run()
