from nicegui import ui

class Sidebar:
    def __init__(self):
        self.drawer = None

    def toggle(self):
        if self.drawer:
            self.drawer.toggle()

    def render(self):
        with ui.left_drawer(value=False).classes('bg-slate-100 border-r border-gray-200') as self.drawer:
            with ui.column().classes('w-full p-4 gap-4'):
                ui.label('Configuration').classes('text-xs font-bold uppercase text-slate-500')
                ui.select(['Release', 'Debug'], value='Release', label='Configuration').classes('w-full')
                ui.select(['x64', 'ARM64'], value='x64', label='Platform').classes('w-full')
                
                ui.separator()
                
                ui.label('Links').classes('text-xs font-bold uppercase text-slate-500')
        return self.drawer
