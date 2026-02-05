from nicegui import ui

class RightPanel:
    def render(self):
        with ui.column().classes('w-full h-full p-0 gap-0'):
            self._render_header()
            self._render_content()

    def _render_header(self):
        with ui.row().classes('w-full bg-slate-200 p-2 items-center justify-between border-b border-gray-300'):
            ui.label('Intermediate Representation').classes('text-sm font-bold uppercase tracking-wider text-slate-700')
            with ui.row().classes('gap-2'):
                ui.icon('visibility', size='xs').classes('text-slate-500')

    def _render_content(self):
        # Sample data for demonstration
        data = {
            "type": "Program",
            "body": [
                {
                    "type": "FunctionDeclaration",
                    "id": {"type": "Identifier", "name": "main"},
                    "params": [],
                    "body": {
                        "type": "BlockStatement",
                        "body": []
                    }
                }
            ]
        }
        # 'readOnly': True prevents editing
        # on_select callback to notify on node clicks
        ui.json_editor({'content': {'json': data}, 'readOnly': True},
                       on_select=lambda e: ui.notify(f'Selected: {e.selection}')
                       ).classes('w-full h-full p-2 bg-slate-50 border-none')
