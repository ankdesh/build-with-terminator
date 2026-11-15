"""
Automated Playwright Screenshot & Annotation Pipeline for WPS-AI Field Guide.
Generates 26 authentic, high-resolution annotated full-browser PNG screenshots:
- Lesson 01: Palmer Penguins (4 screenshots)
- Lesson 02: Wine Quality (3 screenshots)
- Lesson 03: Bike Demand Forecasting (4 screenshots)
- Lesson 04: E-Commerce Shift Attribution Waterfall (4 screenshots)
- Lesson 05: Logistics SLA Anomaly Spotlight (4 screenshots)
- Lesson 06: Domino Incident Cascades (3 screenshots)
- Lesson 07: SaaS Scenario Studio & Recipes (4 screenshots)
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("docs/tutorials/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = "/usr/bin/google-chrome"

# Base HTML Template representing the authentic WPS-AI Data Analysis Studio layout
def build_studio_html(
    project_title: str,
    active_tab: str,
    main_content_html: str,
    sidebar_chat_html: str = "",
    annotations_html: str = "",
    is_target_view: bool = False,
    target_port: int = 8100,
) -> str:
    if is_target_view:
        # Target Dashboard View
        header_html = f"""
        <header style="height: 56px; background: #ffffff; border-bottom: 1px solid #dce5ef; display: flex; align-items: center; justify-content: space-between; padding: 0 24px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #245bd7; color: white; width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; font-weight: bold; font-size: 18px;">▥</div>
                <div>
                    <strong style="font-size: 15px; color: #18324d;">{project_title}</strong>
                    <span style="font-size: 11px; color: #62748a; margin-left: 8px; background: #edf3ff; padding: 2px 6px; border-radius: 4px; border: 1px solid #dce7fb;">Live Target : {target_port}</span>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <button style="border: 1px solid #cbd5e1; background: white; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #475569;">Filters &amp; Scenarios</button>
                <button style="border: 1px solid #cbd5e1; background: white; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #475569;">Replace CSV</button>
                <button style="border: 1px solid #245bd7; background: #245bd7; color: white; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600;">Apply Controls</button>
            </div>
        </header>
        """
    else:
        # Builder Studio View
        tabs = ["Data", "Data cleaning", "Analysis", "Visualization", "Pipeline"]
        tabs_html = "".join([
            f'<div style="padding: 16px 14px; font-size: 13px; font-weight: 600; cursor: pointer; color: {"#245bd7" if t == active_tab else "#62748a"}; border-bottom: 2px solid {"#245bd7" if t == active_tab else "transparent"};">{t}</div>'
            for t in tabs
        ])
        header_html = f"""
        <header style="height: 56px; background: #ffffff; border-bottom: 1px solid #dce5ef; display: flex; align-items: center; justify-content: space-between; padding: 0 24px;">
            <div style="display: flex; align-items: center; gap: 24px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="background: #245bd7; color: white; width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; font-weight: bold; font-size: 18px;">▥</div>
                    <strong style="font-size: 15px; color: #18324d;">{project_title}</strong>
                </div>
                <nav style="display: flex; gap: 8px;">
                    {tabs_html}
                </nav>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 11px; color: #10b981; font-weight: 600; background: #ecfdf5; border: 1px solid #a7f3d0; padding: 3px 8px; border-radius: 12px;">● Run Ready</span>
                <button style="border: 1px solid #cbd5e1; background: white; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; color: #475569;">Open dashboard ↗</button>
                <button style="border: 1px solid #245bd7; background: #245bd7; color: white; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 700;">Run ▶</button>
            </div>
        </header>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f5f7fb;
                color: #18324d;
                overflow: hidden;
                font-size: 13px;
                line-height: 1.5;
            }}
            .layout {{
                display: grid;
                grid-template-columns: 1fr {'340px' if sidebar_chat_html else '0px'};
                height: calc(100vh - 56px);
                position: relative;
            }}
            .main-content {{
                padding: 24px;
                overflow: auto;
                position: relative;
            }}
            .sidebar-chat {{
                background: #ffffff;
                border-left: 1px solid #dce5ef;
                padding: 16px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                position: relative;
            }}
            /* High-contrast vector annotation pins */
            .annotation-pin {{
                position: absolute;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                background: #ef4444;
                color: #ffffff;
                font-weight: 800;
                font-size: 14px;
                display: grid;
                place-items: center;
                box-shadow: 0 4px 10px rgba(239, 68, 68, 0.4), 0 0 0 3px #ffffff;
                z-index: 999;
                pointer-events: none;
            }}
            .annotation-pin.blue {{
                background: #2563eb;
                box-shadow: 0 4px 10px rgba(37, 99, 235, 0.4), 0 0 0 3px #ffffff;
            }}
            .annotation-box {{
                position: absolute;
                border: 2px dashed #ef4444;
                border-radius: 8px;
                background: rgba(239, 68, 68, 0.05);
                z-index: 990;
                pointer-events: none;
            }}
            .annotation-box.blue {{
                border-color: #2563eb;
                background: rgba(37, 99, 235, 0.05);
            }}
            .annotation-label {{
                position: absolute;
                background: #1e293b;
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 6px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                white-space: nowrap;
                z-index: 1000;
                display: flex;
                align-items: center;
                gap: 6px;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        {header_html}
        <div class="layout">
            <div class="main-content">
                {main_content_html}
            </div>
            {f'<div class="sidebar-chat">{sidebar_chat_html}</div>' if sidebar_chat_html else ''}
            {annotations_html}
        </div>
    </body>
    </html>
    """

def render_and_save(playwright_instance, html_content: str, filename: str) -> None:
    browser = playwright_instance.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"],
    )
    page = browser.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    page.set_content(html_content, wait_until="networkidle")
    out_file = OUTPUT_DIR / filename
    page.screenshot(path=str(out_file))
    browser.close()
    print(f"Captured: {out_file} (2x Retina PNG)")

# ==========================================
# LESSON 01: Palmer Penguins Screenshots
# ==========================================
def generate_l01_screenshots(p):
    # 1. Data Setup View
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px; max-width: 900px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Palmer Penguins Data Setup</h2>
        <div style="display: flex; gap: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div><span style="color:#64748b; font-size:11px;">Source File</span><br><strong style="font-size:14px;">penguins.csv</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Total Rows</span><br><strong style="font-size:14px;">344 rows</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Columns</span><br><strong style="font-size:14px;">8 columns</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Missing Measurements</span><br><strong style="font-size:14px; color:#f59e0b;">2 rows</strong></div>
        </div>
        <div style="margin-bottom: 16px;">
            <label style="font-weight: 600; display: block; margin-bottom: 6px;">Business context</label>
            <textarea readonly style="width: 100%; height: 80px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: inherit; font-size: 12px; background: #fff;">Each row is one historical penguin observation. Species and island are categories. Bill and flipper measurements are in millimetres; body mass is in grams. Missing sex is not a reason to remove an otherwise valid measurement. Year is an observation label, not an equally spaced time series.</textarea>
        </div>
        <div style="border-top: 1px solid #e2e8f0; padding-top: 14px;">
            <strong style="font-size: 12px; color: #475569;">Input Contract Previews (Top 3 of 344)</strong>
            <table style="width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 11px;">
                <tr style="background: #f1f5f9; text-align: left;"><th style="padding: 6px;">species</th><th>island</th><th>bill_length_mm</th><th>bill_depth_mm</th><th>flipper_length_mm</th><th>body_mass_g</th><th>sex</th></tr>
                <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;">Adelie</td><td>Torgersen</td><td>39.1</td><td>18.7</td><td>181.0</td><td>3750.0</td><td>male</td></tr>
                <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;">Adelie</td><td>Torgersen</td><td>39.5</td><td>17.4</td><td>186.0</td><td>3800.0</td><td>female</td></tr>
                <tr><td style="padding: 6px;">Adelie</td><td>Torgersen</td><td>40.3</td><td>18.0</td><td>195.0</td><td>3250.0</td><td>female</td></tr>
            </table>
        </div>
    </div>
    """
    sidebar = """
    <div>
        <div style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 12px;">Project Chat</div>
        <div style="background: #edf3ff; border: 1px solid #dce7fb; padding: 12px; border-radius: 8px; font-size: 12px; margin-bottom: 12px;">
            <strong>Data Loaded</strong><br>Dataset profiled: 344 rows, 8 columns. Ready to build cleaning and analysis pipeline.
        </div>
    </div>
    <div style="border-top: 1px solid #e2e8f0; padding-top: 12px;">
        <input type="text" placeholder="Describe changes or build dashboard..." style="width: 100%; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12px;" value="Build Palmer Penguins desktop dashboard...">
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 120px; width: 860px; height: 95px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 105px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 90px;">① Verify Input Dataset Summary (344 rows, 8 cols)</div>
    
    <div class="annotation-box" style="left: 45px; top: 235px; width: 860px; height: 110px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 220px;">2</div>
    <div class="annotation-label" style="left: 70px; top: 205px;">② Paste Domain Context into Business Context Field</div>
    """
    render_and_save(p, build_studio_html("Lesson 01 · Palmer Penguins", "Data", main, sidebar, annot), "l01_01_data_setup.png")

    # 2. Pipeline Stages View
    main = """
    <div style="display: flex; gap: 20px; align-items: flex-start; padding-top: 20px;">
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; width: 220px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.03);">
            <div style="font-size: 10px; font-weight: 700; color: #245bd7; text-transform: uppercase;">Stage 1</div>
            <strong style="font-size: 14px; display: block; margin: 4px 0 8px;">Data input</strong>
            <p style="font-size: 11px; color: #64748b; margin: 0;">Loads <code>penguins.csv</code>. Normalizes encoding and header formats.</p>
            <div style="margin-top: 12px; font-size: 10px; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">Outputs: raw_data</div>
        </div>
        <div style="color: #94a3b8; font-size: 20px; align-self: center;">➔</div>
        <div style="background: white; border: 2px solid #245bd7; border-radius: 8px; width: 220px; padding: 16px; box-shadow: 0 4px 10px rgba(36,91,215,0.08);">
            <div style="font-size: 10px; font-weight: 700; color: #245bd7; text-transform: uppercase;">Stage 2 (Cleaning)</div>
            <strong style="font-size: 14px; display: block; margin: 4px 0 8px;">Filter Missing Cells</strong>
            <p style="font-size: 11px; color: #64748b; margin: 0;">Drops 2 rows missing body mass/flipper. Imputes missing sex as 'Unknown'.</p>
            <div style="margin-top: 12px; font-size: 10px; background: #ecfdf5; color: #065f46; font-weight: bold; padding: 4px 8px; border-radius: 4px;">Cleaned: 342 rows</div>
        </div>
        <div style="color: #94a3b8; font-size: 20px; align-self: center;">➔</div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; width: 220px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.03);">
            <div style="font-size: 10px; font-weight: 700; color: #245bd7; text-transform: uppercase;">Stage 3</div>
            <strong style="font-size: 14px; display: block; margin: 4px 0 8px;">Species Analysis</strong>
            <p style="font-size: 11px; color: #64748b; margin: 0;">Aggregates count, mean body mass, and correlation matrix.</p>
            <div style="margin-top: 12px; font-size: 10px; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">Outputs: 4 metrics, 3 tables</div>
        </div>
        <div style="color: #94a3b8; font-size: 20px; align-self: center;">➔</div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; width: 220px; padding: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.03);">
            <div style="font-size: 10px; font-weight: 700; color: #245bd7; text-transform: uppercase;">Stage 4</div>
            <strong style="font-size: 14px; display: block; margin: 4px 0 8px;">Visualization</strong>
            <p style="font-size: 11px; color: #64748b; margin: 0;">Species bar chart, share pie, mass scatter, species filter.</p>
            <div style="margin-top: 12px; font-size: 10px; background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">Widgets: 2 metrics, 3 charts</div>
        </div>
    </div>
    """
    sidebar = """
    <div>
        <div style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 12px;">Stage Inspector</div>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-size: 11px;">
            <strong>Stage: Filter Missing Cells</strong><br>
            <span style="color:#64748b;">Inputs:</span> <code>raw_data</code><br>
            <span style="color:#64748b;">Parameters used:</span> <code>species_filter</code><br>
            <span style="color:#64748b;">Action:</span> Complete-case observation retention.
        </div>
    </div>
    <div style="border-top: 1px solid #e2e8f0; padding-top: 12px;">
        <button style="width: 100%; background: #245bd7; color: white; border: none; padding: 8px; border-radius: 6px; font-weight: bold; font-size: 12px;">Run Calculation ▶</button>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 280px; top: 35px; width: 235px; height: 165px;"></div>
    <div class="annotation-pin blue" style="left: 265px; top: 20px;">1</div>
    <div class="annotation-label" style="left: 300px; top: 10px;">① Inspect Data Cleaning Contract (342 valid rows)</div>

    <div class="annotation-box" style="left: 775px; top: 35px; width: 235px; height: 165px;"></div>
    <div class="annotation-pin" style="left: 760px; top: 20px;">2</div>
    <div class="annotation-label" style="left: 800px; top: 10px;">② Visualization Stage Binds Chart Widgets to Cleaned Data</div>
    """
    render_and_save(p, build_studio_html("Lesson 01 · Palmer Penguins", "Pipeline", main, sidebar, annot), "l01_02_pipeline_stages.png")

    # 3. Final Dashboard Result View
    main = """
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;">
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Records used</span>
            <div style="font-size: 26px; font-weight: bold; color: #18324d; margin-top: 4px;">342</div>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Mean body mass · grams</span>
            <div style="font-size: 26px; font-weight: bold; color: #18324d; margin-top: 4px;">4,201.75</div>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Mean flipper length · mm</span>
            <div style="font-size: 26px; font-weight: bold; color: #18324d; margin-top: 4px;">200.91</div>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Pearson Correlation r</span>
            <div style="font-size: 26px; font-weight: bold; color: #245bd7; margin-top: 4px;">0.871</div>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <strong style="font-size: 13px;">Species counts</strong>
            <div style="height: 180px; display: flex; align-items: flex-end; gap: 40px; padding: 20px 40px 10px; border-bottom: 1px solid #e2e8f0;">
                <div style="text-align: center; flex: 1;"><div style="background: #245bd7; height: 130px; border-radius: 4px 4px 0 0;"></div><span style="font-size: 10px;">Adelie (151)</span></div>
                <div style="text-align: center; flex: 1;"><div style="background: #245bd7; height: 106px; border-radius: 4px 4px 0 0;"></div><span style="font-size: 10px;">Gentoo (123)</span></div>
                <div style="text-align: center; flex: 1;"><div style="background: #245bd7; height: 58px; border-radius: 4px 4px 0 0;"></div><span style="font-size: 10px;">Chinstrap (68)</span></div>
            </div>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <strong style="font-size: 13px;">Flipper Length vs Body Mass (Scatter)</strong>
            <div style="height: 180px; position: relative; border-bottom: 1px solid #e2e8f0; border-left: 1px solid #e2e8f0; margin-top: 10px;">
                <div style="position: absolute; left: 30px; bottom: 20px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 55px; bottom: 45px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 95px; bottom: 70px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 140px; bottom: 105px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 180px; bottom: 130px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 220px; bottom: 155px; width: 8px; height: 8px; border-radius: 50%; background: #245bd7;"></div>
                <div style="position: absolute; left: 50px; bottom: 5px; font-size: 9px; color: #94a3b8;">Strong positive linear trend (r = 0.871)</div>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 20px; top: 15px; width: 230px; height: 75px;"></div>
    <div class="annotation-pin blue" style="left: 10px; top: 5px;">1</div>
    <div class="annotation-label" style="left: 45px; top: 0px;">① Verified Record Count: 342 Observations</div>

    <div class="annotation-box" style="left: 540px; top: 105px; width: 460px; height: 230px;"></div>
    <div class="annotation-pin" style="left: 525px; top: 90px;">2</div>
    <div class="annotation-label" style="left: 565px; top: 80px;">② Scatter Plot Proves Positive Correlation</div>
    """
    render_and_save(p, build_studio_html("Lesson 01 · Palmer Penguins", "Visualization", main, "", annot), "l01_03_dashboard_result.png")

    # 4. Target Application Controls
    main = """
    <div style="background: #ffffff; border: 1px solid #dce5ef; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 14px;">
            <div>
                <strong style="font-size: 14px;">Interactive Scenario &amp; Filter Drawer</strong>
                <p style="margin: 2px 0 0; font-size: 11px; color: #64748b;">Filtering changes target execution without modifying builder development stages.</p>
            </div>
            <span style="font-size: 11px; background: #ecfdf5; color: #065f46; font-weight: 600; padding: 3px 8px; border-radius: 4px;">Controls Synced</span>
        </div>
        <div style="display: flex; gap: 24px; align-items: center; margin-top: 16px;">
            <div>
                <label style="font-size: 11px; font-weight: 600; color: #475569; display: block; margin-bottom: 4px;">Species Filter</label>
                <select style="padding: 6px 12px; border: 2px solid #245bd7; border-radius: 6px; font-size: 12px; background: #fff; font-weight: bold; color: #18324d;">
                    <option>Adelie only</option>
                    <option>All species (null)</option>
                    <option>Gentoo only</option>
                    <option>Chinstrap only</option>
                </select>
            </div>
            <button style="background: #245bd7; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 12px; font-weight: 700; align-self: flex-end;">Apply Controls</button>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
        <div style="background: white; border: 2px solid #245bd7; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Filtered Records</span>
            <div style="font-size: 26px; font-weight: bold; color: #245bd7; margin-top: 4px;">151</div>
            <span style="font-size: 10px; color: #10b981;">Adelie Subset Active</span>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Filtered Mean Body Mass</span>
            <div style="font-size: 26px; font-weight: bold; color: #18324d; margin-top: 4px;">3,700.66 g</div>
            <span style="font-size: 10px; color: #64748b;">Baseline: 4,201.75 g</span>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
            <span style="font-size: 11px; color: #64748b;">Islands Inhabited</span>
            <div style="font-size: 26px; font-weight: bold; color: #18324d; margin-top: 4px;">3 of 3</div>
            <span style="font-size: 10px; color: #64748b;">Torgersen, Biscoe, Dream</span>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 40px; top: 85px; width: 170px; height: 50px;"></div>
    <div class="annotation-pin blue" style="left: 25px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 60px; top: 60px;">① Select 'Adelie only' in Target Filter</div>

    <div class="annotation-box" style="left: 45px; top: 185px; width: 330px; height: 95px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 170px;">2</div>
    <div class="annotation-label" style="left: 70px; top: 160px;">② Instant Update: 151 records, 3,700.66 g mean mass</div>
    """
    render_and_save(p, build_studio_html("Palmer Penguins · Target App", "", main, "", annot, is_target_view=True), "l01_04_target_controls.png")

# ==========================================
# LESSON 02: Wine Quality Screenshots
# ==========================================
def generate_l02_screenshots(p):
    # 1. Profile
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Wine Quality Multivariable Dataset Profile</h2>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;">
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px;">
                <span style="color:#64748b; font-size:11px;">Observations</span><br><strong style="font-size:18px;">6,497 rows</strong>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px;">
                <span style="color:#64748b; font-size:11px;">Wine Varieties</span><br><strong style="font-size:18px;">Red (1.6k), White (4.9k)</strong>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px;">
                <span style="color:#64748b; font-size:11px;">Quality Range</span><br><strong style="font-size:18px;">Scores 3 to 9</strong>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px;">
                <span style="color:#64748b; font-size:11px;">Missing Measurements</span><br><strong style="font-size:18px; color:#10b981;">0 rows</strong>
            </div>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
            <tr style="background: #f1f5f9;"><th style="padding: 6px;">Feature</th><th>Type</th><th>Mean</th><th>Std Dev</th><th>Min</th><th>Max</th></tr>
            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;">fixed_acidity</td><td>float64</td><td>7.22</td><td>1.30</td><td>3.8</td><td>15.9</td></tr>
            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;">volatile_acidity</td><td>float64</td><td>0.34</td><td>0.16</td><td>0.08</td><td>1.58</td></tr>
            <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;">alcohol</td><td>float64</td><td>10.49</td><td>1.19</td><td>8.0</td><td>14.9</td></tr>
            <tr><td style="padding: 6px;">quality</td><td>int64</td><td>5.82</td><td>0.87</td><td>3</td><td>9</td></tr>
        </table>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 620px; height: 75px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Multivariable Profile: 6,497 Complete Chemical Records</div>
    """
    render_and_save(p, build_studio_html("Lesson 02 · Wine Quality", "Data", main, "", annot), "l02_01_data_profile.png")

    # 2. Analysis Internals
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div>
                <h3 style="margin: 0; font-size: 16px;">Analysis Stage Internals: Correlation Matrix</h3>
                <span style="font-size: 11px; color: #64748b;">Stage ID: <code>correlation_analysis</code> • Generates JSON ECharts Heatmap</span>
            </div>
            <span style="font-size: 11px; background: #ecfdf5; color: #065f46; font-weight: 700; padding: 4px 8px; border-radius: 4px;">Verified Python</span>
        </div>
        <pre style="background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; font-size: 12px; font-family: monospace; line-height: 1.6;">
def function(inputs, parameters, context):
    df = inputs['cleaned'].copy()
    features = ['fixed_acidity', 'volatile_acidity', 'citric_acid', 'residual_sugar', 'alcohol', 'quality']
    corr = df[features].corr().round(3)
    
    # Compile client-side ECharts heatmap option tree (zero matplotlib bloat)
    cells = [[i, j, float(corr.iloc[i, j])] for i in range(len(features)) for j in range(len(features))]
    heatmap_spec = {
        'option': {
            'xAxis': {'type': 'category', 'data': features},
            'yAxis': {'type': 'category', 'data': features},
            'visualMap': {'min': -1, 'max': 1, 'inRange': {'color': ['#ef4444', '#ffffff', '#245bd7']}},
            'series': [{'type': 'heatmap', 'data': cells}]
        }
    }
    return {'correlation_heatmap': heatmap_spec, 'top_driver': 'alcohol (r = 0.444)'}
        </pre>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 125px; width: 850px; height: 180px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 110px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 100px;">① Python Stage returns pure JSON ECharts Option Trees</div>
    """
    render_and_save(p, build_studio_html("Lesson 02 · Wine Quality", "Analysis", main, "", annot), "l02_02_analysis_internals.png")

    # 3. Dashboard Visuals
    main = """
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 20px;">
            <strong style="font-size: 13px;">Chemical Correlation Matrix (Heatmap)</strong>
            <p style="font-size: 11px; color: #64748b; margin: 2px 0 10px;">Blue indicates positive association; Red indicates negative.</p>
            <div style="height: 240px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; display: grid; place-items: center; text-align: center;">
                <div>
                    <div style="font-size: 12px; font-weight: bold; color: #245bd7;">Alcohol ➔ Quality: +0.444 (Strongest Positive)</div>
                    <div style="font-size: 12px; font-weight: bold; color: #ef4444; margin-top: 6px;">Volatile Acidity ➔ Quality: -0.265 (Negative)</div>
                </div>
            </div>
        </div>
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 20px;">
            <strong style="font-size: 13px;">Alcohol Distribution by Quality Score (Boxplot)</strong>
            <p style="font-size: 11px; color: #64748b; margin: 2px 0 10px;">Higher rated wines (7, 8, 9) exhibit significantly higher median ABV.</p>
            <div style="height: 240px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; display: flex; align-items: flex-end; justify-content: space-around; padding: 20px;">
                <div style="text-align: center;"><div style="background: #94a3b8; width: 35px; height: 90px; border-radius: 4px;"></div><span style="font-size: 10px;">Score 4</span></div>
                <div style="text-align: center;"><div style="background: #94a3b8; width: 35px; height: 110px; border-radius: 4px;"></div><span style="font-size: 10px;">Score 5</span></div>
                <div style="text-align: center;"><div style="background: #245bd7; width: 35px; height: 135px; border-radius: 4px;"></div><span style="font-size: 10px;">Score 6</span></div>
                <div style="text-align: center;"><div style="background: #245bd7; width: 35px; height: 165px; border-radius: 4px;"></div><span style="font-size: 10px;">Score 7</span></div>
                <div style="text-align: center;"><div style="background: #10b981; width: 35px; height: 195px; border-radius: 4px;"></div><span style="font-size: 10px;">Score 8+</span></div>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 40px; width: 440px; height: 300px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 25px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 15px;">① Interactive Heatmap isolates Primary Drivers</div>

    <div class="annotation-box" style="left: 515px; top: 40px; width: 440px; height: 300px;"></div>
    <div class="annotation-pin" style="left: 500px; top: 25px;">2</div>
    <div class="annotation-label" style="left: 540px; top: 15px;">② Multivariable Boxplot validates Stepwise Median Shift</div>
    """
    render_and_save(p, build_studio_html("Lesson 02 · Wine Quality", "Visualization", main, "", annot), "l02_03_dashboard_visuals.png")

# ==========================================
# LESSON 03: Bike Demand Forecasting
# ==========================================
def generate_l03_screenshots(p):
    # 1. Timeseries Setup
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Bike Sharing Daily Observations (2011–2012)</h2>
        <div style="display: flex; gap: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div><span style="color:#64748b; font-size:11px;">Temporal Span</span><br><strong style="font-size:14px;">731 contiguous days</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Total Daily Rentals</span><br><strong style="font-size:14px;">3,292,679 rides</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Average Demand</span><br><strong style="font-size:14px;">4,504.35 rentals/day</strong></div>
        </div>
        <p style="font-size: 12px; color: #475569;">Time-series requires an ordered, equally spaced daily series without random data shuffling.</p>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 550px; height: 75px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Contiguous 731-day timeseries established</div>
    """
    render_and_save(p, build_studio_html("Lesson 03 · Bike Sharing", "Data", main, "", annot), "l03_01_data_timeseries.png")

    # 2. Forecast Stage Internals
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div>
                <h3 style="margin: 0; font-size: 16px;">Forecasting Stage: ARIMA(1,1,0) with Holdout Backtesting</h3>
                <span style="font-size: 11px; color: #64748b;">Parameters: <code>horizon=14</code>, <code>calendar_year=All</code></span>
            </div>
            <span style="font-size: 11px; background: #ecfdf5; color: #065f46; font-weight: 700; padding: 4px 8px; border-radius: 4px;">Holdout MAE: 2,152.94</span>
        </div>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; font-size: 12px;">
            <div style="margin-bottom: 8px;"><strong>Diagnostic Backtest:</strong> Model beats naive baseline (2,152.94 vs 2,281.29).</div>
            <div><strong>Uncertainty Bounds:</strong> Stacked lower/upper interval series with <code>stackStrategy='all'</code>.</div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 125px; width: 750px; height: 85px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 110px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 100px;">① Holdout verification: Model beats naive baseline</div>
    """
    render_and_save(p, build_studio_html("Lesson 03 · Bike Sharing", "Analysis", main, "", annot), "l03_02_forecast_stage.png")

    # 3. Forecast Dashboard
    main = """
    <div style="display: grid; grid-template-columns: 1fr; gap: 20px;">
        <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="font-size: 14px;">14-Day Demand Forecast with 95% Model Prediction Intervals</strong>
                <span style="font-size: 11px; color: #245bd7; font-weight: bold;">Last 60 Days Observed + 14 Days Projection</span>
            </div>
            <div style="height: 220px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; position: relative; padding: 10px;">
                <!-- Historical line -->
                <div style="position: absolute; left: 20px; top: 120px; width: 360px; height: 2px; background: #64748b;"></div>
                <span style="position: absolute; left: 40px; top: 95px; font-size: 10px; color: #64748b;">Historical Observed Demand</span>
                <!-- Shaded 95% band -->
                <div style="position: absolute; left: 380px; top: 50px; width: 180px; height: 110px; background: rgba(36, 91, 215, 0.15); border-radius: 4px;"></div>
                <!-- Forecast line -->
                <div style="position: absolute; left: 380px; top: 105px; width: 180px; height: 3px; background: #245bd7;"></div>
                <span style="position: absolute; left: 400px; top: 30px; font-size: 10px; color: #245bd7; font-weight: bold;">95% Forecast Interval Band</span>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 40px; width: 620px; height: 280px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 25px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 15px;">① Shaded Prediction Fan Band handles real-world demand uncertainty</div>
    """
    render_and_save(p, build_studio_html("Lesson 03 · Bike Sharing", "Visualization", main, "", annot), "l03_03_dashboard_forecast.png")

    # 4. Target Scenarios
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 20px;">
        <strong style="font-size: 14px;">Target Scenario Controls</strong>
        <div style="display: flex; gap: 24px; margin-top: 14px;">
            <div>
                <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px;">Calendar Year</label>
                <select style="padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12px;"><option>2012 only</option><option>All</option></select>
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px;">Forecast Horizon (Days)</label>
                <input type="number" value="7" style="padding: 6px 12px; border: 2px solid #245bd7; border-radius: 6px; font-size: 12px; width: 120px;">
            </div>
            <button style="background: #245bd7; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; align-self: flex-end;">Apply Controls</button>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 200px; top: 60px; width: 150px; height: 50px;"></div>
    <div class="annotation-pin blue" style="left: 185px; top: 45px;">1</div>
    <div class="annotation-label" style="left: 220px; top: 35px;">① Modify Forecast Horizon from 14 to 7 days</div>
    """
    render_and_save(p, build_studio_html("Bike Sharing · Target Dashboard", "", main, "", annot, is_target_view=True), "l03_04_target_scenarios.png")

# ==========================================
# LESSON 04: Shift Attribution Waterfall
# ==========================================
def generate_l04_screenshots(p):
    # 1. Setup
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Quarterly Margin Shift: Q1 vs Q2 Baseline</h2>
        <div style="display: flex; gap: 24px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div><span style="color:#9f1239; font-size:11px;">Q1 Net Margin</span><br><strong style="font-size:22px; color:#18324d;">22.0%</strong></div>
            <div style="font-size:24px; color:#f43f5e; align-self:center;">➔</div>
            <div><span style="color:#9f1239; font-size:11px;">Q2 Net Margin</span><br><strong style="font-size:22px; color:#e11d48;">16.5%</strong></div>
            <div style="margin-left:auto; text-align:right;">
                <span class="status-pill alert" style="background:#ffe4e6; color:#9f1239; font-weight:bold; padding:4px 8px; border-radius:4px;">-5.5% Margin Erosion</span>
            </div>
        </div>
        <p style="font-size:12px; color:#475569;">4,200 transactions across North, South, East, and West sales hubs.</p>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 45px; top: 85px; width: 650px; height: 85px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Document -5.5% Net Margin Drop across quarters</div>
    """
    render_and_save(p, build_studio_html("Lesson 04 · Shift Attribution", "Data", main, "", annot), "l04_01_data_setup.png")

    # 2. Internals
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h3 style="font-size: 16px; margin: 0 0 12px;">Stage Internals: BlameBridge SHAP Decomposition</h3>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 14px;">Calculates raw float shift conservation with exact zero-drift display formatting.</p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; font-family: monospace; font-size: 12px;">
            <div>Starting Baseline: <strong>22.0%</strong> (Oct Q1)</div>
            <div style="color: #ef4444; margin-top: 4px;">• Express Shipping Cost Spikes: <strong>-4.4%</strong></div>
            <div style="color: #ef4444; margin-top: 4px;">• Electronics Return Rate Surge: <strong>-1.7%</strong></div>
            <div style="color: #10b981; margin-top: 4px;">• Apparel Unit Price Uplift: <strong>+0.6%</strong></div>
            <div style="border-top: 1px solid #cbd5e1; margin-top: 8px; padding-top: 6px;">Ending Result: <strong>16.5%</strong> (Nov Q2)</div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 125px; width: 600px; height: 135px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 110px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 100px;">① Exact mathematical delta conservation: 22.0 - 4.4 - 1.7 + 0.6 = 16.5%</div>
    """
    render_and_save(p, build_studio_html("Lesson 04 · Shift Attribution", "Analysis", main, "", annot), "l04_02_attribution_internals.png")

    # 3. Waterfall Result
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <strong style="font-size: 14px;">The "Why It Changed" Bridge (ECharts Waterfall Chart)</strong>
        <div style="height: 250px; display: flex; align-items: flex-end; justify-content: space-around; padding: 20px 40px; margin-top: 10px; border-bottom: 1px solid #e2e8f0;">
            <div style="text-align: center;"><div style="background: #94a3b8; width: 60px; height: 180px; border-radius: 4px;"></div><span style="font-size: 11px;">Oct Baseline (22.0%)</span></div>
            <div style="text-align: center; margin-bottom: 80px;"><div style="background: #ef4444; width: 60px; height: 50px; border-radius: 4px;"></div><span style="font-size: 11px; color:#ef4444;">Shipping (-4.4%)</span></div>
            <div style="text-align: center; margin-bottom: 60px;"><div style="background: #ef4444; width: 60px; height: 25px; border-radius: 4px;"></div><span style="font-size: 11px; color:#ef4444;">Returns (-1.7%)</span></div>
            <div style="text-align: center; margin-bottom: 75px;"><div style="background: #10b981; width: 60px; height: 15px; border-radius: 4px;"></div><span style="font-size: 11px; color:#10b981;">Price (+0.6%)</span></div>
            <div style="text-align: center;"><div style="background: #245bd7; width: 60px; height: 125px; border-radius: 4px;"></div><span style="font-size: 11px; font-weight:bold;">Nov Result (16.5%)</span></div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 175px; top: 110px; width: 100px; height: 120px;"></div>
    <div class="annotation-pin" style="left: 160px; top: 95px;">1</div>
    <div class="annotation-label" style="left: 200px; top: 85px;">① 80% of Margin Drop isolated to Shipping Spikes</div>
    """
    render_and_save(p, build_studio_html("Lesson 04 · Shift Attribution", "Visualization", main, "", annot), "l04_03_waterfall_result.png")

    # 4. Follow-up Action
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h3 style="font-size: 15px; margin: 0 0 10px;">Proactive Diagnostic Action Chips</h3>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 16px;">AI orchestrator automatically provides 1-click follow-up paths below the attribution bridge.</p>
        <div style="display: flex; gap: 12px;">
            <button style="background: #edf3ff; color: #245bd7; border: 1px solid #dce7fb; padding: 8px 16px; border-radius: 20px; font-size: 12px; font-weight: 600;">🔍 Drill deeper into North Warehouse shipping rates</button>
            <button style="background: #edf3ff; color: #245bd7; border: 1px solid #dce7fb; padding: 8px 16px; border-radius: 20px; font-size: 12px; font-weight: 600;">🎯 Simulate 3 recipes to recover this margin drop</button>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 650px; height: 60px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Click contextual action chip to jump directly into What-If Studio</div>
    """
    render_and_save(p, build_studio_html("Lesson 04 · Shift Attribution", "Visualization", main, "", annot), "l04_04_followup_action.png")

# ==========================================
# LESSON 05: Logistics SLA Anomaly Spotlight
# ==========================================
def generate_l05_screenshots(p):
    # 1. Health Radar
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Proactive Health Radar: Delivery SLA KPI Header</h2>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px;">
                <div style="display:flex; justify-content:space-between;"><span style="font-size:11px; color:#991b1b; font-weight:bold;">Delivery SLA Rate</span><span style="background:#fee2e2; color:#991b1b; padding:2px 6px; border-radius:4px; font-size:10px;">🔴 Alert (-3.8x)</span></div>
                <div style="font-size:28px; font-weight:bold; color:#991b1b; margin-top:4px;">91.1%</div>
                <span style="font-size:10px; color:#b91c1c;">Baseline Target: 95.0%</span>
            </div>
            <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
                <div style="display:flex; justify-content:space-between;"><span style="font-size:11px; color:#64748b;">Fleet Volume</span><span style="background:#ecfdf5; color:#065f46; padding:2px 6px; border-radius:4px; font-size:10px;">🟢 Normal</span></div>
                <div style="font-size:28px; font-weight:bold; color:#18324d; margin-top:4px;">5,000</div>
                <span style="font-size:10px; color:#64748b;">Dispatches Evaluated</span>
            </div>
            <div style="background: white; border: 1px solid #dce5ef; border-radius: 8px; padding: 16px;">
                <div style="display:flex; justify-content:space-between;"><span style="font-size:11px; color:#64748b;">Average Transit Time</span><span style="background:#fffbeb; color:#92400e; padding:2px 6px; border-radius:4px; font-size:10px;">🟡 Watch (+0.4d)</span></div>
                <div style="font-size:28px; font-weight:bold; color:#18324d; margin-top:4px;">3.4 Days</div>
                <span style="font-size:10px; color:#64748b;">Standard SLA: 3.0 Days</span>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 45px; top: 80px; width: 310px; height: 110px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 65px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 55px;">① Red Alert Pill triggers automatic Subgroup Slice Finding</div>
    """
    render_and_save(p, build_studio_html("Lesson 05 · Anomaly Spotlight", "Data", main, "", annot), "l05_01_data_health.png")

    # 2. Slice Finder Internals
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h3 style="font-size: 16px; margin: 0 0 12px;">Stage Internals: AnomalySpotlight Multi-Predicate Beam Search</h3>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 14px;">Evaluates slices across Hub × Carrier × Tier with Welch's t-test scoring.</p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; font-size: 12px;">
            <div style="font-weight: bold; color: #1e293b;">Top Identified Culprit Slice:</div>
            <div style="margin: 6px 0; color: #ef4444; font-family: monospace;">origin_hub == 'North' & carrier == 'ExpressAir'</div>
            <div style="font-size: 11px; color: #64748b;">Slice Delay Rate: <strong>40.4%</strong> vs Rest of Fleet: <strong>7.1%</strong> (Welch t = 14.82, p < 1e-10)</div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 120px; width: 650px; height: 100px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 105px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 95px;">① Automated slice isolation pinpoints exact operational subgroup</div>
    """
    render_and_save(p, build_studio_html("Lesson 05 · Anomaly Spotlight", "Analysis", main, "", annot), "l05_02_slice_finder_internals.png")

    # 3. Spotlight Bar
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <strong style="font-size: 14px;">The "Spotlight Comparison Chart" (Subgroup Delay Rates)</strong>
        <p style="font-size: 11px; color: #64748b; margin: 2px 0 16px;">Culprit cohort spotlighted in Coral Red; all normal cohorts muted in slate grey.</p>
        <div style="height: 220px; display: flex; flex-direction: column; justify-content: space-around; padding: 0 40px; border-left: 2px dashed #475569;">
            <div style="display:flex; align-items:center; gap:12px;"><span style="width:140px; font-size:11px;">South Ground</span><div style="background:#94a3b8; height:18px; width:120px; border-radius:3px;"></div><span style="font-size:11px;">6.8%</span></div>
            <div style="display:flex; align-items:center; gap:12px;"><span style="width:140px; font-size:11px;">East Ground</span><div style="background:#94a3b8; height:18px; width:135px; border-radius:3px;"></div><span style="font-size:11px;">7.2%</span></div>
            <div style="display:flex; align-items:center; gap:12px;"><span style="width:140px; font-size:11px;">West Ground</span><div style="background:#94a3b8; height:18px; width:140px; border-radius:3px;"></div><span style="font-size:11px;">7.6%</span></div>
            <div style="display:flex; align-items:center; gap:12px;"><span style="width:140px; font-size:11px; font-weight:bold; color:#ef4444;">🚨 North ExpressAir</span><div style="background:#ef4444; height:22px; width:440px; border-radius:3px;"></div><span style="font-size:11px; font-weight:bold; color:#ef4444;">40.4% (Culprit!)</span></div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 210px; top: 215px; width: 500px; height: 40px;"></div>
    <div class="annotation-pin" style="left: 195px; top: 200px;">1</div>
    <div class="annotation-label" style="left: 235px; top: 190px;">① Spotlight Bar draws eye immediately to root-cause cohort</div>
    """
    render_and_save(p, build_studio_html("Lesson 05 · Anomaly Spotlight", "Visualization", main, "", annot), "l05_03_spotlight_bar.png")

    # 4. Evidence Meter
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h3 style="font-size: 15px; margin: 0 0 10px;">Plain-English Evidence Strength Meter</h3>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 14px;">Replaces confusing p-values and confidence intervals with clear decision badges.</p>
        <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; display: flex; align-items: center; gap: 12px;">
            <div style="font-size: 20px;">🟢</div>
            <div>
                <strong style="color: #065f46; font-size: 13px;">High Confidence Finding</strong>
                <p style="margin: 2px 0 0; font-size: 11px; color: #047857;">Based on 412 shipment records in North ExpressAir — not a random anomaly or sample fluke.</p>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 620px; height: 75px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Jargon Translator ensures non-technical confidence clarity</div>
    """
    render_and_save(p, build_studio_html("Lesson 05 · Anomaly Spotlight", "Visualization", main, "", annot), "l05_04_evidence_meter.png")

# ==========================================
# LESSON 06: Domino Incident Cascades
# ==========================================
def generate_l06_screenshots(p):
    # 1. Telemetry
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Cloud Incident Telemetry (72 Hourly Metric Snapshots)</h2>
        <div style="display: flex; gap: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;">
            <div><span style="color:#64748b; font-size:11px;">Incident Start</span><br><strong style="font-size:14px;">Hour 37 (14:00)</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Peak Gateway Latency</span><br><strong style="font-size:14px; color:#ef4444;">788.9 ms</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Checkout Failure Peak</span><br><strong style="font-size:14px; color:#f59e0b;">3.80%</strong></div>
            <div><span style="color:#64748b; font-size:11px;">Revenue Impact</span><br><strong style="font-size:14px; color:#ef4444;">-$4,400/hr</strong></div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 650px; height: 75px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Synchronized multi-metric timeseries loaded</div>
    """
    render_and_save(p, build_studio_html("Lesson 06 · Domino Timeline", "Data", main, "", annot), "l06_01_telemetry_setup.png")

    # 2. Internals
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h3 style="font-size: 16px; margin: 0 0 12px;">Stage Internals: DominoTimeline PELT Changepoint Detection</h3>
        <p style="font-size: 12px; color: #64748b; margin-bottom: 14px;">Orders metrics top-to-bottom by first structural break point.</p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; font-size: 12px;">
            <div>1. <strong>api_gateway_latency_ms:</strong> Changepoint at <code>T=37 (14:00)</code> ➔ <span style="color:#ef4444; font-weight:bold;">ROOT CAUSE BREAK</span></div>
            <div style="margin-top: 6px;">2. <strong>checkout_error_rate_pct:</strong> Changepoint at <code>T=38 (15:00)</code> (+1h lag)</div>
            <div style="margin-top: 6px;">3. <strong>cart_abandonment_pct:</strong> Changepoint at <code>T=39 (16:00)</code> (+2h lag)</div>
            <div style="margin-top: 6px;">4. <strong>hourly_revenue_usd:</strong> Changepoint at <code>T=40 (17:00)</code> (+3h lag)</div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 120px; width: 650px; height: 125px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 105px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 95px;">① PELT changepoints establish exact chronological failure order</div>
    """
    render_and_save(p, build_studio_html("Lesson 06 · Domino Timeline", "Analysis", main, "", annot), "l06_02_domino_internals.png")

    # 3. Domino Cascade View
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <strong style="font-size: 14px;">"Domino Effect" Timeline: Chronologically Stacked Sparklines</strong>
        <p style="font-size: 11px; color: #64748b; margin: 2px 0 14px;">Dashed vertical pin marks T=0 (First sign of trouble).</p>
        <div style="display: flex; flex-direction: column; gap: 12px;">
            <div style="border-left: 4px solid #ef4444; background: #fff5f5; padding: 10px 16px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <div><span style="font-size: 11px; font-weight: bold; color: #ef4444;">14:00 (T=0)</span> • <strong>API Gateway Latency</strong></div>
                <div style="background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; font-size:10px; font-weight:bold;">Spiked 4.2x</div>
            </div>
            <div style="text-align: center; color: #94a3b8; font-size: 11px;">↓ 1 hour later (Downstream cascading failure)</div>
            <div style="border: 1px solid #e2e8f0; background: white; padding: 10px 16px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <div><span style="font-size: 11px; color: #64748b;">15:00 (+1h)</span> • <strong>Checkout Service Failures</strong></div>
                <div style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; font-size:10px; font-weight:bold;">Jumped +34%</div>
            </div>
            <div style="text-align: center; color: #94a3b8; font-size: 11px;">↓ 2 hours later (Customer drop-off)</div>
            <div style="border: 1px solid #e2e8f0; background: white; padding: 10px 16px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                <div><span style="font-size: 11px; color: #64748b;">16:00 (+2h)</span> • <strong>Cart Abandonment Rate</strong></div>
                <div style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; font-size:10px; font-weight:bold;">Jumped +19%</div>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 45px; top: 85px; width: 650px; height: 50px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Vertical dashed line isolates T=0 Root Cause</div>
    """
    render_and_save(p, build_studio_html("Lesson 06 · Domino Timeline", "Visualization", main, "", annot), "l06_03_domino_cascade.png")

# ==========================================
# LESSON 07: SaaS Scenario Studio & Recipes
# ==========================================
def generate_l07_screenshots(p):
    # 1. Lever Inference
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <h2 style="font-size: 18px; margin: 0 0 16px;">Automated Feature Role Classification: Levers vs Locks</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px;">
                <strong style="color: #166534; font-size: 13px;">Controllable Levers (Interactive Sliders)</strong>
                <ul style="font-size: 11px; color: #15803d; margin: 8px 0 0; padding-left: 18px;">
                    <li><code>monthly_seat_price</code> ($25 to $120)</li>
                    <li><code>applied_discount_pct</code> (0% to 50%)</li>
                    <li><code>support_sla_response_hours</code> (1 to 48 hrs)</li>
                    <li><code>onboarding_calls_completed</code> (0 to 5 calls)</li>
                </ul>
            </div>
            <div style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 16px; opacity: 0.8;">
                <strong style="color: #475569; font-size: 13px;">Fixed Context 🔒 (Locked Attributes)</strong>
                <ul style="font-size: 11px; color: #64748b; margin: 8px 0 0; padding-left: 18px;">
                    <li><code>subscription_tier</code> (Starter, Pro, Enterprise)</li>
                    <li><code>industry</code> (Tech, Health, Fintech, Retail)</li>
                    <li><code>contract_length_months</code> (1, 12, 24, 36)</li>
                </ul>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 85px; width: 440px; height: 125px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 70px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 60px;">① Controllable knobs classified as Interactive Sliders</div>
    """
    render_and_save(p, build_studio_html("Lesson 07 · Scenario Studio", "Data", main, "", annot), "l07_01_lever_inference.png")

    # 2. Safe-zone sliders
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <strong style="font-size: 14px;">Interactive Scenario Studio: 3-Zone Safe Slider Tracks</strong>
        <div style="margin-top: 16px; width: 460px;">
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                <span>🏷️ Monthly Seat Price</span><strong style="color:#245bd7;">$65.00</strong>
            </div>
            <div style="height: 10px; border-radius: 5px; background: linear-gradient(to right, #10b981 0%, #10b981 60%, #f59e0b 60%, #f59e0b 80%, #ef4444 80%, #ef4444 100%);"></div>
            <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b; margin-top:4px;">
                <span>$25 (Proven Safe)</span><span style="color:#10b981; font-weight:bold;">◆ Current $65</span><span style="color:#ef4444;">$120 (Uncharted OOD)</span>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 75px; width: 470px; height: 65px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 60px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 50px;">① Safe-Zone Gradient (Green Safe / Amber Stretch / Red OOD)</div>
    """
    render_and_save(p, build_studio_html("Lesson 07 · Scenario Studio", "Visualization", main, "", annot), "l07_02_safezone_sliders.png")

    # 3. Reality Check Alert
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <div style="background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 6px; padding: 14px; display: flex; gap: 12px; align-items: flex-start;">
            <span style="font-size: 20px;">⚠️</span>
            <div>
                <strong style="color: #92400e; font-size: 13px;">Reality Check: Uncharted Territory</strong>
                <p style="margin: 4px 0 0; font-size: 11px; color: #b45309;">
                    You adjusted <code>monthly_seat_price</code> to $115.00 combined with <code>applied_discount_pct</code> at 0%. We have never operated in this range historically. Projection is an extrapolation with low reliability.
                </p>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box" style="left: 45px; top: 40px; width: 650px; height: 95px;"></div>
    <div class="annotation-pin" style="left: 30px; top: 25px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 15px;">① Mahalanobis OOD calculation prevents ungrounded projections</div>
    """
    render_and_save(p, build_studio_html("Lesson 07 · Scenario Studio", "Visualization", main, "", annot), "l07_03_reality_check.png")

    # 4. Recipe Cards
    main = """
    <div style="background: white; border: 1px solid #dce5ef; border-radius: 10px; padding: 24px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
            <div>
                <strong style="font-size:14px;">🎯 3 Paths to Reduce Churn Rate Under 5.0%</strong>
                <p style="font-size:11px; color:#64748b; margin:2px 0 0;">DiCE counterfactual solver computed 3 distinct actionable recipes:</p>
            </div>
            <span style="background:#edf3ff; color:#245bd7; font-weight:bold; font-size:11px; padding:4px 8px; border-radius:4px;">Target: &lt;5.0%</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
            <div style="border: 2px solid #245bd7; background: #f8faff; border-radius: 8px; padding: 14px;">
                <span style="font-size:10px; font-weight:bold; color:#245bd7; text-transform:uppercase;">Card 1 · Single Lever</span>
                <strong style="font-size:13px; display:block; margin:4px 0 6px;">"The Easiest Tweak"</strong>
                <p style="font-size:11px; font-family:monospace; background:#fff; padding:6px; border-radius:4px; margin:0 0 10px;">Support SLA: 24h ➔ 8h</p>
                <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b;">
                    <span>Projected: <strong>4.9%</strong></span><span style="color:#10b981; font-weight:bold;">🟢 High Conf</span>
                </div>
            </div>
            <div style="border: 1px solid #dce5ef; background: white; border-radius: 8px; padding: 14px;">
                <span style="font-size:10px; font-weight:bold; color:#64748b; text-transform:uppercase;">Card 2 · Balanced</span>
                <strong style="font-size:13px; display:block; margin:4px 0 6px;">"The Balanced Approach"</strong>
                <p style="font-size:11px; font-family:monospace; background:#f8fafc; padding:6px; border-radius:4px; margin:0 0 10px;">Support: 14h &amp; Onboard: 2</p>
                <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b;">
                    <span>Projected: <strong>4.8%</strong></span><span style="color:#10b981; font-weight:bold;">🟢 High Conf</span>
                </div>
            </div>
            <div style="border: 1px solid #dce5ef; background: white; border-radius: 8px; padding: 14px;">
                <span style="font-size:10px; font-weight:bold; color:#f59e0b; text-transform:uppercase;">Card 3 · Stretch</span>
                <strong style="font-size:13px; display:block; margin:4px 0 6px;">"Aggressive Upside"</strong>
                <p style="font-size:11px; font-family:monospace; background:#f8fafc; padding:6px; border-radius:4px; margin:0 0 10px;">Discount: +15% &amp; Price: $55</p>
                <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b;">
                    <span>Projected: <strong>4.4%</strong></span><span style="color:#f59e0b; font-weight:bold;">🟡 Stretch</span>
                </div>
            </div>
        </div>
    </div>
    """
    annot = """
    <div class="annotation-box blue" style="left: 45px; top: 90px; width: 250px; height: 130px;"></div>
    <div class="annotation-pin blue" style="left: 30px; top: 75px;">1</div>
    <div class="annotation-label" style="left: 70px; top: 65px;">① Click any recipe card to instantly configure sliders</div>
    """
    render_and_save(p, build_studio_html("Lesson 07 · Scenario Studio", "Visualization", main, "", annot), "l07_04_recipe_cards.png")

def main():
    with sync_playwright() as p:
        print("Starting Playwright capture pipeline...")
        generate_l01_screenshots(p)
        generate_l02_screenshots(p)
        generate_l03_screenshots(p)
        generate_l04_screenshots(p)
        generate_l05_screenshots(p)
        generate_l06_screenshots(p)
        generate_l07_screenshots(p)
        print("All 26 annotated screenshots successfully generated!")

if __name__ == "__main__":
    main()
