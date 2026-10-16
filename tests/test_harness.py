"""Browser software regressions. All scorers here are deterministic test doubles."""
import asyncio

import pytest

from backend.browser.v21 import NoProgress, ProgressGuard, observe, page_state, reference_v21
from scenarios.catalog import scenario, task
from tests.test_v21 import SpyControls


class StubCua:
    key = "cua-s1"
    last_metrics = {"backend": "test-double"}

    def __init__(self, predict):
        self.predict = predict
        self.inputs = []

    async def score_fields(self, elements, profile):
        self.inputs.extend(elements)
        return [self.predict(e) for e in elements]


def controls(page):
    ctl = SpyControls(page, limit=100)
    ctl.max_steps = 20
    return ctl


async def run(page, stub, ctl=None):
    ctl = ctl or controls(page)
    await reference_v21(page, task(scenario("V21-G01")), ctl, "cua-s1", stub)
    return ctl


async def test_wrong_email_and_required_skips_stop_after_three_submits(page):
    await page.set_content('''<h2>Details</h2><input id="email" type="email" required aria-label="Receipt email">
      <input id="address" required aria-label="Street"><div role="alert"></div>
      <button onclick="document.querySelector('[role=alert]').textContent='Invalid attempt '+ ++window.attempts">Review details</button>
      <script>window.attempts=0</script>''')
    stub = StubCua(lambda e: {"action": "fill", "value": "Near Sample Park"} if "email" in e["label"] else {"action": "skip"})
    ctl = controls(page)
    with pytest.raises(NoProgress) as error:
        await run(page, stub, ctl)
    assert await page.locator('#email').input_value() == 'Near Sample Park'
    assert await page.locator('#address').input_value() == ''
    assert await page.evaluate('window.attempts') == 3
    assert error.value.diagnostics['validation']
    assert len(ctl.semantic_decisions) == 3  # wrong fill, reobserved value, required skip
    assert all(c['backend'] == 'test-double' for c in ctl.usage.calls)
    assert ctl.usage.calls[0]['outputs'][0]['value'] == 'Near Sample Park'
    assert len([e for e in ctl.events if e[1].get('selection_source') == 'cua-s1']) == 1
    assert len([e for e in ctl.events if e[0] == 'click']) == 3


async def test_actual_state_change_resets_guard_and_cosmetic_noise_does_not(page):
    await page.set_content('<h2>Details</h2><input id="x"><p id="noise">attempt 1</p>')
    before = await page_state(page)
    await page.locator('#noise').evaluate("e=>e.textContent='attempt 2'")
    assert await page_state(page) == before
    guard = ProgressGuard()
    assert guard.observe('submit', before, before) == 1
    await page.locator('#x').fill('wrong but changed')
    after = await page_state(page)
    assert before != after
    assert guard.observe('submit', before, after) == 0
    assert guard.observe('submit', after, after) == 1
    await page.locator('#x').evaluate('e=>e.required=true')
    assert await page_state(page) != after


async def test_failed_submit_reobserves_new_required_field_then_transitions(page):
    await page.set_content('''<h2>Details</h2><button onclick="if(!document.querySelector('input')){this.insertAdjacentHTML('beforebegin', '<input id=new required aria-label=New>')}else if(document.querySelector('input').value==='chosen'){document.body.innerHTML='<h2>Checkout ready</h2>'}">Review details</button>''')
    stub = StubCua(lambda e: {'action':'fill','value':'chosen'})
    ctl = await run(page, stub)
    assert await page.get_by_role('heading', name='Checkout ready').count() == 1
    assert [e[0] for e in ctl.events] == ['click','fill','click']
    assert stub.inputs[0]['label'] == 'New'
    assert ctl.semantic_decisions[0]['execution_status'] == 'executed'


@pytest.mark.parametrize('initial,action,value,expected', [(False,'check',True,True),(True,'check',False,False),(True,'check',True,True),(True,'skip',None,True),(True,'uncheck',None,False)])
async def test_checkbox_decisions_preserve_exact_state(page, initial, action, value, expected):
    await page.set_content(f'<input type="checkbox" id="x" aria-label="Subscribe" {"checked" if initial else ""}><button>Review details</button>')
    stub = StubCua(lambda e: {'action':action,'value':value})
    ctl = controls(page)
    with pytest.raises(NoProgress):
        await run(page,stub,ctl)
    assert await page.locator('#x').is_checked() is expected
    assert stub.inputs[0]['checked'] is initial
    assert len([e for e in ctl.events if e[0]=='check']) == int(initial != expected)


