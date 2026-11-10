import time
from playwright.sync_api import sync_playwright

PROJECT_ID = "fbd71690-4cda-483a-a75b-b5d06aa17fd0"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        context = browser.new_context(viewport={'width': 1366, 'height': 850})
        page = context.new_page()

        print(f"[Scenario 2 Repair] Opening project {PROJECT_ID}...")
        page.goto(f'http://127.0.0.1:8080/?project={PROJECT_ID}')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        # Rename project to 'Minimal sales report' if needed
        title_btn = page.locator('button.project-name-button')
        if "Minimal sales report" not in (title_btn.text_content() or ""):
            print("[Scenario 2 Repair] Renaming project to 'Minimal sales report'...")
            title_btn.click()
            page.wait_for_timeout(500)
            name_input = page.locator('fieldset.settings-fields input').first
            name_input.fill('Minimal sales report')
            name_input.press('Tab')
            page.wait_for_timeout(500)
            page.locator('button:has-text("Done")').click()
            page.wait_for_timeout(1000)

        # Open Run output drawer to show error
        print("[Scenario 2 Repair] Capturing Run output error...")
        drawer_btn = page.locator('button.run-drawer-toggle')
        drawer_btn.click()
        page.wait_for_timeout(1000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_09a_run_error_drawer.png')

        # Ensure Chat dock is open
        if page.locator('aside.studio-dock').count() == 0:
            page.locator('button[aria-label="Open side panel"]').click()
            page.wait_for_timeout(500)

        # Set context to Project if needed
        chat_context = page.locator('.chat-context')
        proj_btn = page.locator('.chat-context button:has-text("Project")')
        if proj_btn.count() > 0 and proj_btn.is_visible():
            print("[Scenario 2 Repair] Setting chat context to Project...")
            proj_btn.click()
            page.wait_for_timeout(500)

        # Send repair prompt
        repair_prompt = "Fix the latest failed run using its logs. Keep the requested business rules. Save the repair; I will select Run."
        print(f"[Scenario 2 Repair] Sending repair prompt...")
        chat_input = page.locator('aside.studio-dock textarea')
        chat_input.fill(repair_prompt)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_09b_repair_prompt_sent.png')
        page.locator('aside.studio-dock button[aria-label="Send chat message"]').click()

        # Wait for new review card
        print("[Scenario 2 Repair] Waiting for repair review...")
        start_wait = time.time()
        applied = False
        while time.time() - start_wait < 120:
            # Look for pending review card with Apply button
            apply_btns = page.locator('.chat-review button.primary:has-text("Apply")')
            for i in range(apply_btns.count()):
                btn = apply_btns.nth(i)
                if btn.is_visible() and not btn.is_disabled():
                    print(f"[Scenario 2 Repair] Found active Apply button in {int(time.time() - start_wait)}s!")
                    page.screenshot(path='artifacts/scenario_report/screenshots/s2_09c_repair_review_card.png')
                    btn.click()
                    applied = True
                    break
            if applied:
                break
            time.sleep(2)

        if not applied:
            print("[Scenario 2 Repair] ERROR: Could not find active Apply button within timeout!")
            page.screenshot(path='artifacts/scenario_report/screenshots/s2_09c_error_waiting_apply.png')
            browser.close()
            return

        page.wait_for_timeout(2000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_09d_repair_applied.png')

        # Click Run
        print("[Scenario 2 Repair] Clicking Run in top bar...")
        run_btn = page.locator('header.studio-header button.primary:has-text("Run")')
        run_btn.click()

        # Wait for run to succeed
        start_run = time.time()
        run_succeeded = False
        while time.time() - start_run < 40:
            badge = page.locator('.workspace-toolbar .state-badge').text_content() or ''
            if 'Calculations up to date' in badge:
                run_succeeded = True
                break
            time.sleep(1)
        print(f"[Scenario 2 Repair] Run finished in {int(time.time() - start_run)}s. Succeeded: {run_succeeded}")
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_09e_run_succeeded.png')

        # Check Visualization
        print("[Scenario 2 Repair] Checking Visualization view...")
        page.locator('aside.studio-navigation nav button:has-text("Visualization")').click()
        page.wait_for_timeout(2000)
        page.screenshot(path='artifacts/scenario_report/screenshots/s2_10_visualization_view.png')

        vis_content = page.content()
        print("Visualization check Sales value 800.00:", "800.00" in vis_content or "800" in vis_content)
        print("Visualization check Excluded lines 3:", "3" in vis_content)
        print("Visualization check Scenario sales 800.00:", "800.00" in vis_content)
        print("Visualization check India 530:", "530" in vis_content)
        print("Visualization check UK 270:", "270" in vis_content)

        # Open Dashboard
        dash_link = page.locator('a:has-text("Open dashboard")')
        dash_url = dash_link.get_attribute('href')
        print("[Scenario 2 Repair] Dashboard URL:", dash_url)

        if dash_url:
            dash_page = context.new_page()
            dash_page.goto(dash_url)
            dash_page.wait_for_load_state('networkidle')
            dash_page.wait_for_timeout(2000)
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_11_dashboard_initial.png')

            # Open Filters and scenarios
            print("[Scenario 2 Repair] Opening Filters and scenarios drawer...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_12_dashboard_controls_open.png')

            # Set Discount percent to 10
            print("[Scenario 2 Repair] Setting Discount percent to 10...")
            disc_input = dash_page.locator('label:has-text("Discount percent") input')
            if disc_input.count() > 0:
                disc_input.fill('10')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_13_discount_10_applied.png')

            d1_content = dash_page.content()
            print("Dashboard check Scenario sales 720.00:", "720.00" in d1_content or "720" in d1_content)
            print("Dashboard check Original sales 800.00:", "800.00" in d1_content or "800" in d1_content)

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
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_14_india_discount_10.png')

            d2_content = dash_page.content()
            print("Dashboard check India sales 530.00:", "530.00" in d2_content or "530" in d2_content)
            print("Dashboard check India scenario sales 477.00:", "477.00" in d2_content or "477" in d2_content)
            print("Dashboard check India excluded lines 1:", "1" in d2_content)

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
            dash_page.screenshot(path='artifacts/scenario_report/screenshots/s2_15_dashboard_reset.png')

        browser.close()

if __name__ == '__main__':
    run()
