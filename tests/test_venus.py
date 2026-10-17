"""Unit/contract tests only. Mocked outputs here are never benchmark results."""
import asyncio
import json
import pytest
from PIL import Image
from backend.adapters.venus import (
    VenusAdapter, parse_venus_action, image_size_for_model, build_prompt,
    WEB_USER_PROMPT, ARTIFACT_REVISION,
)
from backend.adapters.specialists import SpecialistOutputError


@pytest.mark.parametrize("expression, expected", [
    ("Click(box=(500,500))", {"action":"click", "x":640, "y":450}),
    ("Type(content='A, B (unit 2)')", {"action":"type", "text":"A, B (unit 2)", "submit":True}),
    ("PressEnter()", {"action":"press", "key":"Enter"}),
    ("Hotkey(keys=['ctrl','a'])", {"action":"press", "key":"Control+a"}),
    ("Finished(content='done')", {"action":"done", "status":"success"}),
    ("CallUser(content='authorisation needed')", {"action":"done", "status":"needs_user"}),
    ("Scroll(direction='down')", {"action":"scroll", "direction":"down"}),
    ("Drag(start=(100,200),end=(500,1000))", {"action":"drag", "start":(128,180), "end":(640,899)}),
])
def test_native_actions(expression, expected):
    raw = f"<think>Unit test only</think><action>{expression}</action><conclusion>test</conclusion>"
    action = parse_venus_action(raw, (1280,900), (640,450))
    assert action.items() >= expected.items()
    assert action["raw"] == raw and action["native_action"] == expression


@pytest.mark.parametrize("raw", [
    "Click(box=(1,2))", "<action>Click(box=(1,2))</action><action>Wait()</action>",
    "<action>Click(box=(1001,2))</action>", "<action>Click(box=(-1,2))</action>",
    "<action>Click(box=(2,1000.01))</action>", "<action>Click(box=(2,-0.01))</action>",
    "<action>Click(box=(True,2))</action>", "<action>Click(box=(1e1000,2))</action>",
    "<action>Click(box=(1,2,3,4))</action>", "<action>Click(box=(1,2),selector='#answer')</action>",
    "<action>Click(box=(1,2),box=(3,4))</action>", "<action>Type(content=42)</action>",
    "<action>Wait(3)</action>", "<action>Wait(seconds=3)</action>",
    "<action>Click(box=__import__('os').system('false'))</action>",
    "<action>Click(**dict(box=(1,2)))</action>", "<action>Unknown()</action>",
])
def test_malformed_outputs_rejected(raw):
    with pytest.raises(SpecialistOutputError) as caught:
        parse_venus_action(raw, (1280,900), (640,450))
    assert caught.value.raw_text == raw


def test_unsupported_native_actions_distinct():
    from backend.adapters.specialists import UnsupportedCapability
    with pytest.raises(UnsupportedCapability):
        parse_venus_action("<action>Launch(url='https://example.invalid')</action>", (1280,900))


def test_processor_grid_and_coordinate_edges():
    assert image_size_for_model((1280,900)) == (1184,832)
    for size in [(1280,900),(375,812),(256,256),(1920,1080)]:
        w,h=image_size_for_model(size)
        assert w%32==h%32==0 and w*h<=1003520
        a=parse_venus_action("<action>Click(box=(1000,1000))</action>",size,(w,h))
        assert (a['x'],a['y']) == (size[0]-1,size[1]-1)


@pytest.mark.parametrize("name", ["Click", "DoubleClick", "Hover", "LongPress"])
def test_coordinate_contract_is_independent_of_processor_resize(name):
    raw = f"<action>{name}(box=(291,951))</action>"
    for model_size in [(1184,832), (640,448), (256,256), None]:
        action = parse_venus_action(raw, (1280,900), model_size)
        assert (action['x'], action['y']) == (372,855)
    origin = parse_venus_action(f"<action>{name}(box=(0,0))</action>", (1280,900))
    assert (origin['x'],origin['y']) == (0,0)


def test_metadata_declares_native_normalized_coordinate_contract():
    metadata = VenusAdapter().metadata()
    assert metadata['adapter_version'] == 'ui-venus-1.5-web-mlx-v3-css-geometry'
    assert metadata['coordinate_space'].startswith('normalized [0,1000]')
    assert metadata['coordinate_contract_source'].endswith('2602.09082v1#S3.SS1.SSS1')


