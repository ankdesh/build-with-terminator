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

        print("[Scenario 1] Navigating to studio...")
        page.goto('http://127.0.0.1:8080')
        page.wait_for_load_state('networkidle')
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_00_initial_home.png'))

        # 1. Load energy example
        print("[Scenario 1] Clicking 'Load energy example'...")
        load_btn = page.locator('button:has-text("Load energy example")').first
        load_btn.click()
        page.wait_for_timeout(3000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_01_loaded_example.png'))

        # 2. Select Pipeline view
        print("[Scenario 1] Navigating to Pipeline...")
        pipeline_nav = page.locator('aside.studio-navigation nav button:has-text("Pipeline")')
        if pipeline_nav.count() > 0:
            pipeline_nav.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_02_pipeline_view.png'))

        # 3. Open Data cleaning
        print("[Scenario 1] Navigating to Data cleaning...")
        cleaning_nav = page.locator('aside.studio-navigation nav button:has-text("Data cleaning")')
        if cleaning_nav.count() > 0:
            cleaning_nav.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_03_data_cleaning.png'))

        # 4. Select Run
        print("[Scenario 1] Clicking Run...")
        run_btn = page.locator('header.studio-header button.primary:has-text("Run")')
        run_btn.click()
        
        # Wait for run completion
        start_time = time.time()
        succeeded = False
        while time.time() - start_time < 30:
            status_text = page.locator('.workspace-toolbar .state-badge').text_content() or ''
            if 'Calculations up to date' in status_text:
                succeeded = True
                break
            time.sleep(1)
        print(f"[Scenario 1] Run finished. Succeeded: {succeeded}")
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_04_run_finished.png'))

        # 5. Open Visualization
        print("[Scenario 1] Navigating to Visualization...")
        vis_nav = page.locator('aside.studio-navigation nav button:has-text("Visualization")')
        if vis_nav.count() > 0:
            vis_nav.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS_DIR / 's1_05_visualization_view.png'))

        # Check metrics in visualization
        content = page.content()
        print("Checking key metrics in visualization page:")
        print("Contains 19,511.36:", "19,511.36" in content or "19511" in content)
        print("Contains 2,926.70:", "2,926.70" in content or "2926.7" in content)
        print("Contains 5,132.22:", "5,132.22" in content or "5132" in content)

        # 6. Open Dashboard
        print("[Scenario 1] Looking for Open dashboard button...")
        dash_btn = page.locator('a:has-text("Open dashboard")')
        dash_url = dash_btn.get_attribute('href')
        print("Dashboard URL:", dash_url)

        if dash_url:
            dash_page = context.new_page()
            dash_page.goto(dash_url)
            dash_page.wait_for_load_state('networkidle')
            dash_page.wait_for_timeout(2000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's1_06_dashboard_initial.png'))

            # Open Filters and scenarios
            print("[Scenario 1] Opening Filters and scenarios drawer...")
            filters_btn = dash_page.locator('button:has-text("Filters and scenarios")')
            filters_btn.click()
            dash_page.wait_for_timeout(1000)
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's1_07_filters_drawer_open.png'))

            # Change Price per kWh to 0.20
            print("[Scenario 1] Changing Price per kWh to 0.20...")
            price_input = dash_page.locator('label:has-text("Price per kWh") input')
            price_input.fill('0.20')
            
            # Click Apply controls
            apply_btn = dash_page.locator('button:has-text("Apply controls")')
            apply_btn.click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's1_08_dashboard_price_020.png'))

            # Check values
            d_content = dash_page.content()
            print("Price 0.20 check: Total kWh 19,511.36:", "19,511.36" in d_content)
            print("Price 0.20 check: Est Cost 3,902.27:", "3,902.27" in d_content)

            # Re-open filters, select Zone-A and Price 0.20
            print("[Scenario 1] Reopening filters to select Zone-A...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            
            zone_select = dash_page.locator('label:has-text("Zone") select')
            zone_select.select_option(label='Zone-A')
            
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's1_09_dashboard_zoneA_020.png'))
            
            d_content2 = dash_page.content()
            print("Zone A check: 5,132.22:", "5,132.22" in d_content2)
            print("Zone A check: 1,026.44:", "1,026.44" in d_content2)

            # Reset
            print("[Scenario 1] Resetting to All and 0.15...")
            dash_page.locator('button:has-text("Filters and scenarios")').click()
            dash_page.wait_for_timeout(1000)
            dash_page.locator('label:has-text("Zone") select').select_option(index=0)
            dash_page.locator('label:has-text("Price per kWh") input').fill('0.15')
            dash_page.locator('button:has-text("Apply controls")').click()
            dash_page.wait_for_timeout(3000)
            dash_page.wait_for_load_state('networkidle')
            dash_page.screenshot(path=str(SCREENSHOTS_DIR / 's1_10_dashboard_reset.png'))
            d_content3 = dash_page.content()
            print("Reset check: 19,511.36:", "19,511.36" in d_content3)
            print("Reset check: 2,926.70:", "2,926.70" in d_content3)

        browser.close()


if __name__ == '__main__':
    run()
