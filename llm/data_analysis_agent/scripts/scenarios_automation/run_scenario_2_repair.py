import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SCREENSHOTS_DIR, ensure_temp_dirs

def run():
    ensure_temp_dirs()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 850})
        page = context.new_page()

        print("[Scenario 2 Repair] Navigating to studio...")
        page.goto('http://127.0.0.1:8080')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        # Select 'Minimal sales report' project if not already selected
        proj_select = page.locator('#project-select')
        current_val = proj_select.input_value()
        print("Current project select value:", current_val)
        
        # Check projects listed
        options = proj_select.locator('option').all_text_contents()
        print("Available projects:", options)
        for opt in options:
            if "Minimal sales report" in opt:
                proj_select.select_option(label=opt)
                break
        page.wait_for_timeout(2000)
        page.wait_for_load_state('networkidle')

        # Open Run output drawer to show the error
        print("[Scenario 2 Repair] Opening Run output drawer...")
        drawer_btn = page.locator('button.run-drawer-toggle')
        if drawer_btn.count() > 0:
            drawer_btn.click()
            page.wait_for_timeout(1000)
            page.screenshot(path=str(SCREENSHOTS_DIR / 's2_09a_run_error_drawer.png'))

        # Ensure Chat dock is open
        if page.locator('aside.studio-dock').count() == 0:
            page.locator('button[aria-label="Open side panel"]').click()
            page.wait_for_timeout(500)

        # Ensure Project context
        proj_btn = page.locator('.chat-context button:has-text("Project")')
        if proj_btn.count() > 0 and proj_btn.is_visible():
            print("[Scenario 2 Repair] Switching chat context to Project...")
            proj_btn.click()
            page.wait_for_timeout(500)

        # Send repair prompt
        repair_prompt = "Fix the latest failed run using its logs. Keep the requested business rules. Save the repair; I will select Run."
        print(f"[Scenario 2 Repair] Sending repair prompt: {repair_prompt}")
        chat_input = page.locator('aside.studio-dock textarea')
        chat_input.fill(repair_prompt)
        page.locator('aside.studio-dock button[aria-label="Send chat message"]').click()

        # Wait for repair review
        print("[Scenario 2 Repair] Waiting for repair review from LLM...")
        start_wait = time.time()
        apply_btn = page.locator('.chat-review button.primary:has-text("Apply")').last
        while time.time() - start_wait < 120:
            if apply_btn.count() > 0 and apply_btn.is_visible():
                print(f"[Scenario 2 Repair] Repair review arrived in {int(time.time() - start_wait)}s!")
                break
            time.sleep(2)

        page.screenshot(path=str(SCREENSHOTS_DIR / 's2_09b_repair_review_received.png'))

        # Click Apply
        print("[Scenario 2 Repair] Applying repair...")
        apply_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's2_09c_repair_applied.png'))

        # Select Run
        print("[Scenario 2 Repair] Clicking Run in top bar...")
        run_btn = page.locator('header.studio-header button.primary:has-text("Run")')
        run_btn.click()

        # Wait for run to succeed
        start_run = time.time()
        run_done = False
        while time.time() - start_run < 40:
            badge = page.locator('.workspace-toolbar .state-badge').text_content() or ''
            if 'Calculations up to date' in badge:
                run_done = True
                break
            time.sleep(1)
        print(f"[Scenario 2 Repair] Run completed. Succeeded: {run_done}")
        page.screenshot(path=str(SCREENSHOTS_DIR / 's2_09d_run_succeeded.png'))

        # Check Visualization
        print("[Scenario 2 Repair] Checking Visualization view...")
        page.locator('aside.studio-navigation nav button:has-text("Visualization")').click()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's2_10_visualization_view.png'))

        vis_content = page.content()
        print("Sales value 800.00:", "800.00" in vis_content or "800" in vis_content)
        print("Excluded lines 3:", "3" in vis_content)
        print("Scenario sales 800.00:", "800.00" in vis_content)
        print("India 530:", "530" in vis_content)
        print("UK 270:", "270" in vis_content)

        # Open Dashboard
        dash_link = page.locator('a:has-text("Open dashboard")')
        dash_url = dash_link.get_attribute('href')
        print("[Scenario 2 Repair] Dashboard URL:", dash_url)

        if dash_url:
            dash_page = context.new_page()
            dash_page.goto(dash_url)
            dash_page.wait_for_load_state('networkidle')
            dash_page.wait_for_timeout(2000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's2_11_dashboard_initial.png'))

            # Open Filters and scenarios
            print("[Scenario 2 Repair] Opening Filters and scenarios drawer...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's2_12_dashboard_controls_open.png'))

            # Set Discount percent to 10
            print("[Scenario 2 Repair] Setting Discount percent to 10...")
            disc_input = dash_page.locator('label:has-text("Discount percent") input')
            if disc_input.count() > 0:
                disc_input.fill('10')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's2_13_discount_10_applied.png'))

            d1_content = dash_page.content()
            print("Scenario sales 720.00:", "720.00" in d1_content or "720" in d1_content)
            print("Original sales 800.00 stays:", "800.00" in d1_content or "800" in d1_content)

            # Filter to India and Discount 10
            print("[Scenario 2 Repair] Selecting Country India and Discount 10...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            c_select = dash_page.locator('label:has-text("Country") select, label:has-text("country") select')
            if c_select.count() > 0:
                c_select.select_option(label='India')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's2_14_india_discount_10.png'))

            d2_content = dash_page.content()
            print("India sales 530.00:", "530.00" in d2_content or "530" in d2_content)
            print("India scenario sales 477.00:", "477.00" in d2_content or "477" in d2_content)
            print("India excluded lines 1:", "1" in d2_content)

            # Reset
            print("[Scenario 2 Repair] Resetting to All and 0...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            if c_select.count() > 0:
                c_select.select_option(index=0)
            if disc_input.count() > 0:
                disc_input.fill('0')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's2_15_dashboard_reset.png'))

        browser.close()

if __name__ == '__main__':
    run()
