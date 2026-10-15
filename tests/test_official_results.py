import copy, json, sqlite3
from pathlib import Path
import pytest
from backend.research import official
from backend.research.protocol import release
from backend.research.statistics import analyse
from scripts.research.cleanup_validation import classify, clean
from scenarios.research import digest


def sample():
    m=release();s=m['scenarios'][0];settings={'seed':2026}
    cp={'verified':True,'repository':'fixture-only','revision':'revision-a','checkpoint_hashes':{'weights':'hash-a'}}
    protocol=digest({'settings':settings,'release_hash':m['release_hash']})
    c={'research_release':m['release'],'release_hash':m['release_hash'],'settings':settings,'scoring_version':'3.0','research_protocol_hash':protocol,'checkpoints':{'cua-s1':official.checkpoint_identity(cp)}}
    r={'id':'evidence','model':'cua-s1','kind':'specialist','status':'failed','calls':[{'model':'cua-s1','backend':'local'}],'scoring_version':'3.0','research_release':m['release'],'release_hash':m['release_hash'],'research_protocol_hash':protocol,'scenario':s['id'],'scenario_hash':s['scenario_hash'],'implementation_family':s['implementation_family'],'research_track':'A','task_resolved_correctly':False,'checkout_prepared':False,'primary_failure_category':'timeout','execution_manifest':{'standard_run_all':True,'checkpoint':cp,'settings':settings,'scenario_manifest_hash':m['manifest_hash'],'source_hash':m['source_hash']}}
    return m,c,r


def test_no_implicit_protocol_selection(tmp_path,monkeypatch):
    m,c,r=sample();monkeypatch.setattr(official,'DATA',tmp_path)
    assert official.select([r],m)[0]==[]
    assert analyse([r],m)['total_attempts']==0


@pytest.mark.parametrize('change',[
    {'model':'reference'},{'test_double':True},{'calls':[{'backend':'test-double'}]},
    {'scoring_version':'2.1'},{'release_hash':'old'},{'research_protocol_hash':'different'},
    {'scenario_hash':'tampered'},{'research_release':'old'},
])
def test_incompatible_or_validation_rows_excluded(change):
    m,c,r=sample();r.update(change)
    assert official.select([r],m,c)[0]==[]


def test_checkpoint_changes_and_settings_do_not_mix():
    m,c,r=sample()
    assert official.select([r],m,c)[0]==[r]
    changed=copy.deepcopy(r);changed['execution_manifest']['checkpoint']['revision']='other'
    assert official.select([changed],m,c)[0]==[]
    changed=copy.deepcopy(r);changed['execution_manifest']['settings']['seed']=7
    assert official.select([changed],m,c)[0]==[]


@pytest.mark.parametrize('status',['failed','blocked','unavailable','stopped','running'])
def test_verified_attempts_survive_without_success_or_calls(status):
    m,c,r=sample();r.update(status=status,calls=[])
    assert official.select([r],m,c)[0]==[r]


def test_dashboard_export_share_exact_population(tmp_path,monkeypatch):
    import io,zipfile
    from backend.research import export
    m,c,r=sample();monkeypatch.setattr(official,'configuration',lambda m:(c,None))
    monkeypatch.setattr(export,'release',lambda **kw:m)
    rows=[r,{**r,'id':'old','scoring_version':'2.1'},{**r,'id':'mock','test_only':True}]
    data=official.dataset(rows)
    z=zipfile.ZipFile(io.BytesIO(export.bundle(rows)))
    assert [x['id'] for x in data['runs']]==['evidence']
    assert json.loads(z.read('analysis.json'))['summary']==data['summary']
    assert [x['id'] for x in json.loads(z.read('runs.json'))]==['evidence']
    assert 'docs/operations/RESULTS_DATASET.md' in z.namelist()
    assert data['providers'] and data['payments'] and data['total_attempts']==1


def test_storage_isolates_reference_and_preserves_experiments(tmp_path,monkeypatch):
    from backend.storage import database as db
    monkeypatch.setattr(db,'DATA',tmp_path);monkeypatch.setattr(db,'DB',tmp_path/'results.sqlite3')
    m,c,r=sample();r['result_store']='experiments';db.save(r)
    ref={**r,'id':'ref','model':'reference','result_store':'experiments'};db.save(ref)
    assert [x['id'] for x in db.runs()]==['evidence']
    assert [x['id'] for x in db.runs(diagnostic=True)]==['ref']
    db.recover();assert db.get('evidence')['status']=='failed'
    assert not db.experiment_attempt(ref)


