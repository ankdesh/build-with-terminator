from nicegui import app, ui
import bug_manager

bug_manager.init_dirs()

# Base predefined tags
TAGS = ['bug', 'feature add', 'feature enhance', 'suggestion']

def setup_theme():
    """Sets up the global theme, fonts, and dark mode"""
    ui.add_head_html('''
        <style>
            body { 
                font-family: system-ui, -apple-system, sans-serif; 
                background-color: #0f172a;
                color: #f1f5f9;
            }
            .premium-card { 
                background: rgba(255, 255, 255, 0.7); 
                backdrop-filter: blur(16px); 
                border-radius: 16px; 
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); 
                border: 1px solid rgba(255, 255, 255, 0.4); 
                transition: all 0.3s ease;
            }
            .body--dark .premium-card {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            }
            .bug-item:hover { 
                transform: translateY(-4px); 
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04); 
                border-color: #3b82f6; 
            }
            .body--dark .bug-item:hover {
                border-color: #60a5fa;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4);
            }
            .gradient-text {
                background: linear-gradient(135deg, #2563eb, #7c3aed);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .body--dark .gradient-text {
                background: linear-gradient(135deg, #60a5fa, #a78bfa);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
        </style>
    ''')
    ui.colors(primary='#4f46e5', secondary='#ec4899', accent='#8b5cf6', dark='#0f172a', positive='#10b981', negative='#ef4444', info='#3b82f6', warning='#f59e0b')
    ui.dark_mode(True)

def create_header():
    """Creates a beautiful shared header."""
    with ui.header().classes('w-full flex justify-between items-center py-4 px-8 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md border-b border-gray-200 dark:border-slate-800').props('elevated=false'):
        with ui.row().classes('items-center gap-3 cursor-pointer').on('click', lambda: ui.navigate.to('/')):
            ui.icon('bug_report', size='md').classes('text-indigo-400')
            ui.html('<span class="text-indigo-400 font-extrabold text-2xl tracking-tight">SAF &amp; Sous Chef</span> <span class="text-white font-extrabold text-2xl tracking-tight">BugTracker</span>')
        
        with ui.row().classes('items-center gap-4'):
            ui.button('Report Bug', on_click=lambda: ui.navigate.to('/'), icon='add').props('flat color=primary').classes('font-bold')
            ui.button('View Bugs', on_click=lambda: ui.navigate.to('/bugs'), icon='list').props('flat color=primary').classes('font-bold')

@ui.page('/')
def index():
    setup_theme()
    create_header()

    with ui.column().classes('w-full items-center p-4 sm:p-8 mt-8'):
        with ui.column().classes('w-full max-w-3xl items-center mb-8'):
            ui.label('Capture the issue.').classes('text-5xl font-extrabold gradient-text mb-2')
            ui.label('Help us make things perfect. Report bugs, suggest features, and track progress.').classes('text-lg text-slate-600 dark:text-slate-400 text-center')

        with ui.card().classes('w-full max-w-3xl p-6 sm:p-10 premium-card'):
            ui.label('Report Details').classes('text-xl font-bold mb-6 text-slate-800 dark:text-white border-b border-slate-200 dark:border-slate-700 pb-2 flex items-center gap-2')
            
            # Mandatory fields
            title = ui.input('Title *').classes('w-full mb-5 text-lg font-medium').props('outlined color=primary')
            details = ui.textarea('Details *').classes('w-full mb-5').props('outlined color=primary autogrow')
            
            with ui.row().classes('w-full gap-5 mb-5'):
                # Utilizing chips and `new-value-mode='add-unique'` allows dynamic custom tags!
                tags = ui.select(
                    options=TAGS, 
                    label='Tags (Optional)', 
                    multiple=True,
                    with_input=True,
                    new_value_mode='add-unique'
                ).classes('flex-grow w-full sm:w-auto').props('use-chips outlined color=accent')
                
            with ui.row().classes('w-full gap-5 mb-6'):
                author_name = ui.input('Author Name (Optional)').classes('flex-grow').props('outlined rounded')
                knox_id = ui.input('Knox ID (Optional)').classes('flex-grow').props('outlined rounded')
            
            # File attachment
            attachment = None
            def handle_upload(e):
                nonlocal attachment
                if e.content.size > 10 * 1024 * 1024:
                    ui.notify('File too large! Max 10MB', type='negative')
                    return
                filename = e.name
                target = bug_manager.ATTACHMENTS_DIR / filename
                with open(target, 'wb') as f:
                    f.write(e.content.read())
                attachment = filename
                ui.notify(f"Attached {filename}", type='positive', icon='cloud_done')

            with ui.column().classes('w-full mb-8'):
                ui.label('Attachment').classes('text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2')
                ui.upload(on_upload=handle_upload, max_file_size=10*1024*1024, auto_upload=True, label='Drop file here or click to upload (Max 10MB)', max_files=1).classes('w-full border-2 border-dashed border-indigo-200 dark:border-indigo-900 rounded-xl p-4 bg-indigo-50/50 dark:bg-indigo-900/10 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors')
            
            def submit():
                t = title.value or ''
                d = details.value or ''
                if not t.strip() or not d.strip():
                    ui.notify('Title and Details are mandatory fields!', type='warning', position='top')
                    return
                    
                bug_data = {
                    'title': t,
                    'details': d,
                    'tags': tags.value or [],
                    'author_name': author_name.value or '',
                    'knox_id': knox_id.value or '',
                    'attachment': attachment
                }
                
                bug_id = bug_manager.save_bug(bug_data)
                ui.notify(f"Bug reported successfully!", type='positive', position='top', icon='check_circle')
                
                # Reset form
                title.value = ''
                details.value = ''
                tags.value = []
                author_name.value = ''
                knox_id.value = ''
            
            with ui.row().classes('w-full justify-end'):
                ui.button('Submit Report', on_click=submit, icon='send').classes('py-3 px-8 text-white font-bold rounded-xl shadow-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 transition-all transform hover:scale-105')