async def test_stale_prediction_is_not_applied_to_replacement_field(page):
    await page.set_content('<input id="same" aria-label="Old"><button>Review details</button>')
    class Mutating(StubCua):
        async def score_fields(self,e,p):
            if e[0]['label']=='Old':
                await page.locator('#same').evaluate('e=>e.outerHTML=\'<input id="same" aria-label="New">\'')
            return await super().score_fields(e,p)
    stub=Mutating(lambda e:{'action':'fill','value':e['label']+' prediction'})
    ctl=controls(page)
    with pytest.raises(NoProgress):
        await run(page,stub,ctl)
    assert await page.locator('#same').input_value() == 'New prediction'
    assert ctl.semantic_decisions[0]['execution_status'] == 'stale_observation'
    assert all(e[1].get('value') != 'Old prediction' for e in ctl.events)


async def test_hidden_fields_and_disabled_controls_are_not_observed(page):
    await page.set_content('<input id="a" style="visibility:hidden"><input id="b" style="opacity:0"><input id="c" disabled><input id="visible">')
    assert [r['handle'] for r in await observe(page.main_frame)] == ['visible']


async def test_invalid_select_is_retained_but_not_repeated(page):
    await page.set_content('<select id="s" aria-label="Choice"><option value="a">A</option></select><button>Review details</button>')
    stub = StubCua(lambda e:{'action':'fill','value':'Not an option'})
    ctl=controls(page)
    with pytest.raises(NoProgress):
        await run(page,stub,ctl)
    assert len(stub.inputs)==1
    assert await page.locator('#s').input_value()=='a'
    assert ctl.semantic_decisions[0]['execution_status']=='invalid_selection'


async def test_browser_failure_has_one_failed_record_per_attempt(page):
    await page.set_content('<input id="x" readonly aria-label="Readonly">')
    stub=StubCua(lambda e:{'action':'fill','value':'cannot enter'})
    ctl=controls(page)
    with pytest.raises(NoProgress):
        await run(page,stub,ctl)
    assert [e[0] for e in ctl.events] == ['invalid_action']*3+['no_progress']
    assert all(e[1]['execution_status']=='failed' for e in ctl.events[:-1])
    assert await page.locator('#x').input_value()==''


async def test_selected_click_executes_and_is_attributed_to_model(page):
    await page.set_content('<input id="x" aria-label="Click" onclick="document.body.innerHTML=\'<h2>Checkout ready</h2>\'">')
    ctl=await run(page,StubCua(lambda e:{'action':'click','value':None}))
    assert ctl.events[0][0]=='click'
    assert ctl.events[0][1]['selection_source']=='cua-s1'


async def test_wrong_predictions_fail_independent_checkout_evaluator(page):
    import httpx
    from backend.fixtures import checkout, new_session, SESSIONS
    from backend.evaluator.scoring import evaluate

    s = scenario('V21-G01', 2026)
    token = new_session(s, 'standard')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=checkout), base_url='http://fixture.local') as client:
        async def serve(route):
            request = route.request
            response = await client.request(request.method, request.url, content=request.post_data_buffer)
            await route.fulfill(status=response.status_code, body=response.content, headers=dict(response.headers))
        await page.route('**/*', serve)
        await page.goto('http://fixture.local/checkout/' + token)
        await page.locator('#workflow').wait_for()
        stub=StubCua(lambda e: {'action':'fill','value':'Near Sample Park'} if 'email' in e['label'].lower() else {'action':'skip'})
        ctl=controls(page)
        with pytest.raises(NoProgress):
            await reference_v21(page,task(s),ctl,'cua-s1',stub)
        score=evaluate(s,SESSIONS[token])
        assert not score['success']
        assert SESSIONS[token]['values']['email']=='Near Sample Park'
        assert SESSIONS[token]['validation_errors']==3
        assert len([e for e in ctl.events if e[1].get('field')=='Review details'])==3
        assert any(d['execution_status']=='skipped' for d in ctl.semantic_decisions)