def test_worker_cold_then_warm_timing_excludes_cold_from_warm_aggregate(monkeypatch):
    """Exercise worker protocol with explicit model/runtime test doubles, no inference."""
    import base64
    import io
    import sys
    from types import SimpleNamespace
    from scripts.diagnostics import venus_worker as worker

    processor = SimpleNamespace(image_processor=SimpleNamespace(do_resize=True),
                                apply_chat_template=lambda *a, **k: 'unit-test-template')
    core = SimpleNamespace(
        set_memory_limit=lambda n: None, set_cache_limit=lambda n: None,
        device_info=lambda: {'test_double': True}, reset_peak_memory=lambda: None,
        random=SimpleNamespace(seed=lambda n: None), get_peak_memory=lambda: 123,
        clear_cache=lambda: None)
    result = SimpleNamespace(text='<action>Wait()</action>', prompt_tokens=3,
                             generation_tokens=2, prompt_tps=1, generation_tps=1)
    monkeypatch.setitem(sys.modules, 'mlx', SimpleNamespace(core=core))
    monkeypatch.setitem(sys.modules, 'mlx.core', core)
    monkeypatch.setitem(sys.modules, 'mlx_vlm', SimpleNamespace(load=lambda *a, **k: (object(), processor)))
    monkeypatch.setitem(sys.modules, 'mlx_vlm.generate', SimpleNamespace(generate=lambda *a, **k: result))
    monkeypatch.setitem(sys.modules, 'mlx_vlm.utils', SimpleNamespace(
        prepare_inputs=lambda *a, **k: {'image_grid_thw': SimpleNamespace(tolist=lambda: [[1,2,2]])}))
    monkeypatch.setattr(worker, 'verify', lambda p: {'files': {'model.safetensors': {'sha256': 'test-double'}}})
    monkeypatch.setattr(worker, 'file_hash', lambda p: 'test-double')
    monkeypatch.setattr(worker.importlib.metadata, 'version', lambda p: 'test-double')
    pixels = io.BytesIO()
    Image.new('RGB', (32,32)).save(pixels, format='PNG')
    request = {'image_base64': base64.b64encode(pixels.getvalue()).decode(),
               'image_size': [32,32], 'system_prompt': 'test', 'prompt': 'test', 'max_tokens': 8}
    monkeypatch.setattr(sys, 'argv', ['venus_worker.py', '--model', '/unit-test-only'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO((json.dumps(request)+'\n') * 2))
    wire = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', wire)
    worker.main()
    cold, warm = [json.loads(line)['metrics'] for line in wire.getvalue().splitlines()]
    assert cold['call_temperature'] == 'cold' and cold['warm_inference_seconds'] is None
    assert cold['model_forward_seconds'] > 0
    assert warm['call_temperature'] == 'warm' and warm['cold_model_loading_seconds'] == 0
    assert warm['warm_inference_seconds'] == warm['model_forward_seconds'] > 0


def test_public_task_projection_and_native_history():
    prompt=build_prompt({'instruction':'Buy simulated order','profile':{'name':'Synthetic'},
                         'canonical_id':'CANARY_ID','expected_values':'CANARY_ANSWERS',
                         'ground_truth':'CANARY_TRUTH','selectors':'CANARY_SELECTOR'},
                        [{'raw':'<action>Wait()</action>','dom':'CANARY_DOM'}])
    assert 'Synthetic' in prompt and '<action>Wait()</action>' in prompt
    assert 'CANARY' not in prompt
    assert "<think>" in prompt and "ENTER" in prompt


async def test_successful_generation_metadata_and_raw_before_parse(monkeypatch):
    adapter=VenusAdapter(max_tokens=128)
    async def response(payload):
        assert payload['image_size']==[1184,832]
        return {'raw_text':'malformed genuine-shaped response from unit-test stub',
                'metrics':{'usage':{'prompt_tokens':12,'completion_tokens':7}},'metadata':{'test_double':True}}
    monkeypatch.setattr(adapter,'_request',response)
    with pytest.raises(SpecialistOutputError):
        await adapter.act(Image.new('RGB',(1280,900)),{'instruction':'Test'},[])
    assert adapter.last_metrics['raw_text'].startswith('malformed')
    assert adapter.last_metrics['usage']['completion_tokens']==7
    assert adapter.metadata()['checkpoint_revision']==ARTIFACT_REVISION
    await adapter.close()


async def test_timeout_and_cancel_close_worker(monkeypatch):
    from backend.adapters.specialists import SpecialistInferenceError
    adapter=VenusAdapter(max_tokens=16)
    adapter.config['inference_timeout_seconds']=0.01
    closed=[]
    async def wait(_): await asyncio.sleep(10)
    async def close(): closed.append(True)
    monkeypatch.setattr(adapter,'_request',wait)
    monkeypatch.setattr(adapter,'close',close)
    with pytest.raises(SpecialistInferenceError):
        await adapter.act(Image.new('RGB',(256,256)),{'instruction':'Test'},[])
    assert closed and not adapter.last_metrics['actual_model']
    adapter.config['inference_timeout_seconds']=20
    task=asyncio.create_task(adapter.act(Image.new('RGB',(256,256)),{'instruction':'Test'},[]))
    await asyncio.sleep(.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert len(closed)==2


def test_invalid_generation_budget():
    for count in [0, -1, True, 9000]:
        with pytest.raises(ValueError): VenusAdapter(max_tokens=count)


async def test_real_worker_process_is_terminated_on_close():
    import sys
    adapter=VenusAdapter()
    child=await asyncio.create_subprocess_exec(sys.executable,'-c','import time; time.sleep(30)',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    adapter._process=child
    await adapter.close()
    assert child.returncode is not None and adapter._process is None
    await adapter.close()


def test_attestation_rejects_stale_code_and_non_inference_record():
    from backend.adapters.venus_verification import verify_record
    with pytest.raises(ValueError,match='actual local inference'):
        verify_record({'verified':True,'actual_model':False})
    with pytest.raises(ValueError,match='changed'):
        verify_record({'verified':True,'actual_model':True,'code_source_hashes':{}})


def test_worker_rejects_self_asserted_artifact_manifest(tmp_path):
    from scripts.diagnostics.venus_worker import verify
    (tmp_path/'checkoutbench_provenance.json').write_text(json.dumps({
        'artifact_id':'mlx-community/UI-Venus-1.5-2B-6bit',
        'artifact_revision':ARTIFACT_REVISION,'files':{}}))
    with pytest.raises(ValueError,match='reviewed pinned'):
        verify(tmp_path)


@pytest.mark.parametrize('blank', ['', '   '])
def test_blank_environment_values_use_local_defaults(monkeypatch, blank):
    from backend.adapters.venus import local_configuration
    keys = ['MODEL_PATH', 'PYTHON', 'BACKEND', 'MAX_PIXELS',
            'INFERENCE_TIMEOUT', 'MEMORY_LIMIT_BYTES', 'HISTORY_LIMIT']
    for key in keys:
        monkeypatch.delenv('UI_VENUS_' + key, raising=False)
    expected = local_configuration()
    for key in keys:
        monkeypatch.setenv('UI_VENUS_' + key, blank)
    assert local_configuration() == expected


def test_explicit_local_environment_values_are_preserved(monkeypatch):
    from backend.adapters.venus import local_configuration
    overrides = {'MODEL_PATH': '/tmp/explicit-model', 'PYTHON': '/tmp/explicit-python',
                 'BACKEND': 'explicit-backend', 'MAX_PIXELS': '262144',
                 'INFERENCE_TIMEOUT': '90.5', 'MEMORY_LIMIT_BYTES': '4000000000',
                 'HISTORY_LIMIT': '0'}
    for key, value in overrides.items():
        monkeypatch.setenv('UI_VENUS_' + key, value)
    assert local_configuration() == {
        'model_path': '/tmp/explicit-model', 'python': '/tmp/explicit-python',
        'backend': 'explicit-backend', 'max_pixels': 262144,
        'inference_timeout_seconds': 90.5, 'memory_limit_bytes': 4000000000,
        'history_limit': 0,
    }


def test_explicit_registration_preserves_other_model_records(tmp_path, monkeypatch):
    from scripts.diagnostics.venus_verify import register_record
    monkeypatch.setenv('BENCH_DATA_DIR', str(tmp_path))
    path = tmp_path / 'research/checkpoint-verification.json'
    path.parent.mkdir()
    existing = {'cua-s1': {'verified': True, 'historical_identity': 'preserve'},
                'tinyclick': {'verified': False}}
    path.write_text(json.dumps(existing))
    unit_record = {'verified': True, 'unit_test_only': True}
    assert register_record(unit_record) == path
    assert json.loads(path.read_text()) == {**existing, 'ui-venus': unit_record}
    assert not list(path.parent.glob('*.tmp'))


def test_registration_rejects_invalid_registry_without_overwriting(tmp_path):
    from scripts.diagnostics.venus_verify import register_record
    path = tmp_path / 'research/checkpoint-verification.json'
    path.parent.mkdir()
    path.write_text('["not a model registry"]')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='model-keyed'):
        register_record({'verified': True}, tmp_path)
    assert path.read_bytes() == before


def test_decoding_metadata_discloses_disabled_repetition_penalty():
    decoding = VenusAdapter().metadata()['decoding']
    assert decoding['repetition_penalty'] == 1.0
    assert decoding['repetition_penalty_application'] == 'disabled; mlx-vlm default None'