@ui.page('/bugs')
def bugs_list():
    setup_theme()
    create_header()
    
    with ui.column().classes('w-full items-center p-4 sm:p-8 mt-4'):
        with ui.column().classes('w-full max-w-5xl mb-8'):
            ui.label('Issue Hub').classes('text-4xl font-extrabold gradient-text mb-1')
            ui.label('View and discuss all reported bugs and features.').classes('text-slate-500 dark:text-slate-400 font-medium')
    
        bugs = bug_manager.load_bugs()
        
        if not bugs:
            with ui.card().classes('w-full max-w-5xl p-16 items-center justify-center premium-card text-center'):
                ui.icon('auto_awesome', color='primary', size='80px').classes('mb-6 opacity-80')
                ui.label('Inbox Zero!').classes('text-3xl font-bold text-slate-800 dark:text-white mb-2')
                ui.label('No issues currently tracked. Great job!').classes('text-lg text-slate-500 dark:text-slate-400')
            return

        with ui.column().classes('w-full max-w-5xl space-y-4'):
            for i, bug in enumerate(bugs):
                with ui.card().classes('w-full p-6 premium-card bug-item cursor-pointer flex flex-row items-center justify-between group').on('click', lambda b=bug: open_bug_dialog(b)):
                    with ui.column().classes('flex-grow mr-6'):
                        with ui.row().classes('items-center gap-3 mb-2'):
                            ui.label(bug.get('title', 'Unknown Title')).classes('text-xl font-bold text-slate-800 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors')
                            
                            for tag in bug.get('tags', []):
                                if isinstance(tag, str):
                                    tag_lower = tag.lower()
                                    bg_color = 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' if tag_lower == 'bug' else 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' if tag_lower.startswith('feat') else 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                                    ui.label(tag.upper()).classes(f'text-[10px] px-2.5 py-1 rounded-md font-bold tracking-wider {bg_color}')
                                
                        author = bug.get('author_name') or 'Anonymous'
                        date = bug.get('created_at', '')[:10]
                        
                        with ui.row().classes('items-center gap-2 text-sm text-slate-500 dark:text-slate-400'):
                            ui.icon('person', size='16px')
                            ui.label(author).classes('font-medium')
                            ui.label('•')
                            ui.icon('calendar_today', size='14px')
                            ui.label(date)
                    
                    with ui.row().classes('items-center gap-5'):
                        cmt_count = len(bug.get('comments', []))
                        with ui.row().classes(f'items-center gap-1.5 {"text-indigo-600 dark:text-indigo-400 font-bold" if cmt_count > 0 else "text-slate-400 dark:text-slate-600 font-medium"}'):
                            ui.icon('forum', size='sm')
                            ui.label(str(cmt_count))
                            
                        if bug.get('attachment'):
                            ui.icon('attach_file', size='sm').classes('text-slate-400')
                            
                        # Chevron for visual cue
                        ui.icon('chevron_right', size='md').classes('text-slate-300 dark:text-slate-600 group-hover:text-indigo-500 transition-colors transform group-hover:translate-x-1')

