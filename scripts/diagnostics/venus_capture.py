"""Capture an unmodified local checkout for separated UI-Venus adapter diagnostics."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

async def capture(args):
    import httpx
    from playwright.async_api import async_playwright
    from backend.browser.security import allowed_url
    if urlsplit(args.base_url).hostname not in {'127.0.0.1','localhost','::1'}:
        raise ValueError('Diagnostics capture accepts a local benchmark server only')
    args.output.mkdir(parents=True,exist_ok=True)
    async with httpx.AsyncClient() as client:
        result=await client.post(args.base_url.rstrip('/')+'/api/preview/'+args.scenario)
        result.raise_for_status();preview=result.json()
    origin=preview['url'].split('/checkout/')[0]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1280,'height':900},service_workers='block')
        async def route(request):
            if allowed_url(request.request.url,origin,preview['token']): await request.continue_()
            else: await request.abort()
        await context.route('**/*',route)
        page=await context.new_page()
        await page.goto(preview['url']);await page.wait_for_timeout(500)
        await page.screenshot(path=str(args.output/'input.png'))
        await browser.close()
    (args.output/'preview.json').write_text(json.dumps(preview,indent=2)+'\n')
    print(json.dumps({'screenshot':str(args.output/'input.png'),'public_task':str(args.output/'preview.json'),'viewport':[1280,900]}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--scenario',default='V3-G01')
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(capture(parser.parse_args()))