def seed_db(path,rows):
    with sqlite3.connect(path/'results.sqlite3') as c:
        c.execute('CREATE TABLE runs (id TEXT PRIMARY KEY,data TEXT NOT NULL)')
        c.executemany('INSERT INTO runs VALUES (?,?)',[(r['id'],json.dumps(r)) for r in rows])


def test_cleanup_backup_readable_and_unknown_evidence_refused(tmp_path):
    r={'id':'old','model':'reference','kind':'reference','status':'completed','calls':[]}
    seed_db(tmp_path,[r]);(tmp_path/'old').mkdir();(tmp_path/'old'/'trace.json').write_text('{}')
    report=clean(tmp_path)
    assert report['backup_verified'] and Path(report['backup']).exists()
    with sqlite3.connect(tmp_path/'results.sqlite3') as c: assert c.execute('select count(*) from runs').fetchone()[0]==0
    assert not (tmp_path/'old').exists()
    with pytest.raises(ValueError): clean(tmp_path)
    for row in ({**r,'model':'cua-s1','calls':[{'backend':'local'}]}, {**r,'model':'unknown'}):
        assert classify(row) in ('preserve_inference_or_ambiguous','ambiguous')
        with sqlite3.connect(tmp_path/'results.sqlite3') as c: c.execute('insert or replace into runs values (?,?)',(row['id'],json.dumps(row)))
        with pytest.raises(ValueError): clean(tmp_path)
        with sqlite3.connect(tmp_path/'results.sqlite3') as c: assert c.execute('select count(*) from runs').fetchone()[0]==1


async def test_standard_api_and_export_population_is_identical(monkeypatch):
    import csv, io, httpx
    from backend import app as application
    m,c,r=sample()
    rows=[r,{**r,'id':'legacy','scoring_version':'2.1'}, {**r,'id':'fake','test_double':True}]
    monkeypatch.setattr(official,'configuration',lambda m:(c,None))
    monkeypatch.setattr(application,'runs',lambda **kw:rows)
    from backend.research import api as research_api
    monkeypatch.setattr(research_api,'runs',lambda **kw:rows)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application.app),base_url='http://testserver') as client:
        normal=(await client.get('/api/results')).json()
        analysis=(await client.get('/api/research/analysis?protocol=unrequested')).json()
        exported=(await client.get('/api/export/json')).json()
        csv_rows=list(csv.DictReader(io.StringIO((await client.get('/api/export/csv')).text)))
        assert normal==analysis
        assert [x['id'] for x in normal['runs']]==[x['id'] for x in exported['runs']]==[x['id'] for x in csv_rows]==['evidence']
        assert (await client.get('/api/results/evidence')).status_code==200
        assert (await client.get('/api/results/legacy')).status_code==404
        assert normal['summary']['task_resolution']['rate']==0


def test_stale_or_corrupt_configuration_fails_closed(tmp_path,monkeypatch):
    m,c,r=sample();monkeypatch.setattr(official,'DATA',tmp_path)
    path=tmp_path/'research/official-protocol.json';path.parent.mkdir()
    for content in ('not-json',json.dumps({**c,'release_hash':'old'}),json.dumps({**c,'research_protocol_hash':'tampered'})):
        path.write_text(content)
        selected,reason=official.select([r],m)
        assert not selected and reason


def test_startup_preserves_verified_running_attempt_as_blocked(tmp_path,monkeypatch):
    from backend.storage import database as db
    monkeypatch.setattr(db,'DATA',tmp_path);monkeypatch.setattr(db,'DB',tmp_path/'results.sqlite3')
    m,c,r=sample();r.update(status='running',result_store='experiments',calls=[])
    db.save(r);db.recover()
    saved=db.get(r['id'])
    assert saved['status']=='blocked' and saved['failure_reason']=='server_restarted'
    assert saved['execution_manifest']==r['execution_manifest']
    assert official.select([saved],m,c)[0]==[saved]
