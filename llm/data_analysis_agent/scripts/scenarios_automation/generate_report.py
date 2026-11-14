import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TEMP_REPORTS_DIR, SCREENSHOTS_DIR, ensure_temp_dirs

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WPS-AI Practical Scenarios Verification & Usability Report</title>
  <style>
    :root {
      --primary: #2563eb;
      --primary-dark: #1d4ed8;
      --primary-light: #eff6ff;
      --success: #16a34a;
      --success-light: #f0fdf4;
      --warning: #d97706;
      --warning-light: #fffbeb;
      --danger: #dc2626;
      --danger-light: #fef2f2;
      --slate-50: #f8fafc;
      --slate-100: #f1f5f9;
      --slate-200: #e2e8f0;
      --slate-300: #cbd5e1;
      --slate-600: #475569;
      --slate-700: #334155;
      --slate-800: #1e293b;
      --slate-900: #0f172a;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: var(--slate-800);
      background: #f8fafc;
      line-height: 1.6;
    }
    header.hero {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
      color: white;
      padding: 48px 32px;
      border-bottom: 1px solid var(--slate-700);
    }
    .hero-content {
      max-width: 1200px;
      margin: 0 auto;
    }
    .hero-tag {
      display: inline-block;
      background: rgba(37, 99, 235, 0.4);
      color: #93c5fd;
      border: 1px solid rgba(147, 197, 253, 0.3);
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 16px;
    }
    h1 { font-size: 32px; font-weight: 700; margin-bottom: 12px; line-height: 1.25; }
    .hero p { font-size: 16px; color: #cbd5e1; max-width: 800px; }
    .meta-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      font-size: 14px;
      color: #94a3b8;
    }
    .meta-bar strong { color: white; }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 36px 24px;
    }
    nav.toc {
      background: white;
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 36px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    nav.toc h3 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--slate-600); margin-bottom: 12px; }
    nav.toc ul { display: flex; flex-wrap: wrap; gap: 12px 24px; list-style: none; }
    nav.toc a { color: var(--primary); text-decoration: none; font-weight: 500; font-size: 14px; }
    nav.toc a:hover { text-decoration: underline; color: var(--primary-dark); }
    
    .section-card {
      background: white;
      border: 1px solid var(--slate-200);
      border-radius: 16px;
      padding: 32px;
      margin-bottom: 36px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .section-card h2 {
      font-size: 24px;
      font-weight: 700;
      color: var(--slate-900);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .section-subtitle {
      color: var(--slate-600);
      font-size: 15px;
      margin-bottom: 24px;
    }
    .scorecard {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 20px;
      margin: 24px 0;
    }
    .score-tile {
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      padding: 20px;
      background: var(--slate-50);
    }
    .score-tile.success { border-left: 5px solid var(--success); }
    .score-tile.warning { border-left: 5px solid var(--warning); }
    .score-tile .tile-title { font-size: 13px; text-transform: uppercase; font-weight: 700; color: var(--slate-600); }
    .score-tile .tile-status { font-size: 20px; font-weight: 700; margin: 6px 0; display: flex; align-items: center; gap: 8px; }
    .score-tile.success .tile-status { color: var(--success); }
    .score-tile.warning .tile-status { color: var(--warning); }
    .score-tile p { font-size: 13px; color: var(--slate-600); line-height: 1.4; }

    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-success { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .badge-warning { background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge-danger { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .badge-info { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }

    table.verification-table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 14px;
    }
    table.verification-table th, table.verification-table td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--slate-200);
      text-align: left;
    }
    table.verification-table th {
      background: var(--slate-50);
      font-weight: 600;
      color: var(--slate-700);
    }
    table.verification-table tr:hover { background: #f8fafc; }
    table.verification-table td.num { font-variant-numeric: tabular-nums; text-align: right; }
    table.verification-table th.num { text-align: right; }

    .step-box {
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      background: white;
    }
    .step-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .step-title {
      font-size: 17px;
      font-weight: 650;
      color: var(--slate-900);
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .step-number {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      background: var(--primary-light);
      color: var(--primary);
      border-radius: 50%;
      font-size: 13px;
      font-weight: 700;
    }
    .step-desc {
      font-size: 14px;
      color: var(--slate-600);
      margin-bottom: 16px;
      line-height: 1.5;
    }
    .gallery {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }
    .shot-card {
      border: 1px solid var(--slate-200);
      border-radius: 8px;
      overflow: hidden;
      background: var(--slate-50);
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .shot-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .shot-card img {
      width: 100%;
      height: 220px;
      object-fit: cover;
      object-position: top;
      display: block;
      border-bottom: 1px solid var(--slate-200);
      cursor: pointer;
    }
    .shot-caption {
      padding: 10px 12px;
      font-size: 12px;
      color: var(--slate-700);
      font-weight: 500;
      background: white;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .shot-caption a {
      color: var(--primary);
      text-decoration: none;
      font-size: 11px;
    }
    .shot-caption a:hover { text-decoration: underline; }

    .callout {
      border-radius: 8px;
      padding: 16px 20px;
      margin: 16px 0;
      font-size: 14px;
      line-height: 1.5;
    }
    .callout-info { background: #f0f9ff; border-left: 4px solid #0284c7; color: #075985; }
    .callout-warning { background: #fffbeb; border-left: 4px solid #f59e0b; color: #92400e; }
    .callout-danger { background: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b; }
    .callout-success { background: #f0fdf4; border-left: 4px solid #22c55e; color: #166534; }
    .callout strong { font-weight: 650; }

    pre.code-block {
      background: #0f172a;
      color: #e2e8f0;
      padding: 16px;
      border-radius: 8px;
      font-size: 12.5px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      overflow-x: auto;
      margin: 12px 0;
      line-height: 1.45;
    }

    .recommendations-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 20px;
      margin-top: 20px;
    }
    .rec-card {
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      padding: 20px;
      background: white;
    }
    .rec-card h3 { font-size: 16px; font-weight: 700; color: var(--slate-900); margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .rec-card p { font-size: 13.5px; color: var(--slate-600); line-height: 1.5; }
    
    footer.page-footer {
      text-align: center;
      padding: 32px;
      color: var(--slate-600);
      font-size: 13px;
      border-top: 1px solid var(--slate-200);
      margin-top: 48px;
    }

    /* Modal / Lightbox */
    .lightbox {
      display: none;
      position: fixed;
      z-index: 9999;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.85);
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .lightbox.active { display: flex; }
    .lightbox img {
      max-width: 95%;
      max-height: 90vh;
      border-radius: 8px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .lightbox-close {
      position: absolute;
      top: 20px;
      right: 20px;
      color: white;
      font-size: 32px;
      cursor: pointer;
      font-weight: 700;
    }
  </style>
</head>
<body>

<header class="hero">
  <div class="hero-content">
    <span class="hero-tag">System Verification & UX Audit</span>
    <h1>WPS-AI Practical Scenarios: Visual Execution & Evaluation Report</h1>
    <p>Comprehensive step-by-step validation of three practical scenarios: Energy Cost Tariff Modeling, Small Sales Reporting with Self-Repair, and Daily Rental Moving Average Trend Analysis.</p>
    <div class="meta-bar">
      <div><strong>Platform:</strong> WPS-AI Studio v0.3.1</div>
      <div><strong>Environment:</strong> Linux x86_64, Chrome (Headless 1366x850)</div>
      <div><strong>Active Model:</strong> gpt-6-luna (OpenAI API)</div>
      <div><strong>Audit Date:</strong> November 7, 2026</div>
      <div><strong>Total Screenshots:</strong> 55 Captures</div>
    </div>
  </div>
</header>

<div class="container">

  <nav class="toc">
    <h3>Quick Navigation</h3>
    <ul>
      <li><a href="#executive-summary">1. Executive Summary & Scorecard</a></li>
      <li><a href="#scenario-1">2. Scenario 1: Compare Energy Costs</a></li>
      <li><a href="#scenario-2">3. Scenario 2: Build a Small Sales Report</a></li>
      <li><a href="#scenario-3">4. Scenario 3: Find a Demand Trend</a></li>
      <li><a href="#analysis">5. Cross-Scenario Usability & System Analysis</a></li>
      <li><a href="#recommendations">6. Actionable Engineering Recommendations</a></li>
    </ul>
  </nav>

  <!-- SECTION 1: EXECUTIVE SUMMARY -->
  <section id="executive-summary" class="section-card">
    <h2>1. Executive Summary & Scorecard</h2>
    <p class="section-subtitle">Visual testing through full browser automation to test end-to-end functionality, design, numerical precision, and error recovery.</p>

    <div class="scorecard">
      <div class="score-tile success">
        <div class="tile-title">Scenario 1 (01-energy-costs.md)</div>
        <div class="tile-status">100% Passed <span class="badge badge-success">Flawless</span></div>
        <p>Pre-packaged example loaded instantly. Fast 1.2s run. All kWh and cost formulas verified across Price and Zone variations.</p>
      </div>
      <div class="score-tile warning">
        <div class="tile-title">Scenario 2 (02-sales-report.md)</div>
        <div class="tile-status">100% Recovered <span class="badge badge-warning">Repaired via Chat</span></div>
        <p>Discovered initial code error (<code>StringMethods.startswith(case=False)</code>). Successfully repaired using one prompt in 10s. All 7 checks passed with precision.</p>
      </div>
      <div class="score-tile success">
        <div class="tile-title">Scenario 3 (03-demand-trend.md)</div>
        <div class="tile-status">100% Passed <span class="badge badge-success">First Run Pass</span></div>
        <p>731 rows processed. 7-day trailing moving average calculated. ECharts dual-series line chart and evidence Q&amp;A validated with 100% numerical accuracy.</p>
      </div>
    </div>

    <div class="callout callout-info">
      <strong>Key Finding:</strong> The platform demonstrates exceptional resilience. When an edge case in Python/Pandas syntax caused a runtime failure during Scenario 2, the built-in self-correction loop diagnosed the worker logs and repaired the workspace in <strong>10 seconds</strong>, producing an approved, working dashboard that matched all expected financial numbers.
    </div>
  </section>

  <!-- SECTION 2: SCENARIO 1 -->
  <section id="scenario-1" class="section-card">
    <h2>2. Scenario 1: Compare Energy Costs</h2>
    <p class="section-subtitle">Goal: Evaluate tariff assumptions for measured electricity usage without model access.</p>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">1</span> Load Pre-built Energy Example &amp; Inspect Pipeline</div>
        <span class="badge badge-success">Passed</span>
      </div>
      <p class="step-desc">Selecting "Load energy example" from the sidebar created the project workspace with 4 linked stages (Data input &rarr; Data cleaning &rarr; Analysis &rarr; Visualization). Pre-cleaned dataset consists of 360 rows.</p>
      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s1_01_loaded_example.png" alt="Energy Example Loaded" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.1 Workspace Loaded</span> <a href="report_screenshots/s1_01_loaded_example.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_02_pipeline_view.png" alt="Pipeline Flow View" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.2 Pipeline Stage Flow</span> <a href="report_screenshots/s1_02_pipeline_view.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_03_data_cleaning.png" alt="Data Cleaning Rule" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.3 Data Cleaning Stage</span> <a href="report_screenshots/s1_03_data_cleaning.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">2</span> Run Workspace &amp; Check Baseline Results</div>
        <span class="badge badge-success">Passed</span>
      </div>
      <p class="step-desc">Run executed in under 2 seconds. The Visualization view rendered KPI metric cards and zone breakdowns matching the documented baseline.</p>
      
      <table class="verification-table">
        <thead>
          <tr>
            <th>Check Metric</th>
            <th>Expected Baseline</th>
            <th>Observed Result</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Input &rarr; Cleaned Readings</td>
            <td>360 &rarr; 360 rows</td>
            <td>360 &rarr; 360 rows</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Total Consumption (kWh)</td>
            <td class="num">19,511.36</td>
            <td class="num">19,511.36</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Estimated Cost (Default 0.15/kWh)</td>
            <td class="num">2,926.70</td>
            <td class="num">2,926.70</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Zone-A Usage</td>
            <td class="num">5,132.22 kWh</td>
            <td class="num">5,132.22 kWh</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Zone-B Usage</td>
            <td class="num">11,837.78 kWh</td>
            <td class="num">11,837.78 kWh</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Zone-C Usage</td>
            <td class="num">2,541.36 kWh</td>
            <td class="num">2,541.36 kWh</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
        </tbody>
      </table>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s1_04_run_finished.png" alt="Run Succeeded Banner" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.1 Run Completed (Up to date)</span> <a href="report_screenshots/s1_04_run_finished.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_05_visualization_view.png" alt="Visualization Stage View" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.2 Builder Visualization</span> <a href="report_screenshots/s1_05_visualization_view.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">3</span> Interactive Target Dashboard &amp; Scenario Testing</div>
        <span class="badge badge-success">Passed</span>
      </div>
      <p class="step-desc">Target service started on port 8101. Tested changing Price per kWh to 0.20 and filtering by Zone-A.</p>
      
      <table class="verification-table">
        <thead>
          <tr>
            <th>Scenario Action</th>
            <th>Expected Total kWh</th>
            <th>Expected Estimated Cost</th>
            <th>Observed Result</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Price per kWh &rarr; 0.20 (All Zones)</td>
            <td class="num">19,511.36</td>
            <td class="num">3,902.27</td>
            <td>19,511.36 kWh &middot; 3,902.27</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Zone &rarr; Zone-A (Price 0.20)</td>
            <td class="num">5,132.22</td>
            <td class="num">1,026.44</td>
            <td>5,132.22 kWh &middot; 1,026.44</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Reset &rarr; All Zones, Price 0.15</td>
            <td class="num">19,511.36</td>
            <td class="num">2,926.70</td>
            <td>19,511.36 kWh &middot; 2,926.70</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
        </tbody>
      </table>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s1_06_dashboard_initial.png" alt="Initial Dashboard" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.1 Dashboard Baseline ($0.15)</span> <a href="report_screenshots/s1_06_dashboard_initial.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_07_filters_drawer_open.png" alt="Filters Drawer Open" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.2 Filters &amp; Scenarios Drawer</span> <a href="report_screenshots/s1_07_filters_drawer_open.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_08_dashboard_price_020.png" alt="Price 0.20 Applied" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.3 Price at 0.20 ($3,902.27)</span> <a href="report_screenshots/s1_08_dashboard_price_020.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_09_dashboard_zoneA_020.png" alt="Zone A Selected" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.4 Zone-A Filter ($1,026.44)</span> <a href="report_screenshots/s1_09_dashboard_zoneA_020.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s1_10_dashboard_reset.png" alt="Dashboard Reset" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.5 Reset Baseline Re-verified</span> <a href="report_screenshots/s1_10_dashboard_reset.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="callout callout-warning">
      <strong>UX Observation (Drawer Dismissal):</strong> Clicking "Apply controls" automatically closes the filter drawer. For rapid parameter exploration (e.g. testing different tariff rate increments), having to repeatedly reopen the drawer introduces unnecessary friction. A "Keep open" pin or sticky filter bar would significantly enhance dashboard usability.
    </div>
  </section>

  <!-- SECTION 3: SCENARIO 2 -->
  <section id="scenario-2" class="section-card">
    <h2>3. Scenario 2: Build a Small Sales Report</h2>
    <p class="section-subtitle">Goal: Turn raw invoice data and business rules into an interactive discount analysis dashboard through natural language chat.</p>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">1</span> Project Setup, CSV Upload &amp; Business Context</div>
        <span class="badge badge-success">Passed</span>
      </div>
      <p class="step-desc">Created "Minimal sales report", uploaded <code>sales_january.csv</code> (10 rows, 5 columns), and defined invoice cancellation business rules.</p>
      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s2_01_new_project_created.png" alt="New Project" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.1 Project Created</span> <a href="report_screenshots/s2_01_new_project_created.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_02_project_renamed.png" alt="Project Renamed" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.2 Title Updated</span> <a href="report_screenshots/s2_02_project_renamed.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_03_csv_uploaded.png" alt="CSV Profile" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.3 Profile: 10 Rows, 5 Cols</span> <a href="report_screenshots/s2_03_csv_uploaded.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_04_business_context_saved.png" alt="Business Context" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.4 Business Rules Stored</span> <a href="report_screenshots/s2_04_business_context_saved.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">2</span> Chat Prompting &amp; Context Switch Discovery</div>
        <span class="badge badge-warning">UX Friction Discovered</span>
      </div>
      <p class="step-desc">When submitting the multi-stage creation prompt while on the Data Input page, the assistant initially rejected the prompt with <code>"Unrelated edits are not allowed in stage context. Use Project context for: project:settings"</code>.</p>
      <div class="callout callout-warning">
        <strong>Context Indicator Ambiguity:</strong> When in Stage context, the UI displays a badge saying <code>Data input &middot; Create or edit stages</code> alongside a button labeled <code>Project</code>. Users easily mistake the button label for the current state rather than the action to switch contexts. Switching to Project context resolved the issue.
      </div>
      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s2_05_chat_project_context.png" alt="Chat Context" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.1 Switched to Project Context</span> <a href="report_screenshots/s2_05_chat_project_context.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_06_prompt_entered.png" alt="Prompt Submitted" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.2 Specification Prompt</span> <a href="report_screenshots/s2_06_prompt_entered.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_07_review_received.png" alt="LLM Review Arrived" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.3 Proposal Review in 32s</span> <a href="report_screenshots/s2_07_review_received.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">3</span> Real-World Error Interception &amp; Automatic Self-Repair</div>
        <span class="badge badge-danger">Real Failure Intercepted</span> &rarr; <span class="badge badge-success">Repaired in 10s</span>
      </div>
      <p class="step-desc">Upon clicking <strong>Apply</strong> and <strong>Run</strong>, the initial generated code failed with a Python runtime exception:</p>
      
      <pre class="code-block">
Traceback (most recent call last):
  File "pipeline_core/worker.py", line 58, in main
    result = PipelineEngine().execute(revision, Path(request["input_path"]), request["parameters"], ...)
  File "<step:clean_sales>", line 4, in mark_valid_sales
  File "pandas/core/strings/accessor.py", line 142, in wrapper
    return func(self, *args, **kwargs)
TypeError: StringMethods.startswith() got an unexpected keyword argument 'case'
      </pre>

      <p class="step-desc"><strong>Root Cause:</strong> The prompt specified <code>InvoiceNo does not start with C (case-insensitive)</code>. The LLM generated <code>df['InvoiceNo'].str.startswith('C', case=False)</code>. In Pandas, <code>startswith</code> does not accept a <code>case</code> parameter (unlike <code>contains</code>).</p>
      
      <p class="step-desc"><strong>Recovery via Troubleshooting Guide:</strong> Prompted chat with: <code>Fix the latest failed run using its logs. Keep the requested business rules. Save the repair; I will select Run.</code></p>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s2_09a_run_error_drawer.png" alt="Run Drawer Error Log" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.1 Error Intercepted in Drawer</span> <a href="report_screenshots/s2_09a_run_error_drawer.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_09b_repair_prompt_sent.png" alt="Repair Prompt Sent" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.2 Log-Aware Repair Sent</span> <a href="report_screenshots/s2_09b_repair_prompt_sent.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_09c_repair_review_card.png" alt="Repair Review Card" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.3 Repair Proposal Arrived (10s)</span> <a href="report_screenshots/s2_09c_repair_review_card.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_09e_run_succeeded.png" alt="Repaired Run Succeeded" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.4 Run Succeeded (1.1s)</span> <a href="report_screenshots/s2_09e_run_succeeded.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">4</span> Dashboard Verification &amp; Business Assumption Testing</div>
        <span class="badge badge-success">100% Passed</span>
      </div>
      
      <table class="verification-table">
        <thead>
          <tr>
            <th>Condition &amp; Target</th>
            <th>Expected Check</th>
            <th>Observed Result</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Baseline (All Countries, 0% Discount)</td>
            <td class="num">Sales Value: 800.00 CU</td>
            <td class="num">800.00 CU</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Baseline Excluded Lines</td>
            <td class="num">3 Lines</td>
            <td class="num">3 Lines</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Baseline Country Totals</td>
            <td>India: 530.00 CU &middot; UK: 270.00 CU</td>
            <td>India: 530.00 &middot; UK: 270.00</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Scenario: 10% Discount (All Countries)</td>
            <td class="num">Scenario Sales: 720.00 CU (Original 800.00)</td>
            <td class="num">720.00 CU (800.00 original)</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Scenario: India Only + 10% Discount</td>
            <td>Sales: 530.00 CU &middot; Scenario: 477.00 CU</td>
            <td>530.00 CU &middot; 477.00 CU</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
          <tr>
            <td>Scenario: India Excluded Lines</td>
            <td class="num">1 Line (C1006 cancelled)</td>
            <td class="num">1 Line</td>
            <td><span class="badge badge-success">Match</span></td>
          </tr>
        </tbody>
      </table>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s2_10_visualization_view.png" alt="Sales Visualization" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.1 Validated Builder Widgets</span> <a href="report_screenshots/s2_10_visualization_view.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_11_dashboard_initial.png" alt="Dashboard Initial" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.2 Target Dashboard Baseline</span> <a href="report_screenshots/s2_11_dashboard_initial.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_13_discount_10_applied.png" alt="10% Discount Applied" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.3 10% Discount (720.00 CU)</span> <a href="report_screenshots/s2_13_discount_10_applied.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_14_india_discount_10.png" alt="India Filter with 10% Discount" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.4 India Filter (477.00 CU)</span> <a href="report_screenshots/s2_14_india_discount_10.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s2_15_dashboard_reset.png" alt="Dashboard Reset" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.5 Reset Complete</span> <a href="report_screenshots/s2_15_dashboard_reset.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>
  </section>

  <!-- SECTION 4: SCENARIO 3 -->
  <section id="scenario-3" class="section-card">
    <h2>4. Scenario 3: Find a Demand Trend</h2>
    <p class="section-subtitle">Goal: Smooth short-term daily swings using a trailing 7-day moving average and test evidence-backed qualitative Q&amp;A.</p>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">1</span> Bike Rental Dataset Import (731 Days)</div>
        <span class="badge badge-success">Passed</span>
      </div>
      <p class="step-desc">Imported <code>bike_daily.csv</code> containing 731 observations covering full calendar years 2011 and 2012.</p>
      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s3_01_new_project_created.png" alt="Demand Project" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.1 Project Created</span> <a href="report_screenshots/s3_01_new_project_created.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_03_csv_uploaded.png" alt="Bike CSV Uploaded" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.2 Profile: 731 Days</span> <a href="report_screenshots/s3_03_csv_uploaded.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_04_business_context_saved.png" alt="Business Context" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>1.3 Moving Average Definition</span> <a href="report_screenshots/s3_04_business_context_saved.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">2</span> Pipeline Generation &amp; First-Run Success</div>
        <span class="badge badge-success">Clean Pass (2.1s Run)</span>
      </div>
      <p class="step-desc">Generated cleaning stage (datetime parsing + calendar year extraction), analysis stage (<code>rolling(7, min_periods=1).mean()</code>), select control (Calendar year), and 4 widgets (Days, Total rentals, Average daily rentals, dual-series line chart).</p>
      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s3_06_review_received.png" alt="Scenario 3 Review" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.1 Review Proposal Arrived (32s)</span> <a href="report_screenshots/s3_06_review_received.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_08_run_completed.png" alt="Run Succeeded" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.2 Run Succeeded First Try (2.1s)</span> <a href="report_screenshots/s3_08_run_completed.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_09_visualization_view.png" alt="Trend Visualization" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>2.3 Dual-Series Line Chart</span> <a href="report_screenshots/s3_09_visualization_view.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">3</span> Yearly Filter Checks &amp; Moving Average Verification</div>
        <span class="badge badge-success">100% Passed</span>
      </div>
      
      <table class="verification-table">
        <thead>
          <tr>
            <th>Calendar Year Filter</th>
            <th>Expected Days</th>
            <th>Expected Total Rentals</th>
            <th>Expected Avg Daily Rentals</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>All Years (2011–2012)</td>
            <td class="num">731</td>
            <td class="num">3,292,679</td>
            <td class="num">4,504.35</td>
            <td><span class="badge badge-success">3,292,679 &middot; 4,504.35</span></td>
          </tr>
          <tr>
            <td>Year 2011 Only</td>
            <td class="num">365</td>
            <td class="num">1,243,103</td>
            <td class="num">3,405.76</td>
            <td><span class="badge badge-success">1,243,103 &middot; 3,405.76</span></td>
          </tr>
          <tr>
            <td>Year 2012 Only</td>
            <td class="num">366 (Leap year)</td>
            <td class="num">2,049,576</td>
            <td class="num">5,599.93</td>
            <td><span class="badge badge-success">2,049,576 &middot; 5,599.93</span></td>
          </tr>
        </tbody>
      </table>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s3_10_dashboard_initial_all.png" alt="Dashboard All Years" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.1 All Years (3.29M Rentals)</span> <a href="report_screenshots/s3_10_dashboard_initial_all.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_12_dashboard_2011.png" alt="Dashboard 2011" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.2 2011 Filter (1.24M Rentals)</span> <a href="report_screenshots/s3_12_dashboard_2011.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_13_dashboard_2012.png" alt="Dashboard 2012" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.3 2012 Filter (2.05M Rentals)</span> <a href="report_screenshots/s3_13_dashboard_2012.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_14_dashboard_reset_all.png" alt="Dashboard Reset" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>3.4 Reset to All Years</span> <a href="report_screenshots/s3_14_dashboard_reset_all.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>

    <div class="step-box">
      <div class="step-header">
        <div class="step-title"><span class="step-number">4</span> Qualitative Evidence Q&amp;A Inspection</div>
        <span class="badge badge-success">Accurate in 6s</span>
      </div>
      <p class="step-desc">Submitted audit question: <em>"Explain how Daily demand calculates its trailing 7-day average. Why is the first value equal to the first day's count? Use the saved calculation and run evidence. Answer only; do not edit the report or run new calculations."</em></p>
      
      <div class="callout callout-success">
        <strong>LLM Response Transcript (6s latency):</strong><br>
        <em>"The saved calculation first sorts the selected data by date, then computes <code>cnt.astype('float64').rolling(7, min_periods=1).mean()</code>. Each value is the mean of the current day’s rental count plus up to 6 preceding days. On day 1 (2011-01-01), there are no earlier days in the window, but <code>min_periods=1</code> allows a valid average using only the 1 available observation. Therefore, the 7-day trailing average on the first day is exactly 985.0, equal to that day's count. This is a retrospective summary of observed values, not a predictive forecast."</em>
      </div>

      <div class="gallery">
        <div class="shot-card">
          <img src="report_screenshots/s3_15_qa_prompt_entered.png" alt="QA Prompt Entered" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.1 Evidence Question Sent</span> <a href="report_screenshots/s3_15_qa_prompt_entered.png" target="_blank">Full size</a></div>
        </div>
        <div class="shot-card">
          <img src="report_screenshots/s3_16_qa_answer_received.png" alt="QA Answer Received" onclick="openLightbox(this.src)">
          <div class="shot-caption"><span>4.2 Precise Non-destructive Answer</span> <a href="report_screenshots/s3_16_qa_answer_received.png" target="_blank">Full size</a></div>
        </div>
      </div>
    </div>
  </section>

  <!-- SECTION 5: CROSS-SCENARIO ANALYSIS -->
  <section id="analysis" class="section-card">
    <h2>5. Cross-Scenario Usability &amp; Architectural Analysis</h2>
    <p class="section-subtitle">Key architectural strengths, performance measurements, and UX friction points identified during visual testing.</p>

    <table class="verification-table">
      <thead>
        <tr>
          <th>Evaluation Dimension</th>
          <th>Observed Characteristic</th>
          <th>Rating</th>
          <th>Technical Insight</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Execution Latency</strong></td>
          <td>Pipeline runs take 1.1s to 2.1s</td>
          <td><span class="badge badge-success">Exceptional</span></td>
          <td>In-memory isolated script execution; Pandas processing handles 731 rows with zero disk I/O bottlenecks.</td>
        </tr>
        <tr>
          <td><strong>LLM Authoring Latency</strong></td>
          <td>30s to 33s for complete multi-stage pipelines</td>
          <td><span class="badge badge-info">Good</span></td>
          <td>Model outputs full Pydantic stage schemas, Python worker functions, and widget specifications in a single pass.</td>
        </tr>
        <tr>
          <td><strong>Self-Repair Loop</strong></td>
          <td>10s turnaround time for error repair</td>
          <td><span class="badge badge-success">Outstanding</span></td>
          <td>Feeding exact worker stderr tracebacks back to the agent enables targeted, 1-line code fixes without losing user context.</td>
        </tr>
        <tr>
          <td><strong>Visualization Architecture</strong></td>
          <td>Zero backend graphics binaries (ECharts client-side)</td>
          <td><span class="badge badge-success">Compliant</span></td>
          <td>Strict adherence to GEMINI.md constitution: backend outputs pure JSON series; React ECharts renders responsive SVGs.</td>
        </tr>
        <tr>
          <td><strong>Context Management UX</strong></td>
          <td>Stage context vs Project context button confusion</td>
          <td><span class="badge badge-warning">Needs Polish</span></td>
          <td>Users editing a stage can easily get blocked when proposing broader changes because the toggle button text looks like a label.</td>
        </tr>
        <tr>
          <td><strong>Dashboard Controls UX</strong></td>
          <td>Off-canvas drawer closes automatically on Apply</td>
          <td><span class="badge badge-warning">Needs Polish</span></td>
          <td>Iterative scenario parameter testing requires re-opening the drawer repeatedly.</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SECTION 6: RECOMMENDATIONS -->
  <section id="recommendations" class="section-card">
    <h2>6. Actionable Engineering Recommendations</h2>
    <p class="section-subtitle">Recommended product enhancements prioritized by user impact and implementation complexity.</p>

    <div class="recommendations-grid">
      <div class="rec-card">
        <h3>1. Auto-Elevate Chat Context</h3>
        <p><strong>Problem:</strong> Submitting a pipeline-wide prompt while in Data Input context results in a hard rejection error banner.<br>
        <strong>Fix:</strong> When the user submits a prompt requiring multiple stages or project settings from within a stage context, provide a 1-click action: <em>"This request modifies multiple stages. [Switch to Project Context &amp; Resubmit]"</em> or auto-elevate scope with notice.</p>
      </div>

      <div class="rec-card">
        <h3>2. Pandas String Method Prompt Guardrail</h3>
        <p><strong>Problem:</strong> Models frequently hallucinate <code>df['col'].str.startswith('X', case=False)</code>.<br>
        <strong>Fix:</strong> In <code>project_agent.py</code> system prompt, add a brief syntax reminder: <em>"Note: pandas <code>str.startswith()</code> does NOT take a <code>case</code> parameter; use <code>.str.upper().str.startswith('X')</code> or <code>.str.contains('^X', case=False)</code>."</em></p>
      </div>

      <div class="rec-card">
        <h3>3. Sticky Filter Toolbar in Target Dashboard</h3>
        <p><strong>Problem:</strong> The "Filters and scenarios" drawer closes immediately on submit, forcing repeated clicks during what-if analysis.<br>
        <strong>Fix:</strong> In <code>RuntimeApp.tsx</code>, add a "Pin filters" option or render an inline filter bar directly above the dashboard widgets when fewer than 4 parameters exist.</p>
      </div>

      <div class="rec-card">
        <h3>4. Clear Scope Badge Typography</h3>
        <p><strong>Problem:</strong> In <code>BuilderApp.tsx</code>, the <code>Project</code> button inside the context bar looks like a state label.<br>
        <strong>Fix:</strong> Change the button label from <code>Project</code> to <code>Switch to Project</code> and show the current scope with an explicit tag: <code>Scope: Stage (Data input)</code>.</p>
      </div>
    </div>
  </section>

</div>

<footer class="page-footer">
  WPS-AI Automated Scenario Verification Report &middot; Generated via Playwright Browser Automation &middot; All 3 Scenarios Executed and Validated
</footer>

<!-- Lightbox Modal -->
<div id="lightbox" class="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">&times;</span>
  <img id="lightbox-img" src="" alt="Enlarged screenshot">
</div>

<script>
  function openLightbox(src) {
    document.getElementById('lightbox-img').src = src;
    document.getElementById('lightbox').classList.add('active');
  }
  function closeLightbox() {
    document.getElementById('lightbox').classList.remove('active');
  }
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeLightbox();
  });
</script>

</body>
</html>
"""

ensure_temp_dirs()

# Ensure all image paths point to local screenshots/ directory inside TEMP_reports/
final_html = html_content.replace('report_screenshots/', 'screenshots/')

report_path_1 = TEMP_REPORTS_DIR / "scenario_execution_report.html"
report_path_1.write_text(final_html, encoding="utf-8")
print(f"Written report: {report_path_1.resolve()} ({len(final_html)} bytes)")

report_path_2 = TEMP_REPORTS_DIR / "index.html"
report_path_2.write_text(final_html, encoding="utf-8")
print(f"Written index: {report_path_2.resolve()} ({len(final_html)} bytes)")

