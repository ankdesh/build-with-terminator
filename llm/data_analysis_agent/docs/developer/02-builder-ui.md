# Builder UI components

## Entry points and ownership

[main.tsx](../../frontend/src/main.tsx) mounts `BuilderApp`. [runtime.main.tsx](../../frontend/src/runtime.main.tsx) mounts `RuntimeApp`. Both use the same CSS and result renderer. [vite.config.ts](../../frontend/vite.config.ts) produces separate builder and runtime asset directories.

| Component | Owns | Direct dependencies | Does not own |
| --- | --- | --- | --- |
| [BuilderApp](../../frontend/src/BuilderApp.tsx) | Project selection; navigation; workspace requests; dock; job status; settings; acceptance/history | React, project API helpers, StageCanvas, PropertiesPanel, Dashboard, StageInternalsCard, AIStageCreatorBar, settings/profile components | Pipeline execution or artifact storage |
| [StageCanvas](../../frontend/src/components/StageCanvas.tsx) | Four stage columns; selection; derived connections; status display; direct page jump; deletion request | Stage/workspace types, React, icons | Creating Python stages or arbitrary graph connections |
| [StageInternalsCard](../../frontend/src/components/StageInternalsCard.tsx) | Stage internals inspection and configuration; title and rationale; inputs/outputs flow; Python code view and edit; cleanup impact stats; table/metric result preview; AI actions (refine, explain, fix) | React, DataTableViewer, workspace and run types | Pipeline execution or server-side sandbox management |
| [AIStageCreatorBar](../../frontend/src/components/AIStageCreatorBar.tsx) | Interactive stage creation prompt input; tailored suggestion chips; manual stage trigger | React, Lucide icons | Direct execution or saving without chat review |
| [PropertiesPanel](../../frontend/src/components/PropertiesPanel.tsx) | Fields for the selected input, executable step, or widget | SettingsFields, workspace and run types | Project-wide settings |
| [SettingsFields](../../frontend/src/components/SettingsFields.tsx) | Commit-on-blur fields; parameter labels, defaults, bounds | React, workspace and run types | Calculations or server validation |
| [Dashboard](../../frontend/src/components/Dashboard.tsx) | Shared widgets; desktop grid; designer selection; drag/resize; keyboard movement | React Grid Layout, ChartViewer, DataTableViewer | Fetching project state or running Python |
| [ChartViewer](../../frontend/src/components/ChartViewer.tsx) | ECharts instance, resizing, chart defaults, PNG action | ECharts, chartExport, icons | Computing analytical values |
| [DataTableViewer](../../frontend/src/components/DataTableViewer.tsx) | Preview table and CSV action | Table types and caller-supplied export callback | Reconstructing full CSV from the preview |
| [RuntimeApp](../../frontend/src/RuntimeApp.tsx) | Dashboard use, CSV upload, controls, refresh/cancel, runtime events | React, Dashboard, DashboardControls, runtime API helpers | Chat, workspace editing, project history |

Stages and logic can be created interactively through AI chat or directly configured. Dedicated pages for Data cleaning and Analysis expose the complete internals of each stage (Python code, configuration options, input/output contracts, cleanup verification, and output tables).

## Navigation and dedicated stage pages

The builder provides dedicated pages for each stage of the analysis pipeline alongside high-level overview views:
1. **Pipeline**: Shows the end-to-end flow with SVG connection curves, stage status badges, and quick links to open dedicated stage pages.
2. **Data input**: Manages source CSV upload, business context, input schema contract, and descriptive profiling.
3. **Data cleaning**: Dedicated page for data cleaning stages, featuring the `AIStageCreatorBar` for interactive AI generation, full stage internals inspection (`StageInternalsCard`), Python script editor, cleanup impact statistics (rows and missing cells before/after), and cleaned data preview tables.
4. **Analysis**: Dedicated page for analytical and aggregation stages, featuring the `AIStageCreatorBar`, stage internals cards, Python calculation editor, parameter bindings, scalar metrics, and resulting tables.
5. **Visualization**: Dedicated page for dashboard presentation, interactive widget creation with AI, 12-column grid layout customization, and scenario control parameters.
6. **History**: Accepted application downloads and version rollback.

