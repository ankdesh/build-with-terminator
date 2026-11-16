"""Check Bedrock chat in an isolated browser project. Build the frontend first."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.async_api import async_playwright, expect
from backend.services.project_store import ProjectStore
from pipeline_core.models import ProjectRevision
from scripts.evaluate_agent import REFERENCE
from config import config


async def exercise(url, project_id, output, executable):
    async with async_playwright() as playwright:
        options = {'headless': True}
        if executable: options['executable_path'] = executable
        browser = await playwright.chromium.launch(**options)
        page = await browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            await page.goto(f'{url}/?project={project_id}')
            query=page.get_by_role('textbox',name='Ask about the selected context or request changes')
            await query.fill('Which zone is best?')
            await page.get_by_role('button',name='Send chat message').click()
            card=page.get_by_role('form',name='Clarification required').last
            await card.wait_for(timeout=60000)
            await page.screenshot(path=str(output/'clarification.png'),full_page=True)
            for field in await card.get_by_role('textbox').all():
                await field.fill('Use highest mean value after current cleaning. Only calculate and show the answer; do not save changes.')
            await card.get_by_role('button',name='Continue request').click()
            result=page.get_by_role('region',name='Temporary analysis result').last
            await result.wait_for(timeout=90000)
            await result.scroll_into_view_if_needed()
            await page.screenshot(path=str(output/'result.png'),full_page=True)
            await page.reload()
            await result.wait_for(timeout=30000)
            rules=page.locator('.project-rules')
            await rules.locator('summary').click()
            await rules.get_by_role('textbox',name='New project rule').fill('Best means highest mean value after cleaning.')
            await rules.get_by_role('button',name='Add rule').click()
            await rules.get_by_role('textbox',name='Project rule',exact=True).wait_for()
            await page.reload()
            await rules.locator('summary').click()
            assert await rules.get_by_role('textbox',name='Project rule',exact=True).input_value()=='Best means highest mean value after cleaning.'
            await rules.get_by_role('button',name='Delete rule').click()
            await rules.get_by_role('textbox',name='Project rule',exact=True).wait_for(state='detached')
            await query.fill('Calculate the growth rate.')
            await page.get_by_role('button',name='Send chat message').click()
            await page.get_by_role('button',name='Cancel request',exact=True).wait_for(timeout=60000)
            await page.get_by_role('button',name='Cancel request',exact=True).click()
            await query.wait_for()
            await expect(query).to_be_enabled(timeout=10000)
            assert not errors,errors
            return {'clarification_resume':True,'temporary_result':True,'reload':True,'rules_persist':True,'rules_delete':True,'cancel':True,'browser_errors':errors}
        finally:
            await browser.close()


def main(args):
    if config.llm_provider!='bedrock': raise SystemExit('Browser acceptance requires llm_provider=bedrock')
    output=Path(args.output_dir).resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wps-agent-browser-') as directory:
        root=Path(directory);store=ProjectStore(root/'projects');project_id=store.create()['id']
        source=root/'data.csv';source.write_text('zone,value\nA,10\nA,10\nB,20\nC,\n')
        store.save_dataset(project_id,source,'data.csv',{'row_count':4,'column_count':2,'columns':[{'name':'zone','data_type':'string'},{'name':'value','data_type':'float'}]},'')
        store.save_revision(project_id,ProjectRevision.model_validate(REFERENCE))
        url=f'http://127.0.0.1:{args.port}'
        with (output/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(args.port)],
                env={**os.environ,'WPS_PROJECTS_DIR':str(store.root)},stdout=log,stderr=log,start_new_session=True)
            try:
                deadline=time.monotonic()+30
                while True:
                    if server.poll() is not None: raise RuntimeError('Test server exited. Read server.log.')
                    try:
                        response=httpx.get(url+'/health',timeout=1)
                        if response.is_success: break
                    except httpx.HTTPError: pass
                    if time.monotonic()>deadline: raise RuntimeError('Test server did not start')
                    time.sleep(.1)
                result=asyncio.run(exercise(url,project_id,output,args.browser_executable))
                (output/'result.json').write_text(json.dumps(result,indent=2))
                print(json.dumps(result))
            finally:
                server.terminate()
                try: server.wait(timeout=20)
                except subprocess.TimeoutExpired: server.kill();server.wait(timeout=5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=19091)
    parser.add_argument('--output-dir',default='TEMP_agent_validation/browser')
    parser.add_argument('--browser-executable')
    main(parser.parse_args())
