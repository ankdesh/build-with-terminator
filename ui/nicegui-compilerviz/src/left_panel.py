from nicegui import ui

class LeftPanel:
    def render(self):
        with ui.column().classes('w-full h-full p-0 gap-0'):
            self._render_header()
            self._render_content()

    def _render_header(self):
        with ui.row().classes('w-full bg-slate-200 p-2 items-center justify-between border-b border-gray-300'):
            ui.label('Source Code').classes('text-sm font-bold uppercase tracking-wider text-slate-700')
            with ui.row().classes('gap-2'):
                ui.icon('code', size='xs').classes('text-slate-500')

    def _render_content(self):
        # Using a full-height, full-width textarea for code input
        ui.textarea(placeholder='// Enter your code here...').classes(
            'w-full h-full p-2 font-mono text-sm border-none focus:outline-none'
        ).props('resize-none borderless')