## Settings locations

| Setting | Location | Save effect |
| --- | --- | --- |
| Project name | Top-bar project name | Rename project |
| CSV, business descriptions, column types | Data; Business context; Input contract | Input/logic changes can require Run |
| Stage title, explanation, related control defaults | Selected card → Properties | Depends on the changed property |
| Widget title, unit, number format, standard binding, geometry | Selected visualization → Properties | Presentation validation against saved artifacts |
| Dashboard title and subtitle | Dashboard settings | Presentation update after save |
| All control labels, defaults, bounds | Filters and scenario defaults | Labels are presentation; defaults/bounds affect calculation identity |

`parameters_used` limits related controls shown for a step. It is not an execution permission boundary. Python receives the parameter map, and the engine hashes all values for cache correctness.

## Desktop layout contract

The system uses one 12-column grid. There are no tablet/phone layouts or device preview modes. Builder minimum width is 1100 CSS pixels; target minimum width is 1000; dashboard content minimum width is 900. Narrower windows use scrolling.

Widgets store `layout={x,y,w,h}`. `x` is zero-based, and `x+w` must not exceed 12. Legacy width 1 maps to 6 columns; width 2 maps to 12 when explicit geometry is absent. Designer drag/resize saves committed geometry. Alt plus arrow keys moves a focused widget. Properties provides numeric position and size fields.

The designer wraps the shared renderer with editing controls. The target and exported app use it for viewing. Do not introduce an independent target chart implementation; it would cause design/runtime drift.

## Request and event behavior

[projects.ts](../../frontend/src/lib/projects.ts) supplies shared request helpers and frontend contracts. `BuilderApp` listens to project events. `RuntimeApp` listens to runtime events and fetches fresh state. Event messages announce changes; the current state response remains authoritative.

Keep controls as an editable form until Apply. Keep a successful result visible during a new run. Dispose chart instances and observers when their component is removed. PNG export renders a temporary canvas because an SVG-rendered ECharts instance can return SVG despite a requested PNG type.

## Legacy UI

`App.tsx`, `ChatInterface`, `SessionSidebar`, and related session-era components remain in the repository. The active builder entry point imports `BuilderApp`, not `App.tsx`. A package or component present in the source tree is not proof that it is part of the active saved-project UI.

## Stage-aware chat and developer inspection

Selecting a stage or widget opens Chat and sets a visible context strip above the composer. Clear returns to Project context. Properties remains a separate tab. Composer text survives card/tab switches; sending captures the context so in-flight replies cannot be retagged. Project switches clear the composer/context. Deleted stages clear active selection without rewriting transcript labels.

One project transcript shows context and saved-result provenance. Explain, Inputs / outputs, Fix latest error and Next steps populate the composer without sending. Changes appear as review cards with affected stages, linked reasons, before/after fields, Apply and Discard. Applied changes offer Undo and Run and ask again; missing results offer Run and ask again or Skip. Stale reviews cannot be applied.

The launcher flag --developer-mode enables the read-only Inspect tab for all clients. GET /api/capabilities reports the flag. Inspection endpoints enforce it and return 404 when disabled. Inputs/widgets show configuration and links to producer code rather than invented local Python. Inspection contains stage configuration, inputs/outputs, related controls, bounded result previews, provenance and diagnostics; credentials are redacted. JSON download is a same-origin attachment. This feature is not a user permission system or a code editor.

## Select a stage before creating cards

Each of the four stage headings is a button. Empty columns also have a selection button. Both set a `category:input`, `category:cleaning`, `category:analysis` or `category:visualization` chat context. The context stays visible above the chat box. This lets a user request cleaning without first creating a complete pipeline. Selecting an existing card sets the narrower card context. Clear returns to Project context.

The server checks category scope on proposal creation and Apply. Changes in the selected stage type are primary edits. Changes to connected stages or controls need explicit linked reasons. Unrelated edits are rejected. Stage inspection still needs a real card.
