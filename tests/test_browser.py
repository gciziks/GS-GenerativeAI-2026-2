"""Browser contract checks with mocked HTTP responses; no LLM inference."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('width,height',[(1440,1000),(390,844)])
def test_question_keyboard_sources_and_responsive(width,height):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':width,'height':height})
        def route(request):
            path=request.request.url.split('http://guide.test')[-1]
            if path=='/':return request.fulfill(path=str(ROOT/'web/index.html'),content_type='text/html; charset=utf-8')
            if path.startswith('/assets/'):
                return request.fulfill(path=str(ROOT/'web'/path.rsplit('/',1)[-1]))
            if path=='/api/health':return request.fulfill(json={'model_ready':True,'default_configuration':'B','allow_configuration_switch':False})
            if path=='/api/catalogo':return request.fulfill(json={'groups':[{'title':'Atende+','kind':'available','description':'Perguntas documentais','questions':['O que é o Atende+?']}]})
            if path=='/api/fontes':return request.fulfill(json=[])
            if path=='/api/perguntar':return request.fulfill(json={'status':'parcial','answer':'Resposta de teste de interface.','missing_information':['Estado em tempo real não consultado.'],'sources':[{'title':'Documento de teste','publisher':'SPTrans','quote':'<script>alert(1)</script>','url':'https://www.sptrans.com.br/atende/','representation':'curated_summary','retrieved_at':'2026-11-12T00:00:00Z','chunk_id':'fixture'}]})
            request.abort()
        page.route('http://guide.test/**',route)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://guide.test/')
        page.get_by_role('button',name='O que é o Atende+?',exact=True).click()
        expect(page.get_by_label('O que você precisa saber?')).to_have_value('O que é o Atende+?')
        page.keyboard.press('Control+Enter')
        expect(page.locator('#answer-status')).to_have_text('Resposta parcial')
        expect(page.locator('#sources')).to_contain_text('<script>alert(1)</script>')
        expect(page.locator('#missing')).to_contain_text('Estado em tempo real')
        link=page.get_by_role('link',name='Abrir documento oficial (nova aba)')
        expect(link).to_have_attribute('href','https://www.sptrans.com.br/atende/')
        expect(link).to_have_attribute('target','_blank')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
        browser.close()

def test_loading_and_recoverable_http_error():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page()
        def route(request):
            path=request.request.url.split('http://guide.test')[-1]
            if path=='/':return request.fulfill(path=str(ROOT/'web/index.html'),content_type='text/html; charset=utf-8')
            if path.startswith('/assets/'):return request.fulfill(path=str(ROOT/'web'/path.rsplit('/',1)[-1]))
            if path=='/api/health':return request.fulfill(json={'model_ready':True})
            if path=='/api/catalogo':return request.fulfill(status=503,json={'detail':'Catálogo indisponível'})
            if path=='/api/fontes':return request.fulfill(json=[])
            if path=='/api/perguntar':
                assert page.locator('#submit').is_disabled()
                assert page.locator('#submit').get_attribute('aria-busy')=='true'
                return request.fulfill(status=503,json={'detail':'Modelo local indisponível. Tente novamente.'})
            request.abort()
        page.route('http://guide.test/**',route)
        page.goto('http://guide.test/')
        expect(page.locator('#catalog-error')).to_be_visible()
        page.get_by_label('O que você precisa saber?').fill('Minha pergunta livre')
        page.get_by_role('button',name='Consultar informação').click()
        expect(page.locator('#feedback')).to_contain_text('Modelo local indisponível')
        expect(page.get_by_role('button',name='Consultar informação')).to_be_enabled()
        browser.close()
