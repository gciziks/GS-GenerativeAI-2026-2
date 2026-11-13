"""Verificação UI com uma consulta real, executada fora da rodada medida."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evidencias'
def main():
    records=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8002/')
        expect(page.locator('.example-list button')).to_have_count(20)
        button=page.locator('.example-list button').first
        button.click()
        question=page.get_by_label('O que você precisa saber?').input_value()
        with page.expect_response(lambda r:r.url.endswith('/api/perguntar'),timeout=110000) as response:
            page.keyboard.press('Control+Enter')
            expect(page.locator('#submit')).to_be_disabled()
        result=response.value.json()
        expect(page.locator('#answer-status')).to_have_text('Informação encontrada')
        expect(page.locator('#sources details')).not_to_have_count(0)
        assert result['status']=='respondido' and result['sources']
        assert all(s['publisher'] and s['url'].startswith('https://') and s['locator'] and s['source_version'] and s['retrieved_at'] for s in result['sources'])
        for width,height,name in [(1440,1000,'resposta-desktop.png'),(390,844,'resposta-mobile.png')]:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(150)
            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert not overflow
            page.screenshot(path=str(OUT/name),full_page=True)
            records.append({'viewport':[width,height],'horizontal_overflow':overflow,'screenshot':name})
        link=page.locator('#sources a').first
        with page.expect_popup() as popup:link.click()
        official=popup.value
        official.wait_for_load_state('domcontentloaded')
        official_info={'url':official.url,'title':official.title()}
        official.close()
        assert not errors
        browser.close()
    (OUT/'interface-modelo-real.json').write_text(json.dumps({'kind':'live_ui_real_inference','inference_requests':1,'question':question,'configuration':'B','http_response':result,'checks':records,'page_errors':errors,'official_link':official_info,'measured_benchmark':False},ensure_ascii=False,indent=2),encoding='utf8')
    print('UI real desktop/mobile, teclado, loading, evidências e link oficial: OK')
if __name__=='__main__':main()