def open_bug_dialog(bug):
    # Setup Dialog Theme overrides inside dialog context
    with ui.dialog().classes('backdrop-blur-sm') as dialog, ui.card().classes('w-[800px] max-w-full p-0 overflow-hidden premium-card'):
        
        # Header banner
        with ui.row().classes('w-full justify-between items-start p-6 bg-slate-800/50 border-b border-slate-700'):
            with ui.column().classes('max-w-[85%]'):
                ui.label(bug.get('title')).classes('text-3xl font-extrabold text-white mb-2 leading-tight')
                with ui.row().classes('items-center gap-3 text-sm'):
                    with ui.row().classes('items-center gap-1 text-slate-300 font-medium bg-slate-700/50 px-3 py-1 rounded-full'):
                        ui.icon('face', size='16px')
                        ui.label(bug.get('author_name', 'Anonymous'))
                    if bug.get('knox_id'):
                        ui.label(f"@{bug.get('knox_id')}").classes('text-slate-400 font-mono')
                    ui.label(f"• {bug.get('created_at', '')[:16].replace('T', ' ')}").classes('text-slate-400')
            ui.button(icon='close', on_click=dialog.close).props('flat round size=md').classes('text-slate-400 hover:text-white transition-colors bg-black/20')
            
        with ui.column().classes('w-full p-6 space-y-6'):
            # Tags section
            if bug.get('tags'):
                with ui.row().classes('w-full gap-2'):
                    for tag in bug.get('tags'):
                        if isinstance(tag, str):
                            ui.label(tag).classes('text-xs px-3 py-1 bg-indigo-900/40 text-indigo-300 rounded-lg border border-indigo-800/50 font-bold uppercase tracking-wide')
            
            # Details Body
            with ui.column().classes('w-full'):
                ui.label('Description').classes('text-sm font-bold text-slate-400 uppercase tracking-wider mb-2')
                with ui.card().classes('w-full bg-slate-800/30 border border-slate-700/50 p-5 rounded-xl shadow-sm'):
                    ui.markdown(bug.get('details', '')).classes('text-slate-200 text-base leading-relaxed break-words')
                    
            # Attachment
            if bug.get('attachment'):
                with ui.row().classes('w-full items-center p-4 bg-slate-800/40 rounded-xl border border-slate-700/50 mt-2 hover:border-indigo-600/50 transition-colors cursor-pointer group'):
                    with ui.row().classes('p-2 bg-indigo-900/50 rounded-lg mr-3 group-hover:scale-110 transition-transform'):
                        ui.icon('insert_drive_file', size='sm').classes('text-indigo-400')
                    with ui.column():
                        ui.label('Attached File').classes('text-xs font-bold text-slate-400')
                        ui.label(f"{bug.get('attachment')}").classes('text-sm font-semibold text-slate-200')

            ui.separator().classes('my-2 border-slate-700/50')
            
            # Comments Section
            with ui.column().classes('w-full'):
                ui.label('Discussion').classes('text-lg font-bold text-white mb-4 flex items-center gap-2')
                comments_container = ui.column().classes('w-full space-y-4 mb-6')
                
                def render_comments():
                    comments_container.clear()
                    latest_bug = bug_manager.get_bug(bug.get('id'))
                    comments = latest_bug.get('comments', []) if latest_bug else []
                    
                    if not comments:
                        with comments_container:
                            with ui.row().classes('w-full items-center justify-center py-6 bg-slate-800/30 rounded-xl border border-dashed border-slate-700'):
                                ui.label('Be the first to comment on this issue.').classes('text-slate-500 font-medium')
                    else:
                        for c in comments:
                            with comments_container:
                                with ui.row().classes('w-full gap-4'):
                                    # Avatar placeholder
                                    initial = c.get('author', 'A')[0].upper()
                                    with ui.column().classes('w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-full items-center justify-center flex-shrink-0 shadow-md'):
                                        ui.label(initial).classes('text-white font-bold text-lg')
                                        
                                    with ui.column().classes('flex-grow bg-slate-800 p-4 rounded-2xl rounded-tl-none border border-slate-700 shadow-sm'):
                                        with ui.row().classes('justify-between w-full items-center mb-1'):
                                            ui.label(c.get('author', 'Anonymous')).classes('font-bold text-sm text-white')
                                            ui.label(c.get('timestamp', '')[:16].replace('T', ' ')).classes('text-xs text-slate-500 font-mono')
                                        ui.label(c.get('text', '')).classes('text-slate-300 text-sm')
                                    
                render_comments()
                
                # New Comment Form
                with ui.column().classes('w-full bg-slate-800/80 p-5 rounded-2xl border border-slate-700 shadow-inner'):
                    with ui.row().classes('w-full gap-3 mb-3'):
                        comment_author = ui.input('Your Name').classes('w-1/3').props('outlined dense bg-slate-900 text-white')
                        new_comment = ui.input('Add to the discussion...').classes('flex-grow').props('outlined dense bg-slate-900 text-white')
                    
                    def submit_comment():
                        text = new_comment.value
                        author = comment_author.value
                        if text and text.strip():
                            success = bug_manager.add_comment(bug['id'], author, text)
                            if success:
                                new_comment.value = ''
                                render_comments()
                                ui.notify('Message posted!', type='positive')
                            else:
                                ui.notify('Error saving comment', type='negative')
                        else:
                            ui.notify('Please write something first', type='warning')
                            
                    with ui.row().classes('w-full justify-end'):
                        ui.button('Post Comment', icon='send', on_click=submit_comment).classes('bg-indigo-600 hover:bg-indigo-700 text-white shadow-md rounded-xl px-6 font-bold transition-transform transform hover:-translate-y-0.5')
                
    dialog.open()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='*SAF & Sous Chef* BugTracker', port=8080)
