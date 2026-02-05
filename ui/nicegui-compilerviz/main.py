from nicegui import ui
from src.layout import create_layout

@ui.page('/')
def main_page():
    create_layout()

# Initialize the app with a dark mode capable theme if needed, 
# but for now standard setup.
# reload=False is often good for ensuring state doesn't get weird during dev if not needed,
# but default is True which is fine.
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='Compiler Viz', port=8080)
