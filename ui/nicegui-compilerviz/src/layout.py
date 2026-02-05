from nicegui import ui
from .sidebar import Sidebar
from .left_panel import LeftPanel
from .right_panel import RightPanel

def create_layout():
    """Sets up the main application layout"""
    
    # Instantiate components
    sidebar = Sidebar()
    left_panel = LeftPanel()
    right_panel = RightPanel()

    # 1. Main Header
    with ui.header(elevated=True).classes('bg-slate-900 text-white h-14 items-center gap-4'):
        ui.button(on_click=sidebar.toggle, icon='menu').props('flat color=white dense round')
        ui.label('NiceGUI Compiler Viz').classes('text-xl font-bold tracking-tight')

    # 2. Left Sidebar (Collapsible)
    sidebar.render()

    # 3. Main Split Content
    with ui.splitter(value=50).classes('w-full h-[calc(100vh-3.5rem)]') as splitter:
        with splitter.before:
            left_panel.render()
        with splitter.after:
            right_panel.render()
