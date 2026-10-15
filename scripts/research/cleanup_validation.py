"""Explicit, fail-closed one-time cleanup. Stop the app before --apply."""
import argparse, collections, hashlib, json, re, shutil, sqlite3, tarfile, tempfile
from datetime import datetime, timezone
from pathlib import Path


def classify(r):
    calls = r.get('calls') or []
    evidence = bool(calls or r.get('model_call_count') or r.get('inference_seconds') or (r.get('execution_manifest') or {}).get('checkpoint'))
    if evidence:
        return 'preserve_inference_or_ambiguous'
    if r.get('model') == 'reference' and r.get('kind') == 'reference':
        return 'deterministic_reference'
    if any(r.get(k) for k in ('test_only','is_test_double','test_double')):
        return 'explicit_test_double'
    reason = str(r.get('failure_reason',''))
    if r.get('status') == 'unavailable' and not r.get('events') and any(x in reason for x in ('is not configured','MODEL_PATH','Missing Python dependency')):
        return 'unconfigured_availability_check'
    return 'ambiguous'


def audit(data):
    with sqlite3.connect(data/'results.sqlite3') as c:
        rows = [(rid, raw, json.loads(raw)) for rid, raw in c.execute('SELECT id,data FROM runs ORDER BY id')]
    report = {'record_count':len(rows),'classification':dict(collections.Counter(classify(r) for _,_,r in rows)), 'versions':dict(collections.Counter(r.get('benchmark_version','1.0 (unversioned legacy)') for _,_,r in rows)), 'records':[{'id':rid,'model':r['model'],'status':r['status'],'classification':classify(r)} for rid,_,r in rows]}
    return rows, report


def clean(data):
    rows, report = audit(data)
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", rid) for rid,_,_ in rows):
        raise ValueError("Reset refused: unsafe artifact directory identifier")
    if any(classify(r) in ('ambiguous','preserve_inference_or_ambiguous') for _,_,r in rows):
        raise ValueError('Reset refused: genuine inference evidence or ambiguous records must be preserved')
    if not rows:
        raise ValueError('No obsolete records; no reset performed')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive=data/'archives'/('pre-evaluation-validation-'+stamp)
    archive.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        with sqlite3.connect(data/'results.sqlite3') as source, sqlite3.connect(root/'results.sqlite3') as dest: source.backup(dest)
        (root/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
        (root/'runs.json').write_text(json.dumps([r for _,_,r in rows],indent=2)+'\n')
        for rid,_,_ in rows:
            p=data/rid
            if p.is_dir(): shutil.copytree(p,root/rid)
        hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        (root/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
        bundle=archive/'backup.tar.gz'
        with tarfile.open(bundle,'w:gz') as t:
            for p in sorted(root.iterdir()): t.add(p,arcname=p.name)
        with tarfile.open(bundle,'r:gz') as t:
            checked=set()
            for member in t:
                if member.name in hashes:
                    assert hashlib.sha256(t.extractfile(member).read()).hexdigest()==hashes[member.name]
                    checked.add(member.name)
            assert checked==set(hashes)
            with tempfile.TemporaryDirectory() as verify:
                db=Path(verify)/'results.sqlite3'; db.write_bytes(t.extractfile('results.sqlite3').read())
                with sqlite3.connect(db) as c:
                    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                    assert c.execute('SELECT id,data FROM runs ORDER BY id').fetchall()==[(rid,raw) for rid,raw,_ in rows]
    # Fail closed if any record changed while the backup was being produced.
    with sqlite3.connect(data/'results.sqlite3') as c:
        c.execute('BEGIN IMMEDIATE')
        assert c.execute('SELECT id,data FROM runs ORDER BY id').fetchall()==[(rid,raw) for rid,raw,_ in rows]
        c.execute('DELETE FROM runs')
    for rid,_,_ in rows:
        if (data/rid).is_dir(): shutil.rmtree(data/rid)
    report.update(backup=str(bundle),backup_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),backup_verified=True,active_records_after=0,artifact_files_archived=len(hashes)-3)
    (archive/'cleanup-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',default='data');p.add_argument('--apply',action='store_true');a=p.parse_args()
    result=clean(Path(a.data)) if a.apply else audit(Path(a.data))[1]
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
