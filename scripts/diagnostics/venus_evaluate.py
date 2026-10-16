"""Run a declared local UI-Venus diagnostic plan through the ordinary API runner.

Use a separate BENCH_DATA_DIR server. No official protocol is configured here.
"""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('research/ui-venus-pilot-plan.json'))
    parser.add_argument('--base-url', default='http://127.0.0.1:8787')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.base_url not in {'http://127.0.0.1:8787', 'http://localhost:8787'}:
        parser.error('Use the isolated local diagnostic server on port 8787')
    plan = json.loads(args.plan.read_text())
    config = plan['config']
    if config['models'] != ['ui-venus'] or config.get('research_release'):
        parser.error('Only non-official local UI-Venus diagnostics are supported')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'declared-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        response = client.post('/api/batches', json=config)
        if response.status_code >= 400:
            raise RuntimeError(f'Batch rejected: {response.status_code}: {response.text}')
        batch = response.json()
        (args.output / 'batch.json').write_text(json.dumps(batch, indent=2)+'\n')
        previous = None
        while True:
            state = client.get('/api/state').raise_for_status().json()
            if not state.get('batch') or state['batch']['id'] != batch['id']:
                raise RuntimeError('Diagnostic batch identity changed')
            current = state.get('current') or {}
            progress = (state['batch']['finished'], current.get('scenario'), current.get('status'))
            if progress != previous:
                print(json.dumps({'finished':progress[0], 'scenario':progress[1], 'status':progress[2], 'reason':current.get('failure_reason')}), flush=True)
                previous = progress
            if not state['running']:
                break
            time.sleep(5)
        rows = [r for r in client.get('/api/diagnostics/results').raise_for_status().json()['runs'] if r.get('batch_id') == batch['id']]
    (args.output / 'runs.json').write_text(json.dumps(rows, indent=2)+'\n')
    summary = {'experiment':plan['experiment'], 'official_leaderboard':False, 'batch_id':batch['id'],
               'intended_trials':len(config['scenarios'])*config['repeats'], 'actual_trials':len(rows),
               'successful_trials':sum(bool(r.get('success')) for r in rows),
               'rows':[{k:r.get(k) for k in ['id','scenario','public_id','status','success','failure_reason','outcome_category','required_field_accuracy','optional_correct','action_count','model_call_count','genuine_inference_call_count','wall_seconds','inference_seconds','invalid_model_output_count','runtime_source_hash','runtime_binding_hash']} for r in rows]}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({'actual_trials':len(rows), 'successful_trials':summary['successful_trials']}), flush=True)


if __name__ == '__main__':
    main()