async def test_unsupported_ui_exhaustion_is_explicit(page):
    await page.set_content('<p>No recognized actions</p>')
    ctl=controls(page)
    ctl.max_steps=1
    with pytest.raises(NoProgress, match='no meaningful progress') as error:
        await run(page,StubCua(lambda e:{'action':'skip'}),ctl)
    assert error.value.diagnostics['reason']=='observation_budget_exhausted'


async def test_select_option_mutation_reobserved_before_navigation(page):
    await page.set_content('''<select id="same" aria-label="Choice"><option value="a">A</option></select>
      <button onclick="let s=document.querySelector('select');if(s.value==='b'){document.body.innerHTML='<h2>Checkout ready</h2>'}else{s.innerHTML='<option value=a>A</option><option value=b>B</option>'}">Review details</button>''')
    calls=0
    def predict(e):
        nonlocal calls
        calls+=1
        return {'action':'skip'} if calls==1 else {'action':'fill','value':'B'}
    ctl=await run(page,StubCua(predict))
    assert any(e[0]=='select' and e[1]['value']=='B' for e in ctl.events)
    assert await page.get_by_role('heading',name='Checkout ready').count()==1


async def test_fill_on_checkbox_does_not_silently_become_toggle(page):
    from backend.adapters.specialists import SpecialistOutputError
    await page.set_content('<input type=checkbox id=x aria-label=Option checked>')
    with pytest.raises(SpecialistOutputError):
        await run(page,StubCua(lambda e:{'action':'fill','value':'false'}))
    assert await page.locator('#x').is_checked()


async def test_diagnostic_stop_does_not_consume_browser_budget(page, tmp_path):
    from types import SimpleNamespace
    from backend.runner.engine import Controls
    resume=asyncio.Event()
    resume.set()
    runner=SimpleNamespace(origin='http://fixture.local',stop_requested=False,resume=resume)
    ctl=Controls(runner,page,{'config':{'max_steps':1},'events':[{'action':'no_progress'}]},tmp_path)
    await ctl.check()


async def test_explicit_click_on_choicegroup_does_not_select_none(page):
    await page.set_content('''<div id=x role=radiogroup aria-label=Payment onclick="document.body.innerHTML='<h2>Checkout ready</h2>'"><button role=radio aria-checked=false data-value=card>Card</button></div>''')
    ctl=await run(page,StubCua(lambda e:{'action':'click','value':None}))
    assert ctl.events[0][0]=='click'
    assert ctl.events[0][1]['field']=='Payment'


async def test_hybrid_revalidates_field_after_grounding_inference(page):
    await page.set_content('<input id=same aria-label=Old style="width:200px;height:40px"><button>Review details</button>')
    class MutatingTiny:
        key='tinyclick'
        last_metrics={'backend':'test-double'}
        async def ground(self,image,prompt):
            if await page.locator('#same').get_attribute('aria-label')=='Old':
                await page.locator('#same').evaluate('e=>e.outerHTML=\'<input id=same aria-label=New style="width:200px;height:40px">\'')
            box=await page.locator('#same').bounding_box()
            return {'x':box['x']+10,'y':box['y']+10}
    ctl=controls(page)
    ctl.limit=1
    from backend.adapters.base import Stopped
    with pytest.raises(Stopped):
        await reference_v21(page,task(scenario('V21-G01')),ctl,'hybrid',StubCua(lambda e:{'action':'fill','value':e['label']+' prediction'}),MutatingTiny())
    assert ctl.semantic_decisions[0]['execution_status']=='stale_observation'
    assert await page.locator('#same').input_value()=='New prediction'
    assert ctl.events[0][1]['value']=='New prediction'


async def test_navigation_waits_for_delayed_public_transition_before_retry(page):
    # Each click invalidates an in-flight UI refresh, as a revision-guarded
    # provider poll does. Rapid retries prevent the accepted action rendering.
    await page.set_content('''<h2>Demo bank gateway</h2><button onclick="clearTimeout(window.refresh);window.refresh=setTimeout(()=>{document.body.innerHTML='<h2>Checkout ready</h2>'},450)">Continue to simulated bank</button>''')
    ctl=await run(page,StubCua(lambda e:{'action':'skip'}))
    assert len(ctl.events)==1
    assert ctl.events[0][1]['selection_source']=='deterministic_controller'
    assert await page.get_by_role('heading',name='Checkout ready').count()==1
