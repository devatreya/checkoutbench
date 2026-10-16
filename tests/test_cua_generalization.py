"""Experimental infrastructure tests; doubles never write real-model evidence."""
import copy
import json
import os
from pathlib import Path

import pytest

from backend.adapters.specialists import cua_byte_trace
from scripts.diagnostics import cua_generalization as study


def test_preregistered_mapping_semantic_eligibility():
    p = study.load_protocol()
    rows = p['mappings']
    assert len(rows) == 23
    assert sum(r['eligibility'] == 'changed' for r in rows) == 7
    assert sum(r['eligibility'] == 'identity' for r in rows) == 6
    assert sum(r['eligibility'] == 'excluded' for r in rows) == 10
    for r in rows:
        if r['original_label'] in ('House / flat / building', 'Landmark', 'Billing address', 'Billing ZIP code', 'Apartment, suite, etc. (optional)'):
            assert r['eligibility'] == 'excluded'
            assert r['familiar_label'] == r['original_label']
    assert next(r for r in rows if r['original_label'] == 'Discount code')['rationale'].startswith('Known upstream optional skip-only')


def test_mapped_labels_exist_in_pinned_catalogue():
    concepts = pytest.importorskip('cua_s1.concepts')
    catalogue = {label for c in concepts.CONCEPTS for label in c.form_labels}
    for row in study.load_protocol()['mappings']:
        if row['eligibility'] in ('changed', 'identity'):
            assert row['familiar_label'] in catalogue


def test_preserve_profile_values_candidate_order_count_and_isolation():
    p = study.load_protocol()
    snapshots = study.public_snapshots()
    original = copy.deepcopy(snapshots)
    design, audit = study.build_design(p, snapshots)
    assert snapshots == original
    assert len(design) == 240
    assert len(audit) == 60
    assert all(r['invariants_valid'] for r in audit)
    for case, snapshot in snapshots.items():
        for i, element in enumerate(snapshot['elements']):
            group = [design['primary', case, i, c] for c in study.CONDITIONS]
            assert all(r['entities'] == group[0]['entities'] for r in group)
            assert all(r['profile'] == snapshot['profile'] for r in group)
            assert group[0]['options'] == group[1]['options']
            assert group[2]['options'] == group[3]['options']
            assert group[0]['contexts'] == group[2]['contexts']
            assert group[1]['contexts'] == group[3]['contexts']
            extra = design['supplemental', case, i, 'A']['entities']
            assert extra[:len(group[0]['entities'])] == group[0]['entities']
            assert len(extra) == len(group[0]['entities']) + 6
    design['primary', 'V21-G01', 0, 'A']['element']['value'] = 'mutated'
    assert design['primary', 'V21-G01', 0, 'B']['element']['value'] == ''
    assert snapshots == original


def test_public_envelope_rejects_private_ground_truth():
    p = study.load_protocol()
    s = study.public_snapshots()['V21-G01']
    mappings = [study.mapping_for(p, 'V21-G01', i,e) for i,e in enumerate(s['elements'])]
    for private in ('expected_values', 'expected_entity_keys', 'dom_ids'):
        with pytest.raises(ValueError, match='only elements and profile'):
            study.condition_case(dict(s, **{private: {}}), mappings, 'A', p)
    s['elements'][0]['expected_value'] = 'SECRET_TRUTH_SENTINEL'
    with pytest.raises(ValueError, match='Unexpected field metadata'):
        study.condition_case(s,mappings,'A',p)


def test_mismatch_invalid_not_silently_dropped():
    p=study.load_protocol()
    cases=study.public_snapshots()
    cases['V21-G01']['elements'][0]['label']='not preregistered'
    with pytest.raises(ValueError,match='preregistered mapping'):
        study.build_design(p,cases)
    cases=study.public_snapshots()
    cases['V21-G01']['profile']['Emergency contact email']='would overwrite'
    with pytest.raises(ValueError,match='overwrite'):
        study.build_design(p,cases)


class InfrastructureDouble:
    """Simulate adapter contract for tests ONLY; no production output is written."""
    def __init__(self, protocol, marker='actual_model'):
        self.protocol=protocol
        self.marker=marker
        self.calls=[]
        self.last_metrics={}

    async def score_fields(self,elements,profile):
        from backend.adapters.specialists import cua_inputs
        self.calls.append(copy.deepcopy((elements,profile)))
        entities,contexts,options=cua_inputs(elements,profile,self.protocol)
        scores=[0.0]*len(options)
        scores[-1]=1.0
        return [{'action':'skip','value':None,'entity_key':None,'selected_index':len(options)-1,
                 'confidence':1.0,'candidate_count':len(entities),'distribution':scores,
                 'inference_kind':self.marker,'input_protocol':self.protocol,
                 'model_input':{'context':contexts[0],'options':options,'entity_keys':[k for k,v in entities],
                                'context_encoding':cua_byte_trace(contexts[0],224),
                                'option_encodings':[cua_byte_trace(o,96) for o in options]}}]


async def infrastructure_records():
    p=study.load_protocol()
    design,_=study.build_design(p)
    adapters={c:InfrastructureDouble(p['conditions'][c]['serialization']) for c in study.CONDITIONS}
    records=await study.infer_design(design,adapters,p)
    return p,adapters,records


@pytest.mark.asyncio
async def test_one_pass_each_snapshot_four_conditions_no_model_selected_revisit():
    p,adapters,records=await infrastructure_records()
    assert len(records)==244
    assert sum(r['repeat'] for r in records)==4
    assert all(len(a.calls)==61 for a in adapters.values())
    for r in records:
        if r['case']!='contract-controls':
            assert r['before_value']==''
    assert len({(r['group'],r['field_id'],r['condition']) for r in records if not r['repeat']})==240


@pytest.mark.asyncio
async def test_inference_rejects_test_double_provenance():
    p=study.load_protocol()
    design,_=study.build_design(p)
    adapters={c:InfrastructureDouble(p['conditions'][c]['serialization'],'test_double') for c in study.CONDITIONS}
    with pytest.raises(ValueError,match='genuine local'):
        await study.infer_design(design,adapters,p)


@pytest.mark.asyncio
async def test_truth_only_post_inference_optional_denominators_repeats():
    p,adapters,records=await infrastructure_records()
    # Public arguments contain no field keys/expected answers/private handles.
    for adapter in adapters.values():
        for elements,profile in adapter.calls:
            assert set(elements[0]) <= {'label','role','value','form_title','checked','placeholder'}
            assert not ({'expected_values','expected_entity_keys','dom_ids'} & set(profile))
    graded=study.grade_records(records,p)
    summary=study.summarize(graded,p)
    primary=summary['groups']['primary']
    all_a=primary['checkout_all']['conditions']['A']
    assert all_a['field_value_accuracy']['denominator']==23
    assert all_a['required_empty_skip_rate']=={'numerator':18,'denominator':18,'rate':1.0}
    assert all_a['optional_acceptability']=={'numerator':5,'denominator':5,'rate':1.0}
    assert all_a['strict_assignment_accuracy']['numerator']==0
    assert primary['checkout_changed_labels']['conditions']['A']['field_value_accuracy']['denominator']==7
    assert primary['checkout_familiar_inclusive']['conditions']['A']['field_value_accuracy']['denominator']==13
    assert primary['checkout_label_excluded']['conditions']['A']['field_value_accuracy']['denominator']==10
    controls=primary['synthetic_contract_controls']['conditions']['A']
    assert controls['field_value_accuracy']['denominator']==6
    assert controls['action_contract_accuracy']['denominator']==7
    assert controls['required_empty_skip_rate']['denominator']==4
    assert all(r['within_declared_tolerance'] for r in summary['reproducibility'])


def paired_row(field,condition,correct):
    return {'field_id':field,'condition':condition,'scoring':{'scored':True,'field_value_correct':correct}}


def test_paired_transitions_correct_matching_and_denominator():
    rows=[paired_row(str(i),c,v) for i,pair in enumerate(((False,True),(True,False),(False,False),(True,True))) for c,v in zip(('A','B'),pair)]
    result=study.transition(list(reversed(rows)),'A','B')
    assert set(result['counts'].values())=={1}
    assert result['accuracy_difference']=={'numerator':0,'denominator':4,'rate':0.0}
    with pytest.raises(ValueError,match='Unpaired'):
        study.transition(rows[:-1],'A','B')
    with pytest.raises(ValueError,match='Duplicate'):
        study.transition(rows+rows[:1],'A','B')


@pytest.mark.asyncio
async def test_sanitized_artifact_omits_values_context_and_reversible_bytes():
    p,_,records=await infrastructure_records()
    graded=study.grade_records(records,p)
    public=[study.sanitized_record(r) for r in graded]
    serialized=json.dumps(public)
    assert 'person@example.invalid' not in serialized
    assert 'byte_ids' not in serialized
    assert 'TASK fill' not in serialized
    assert 'before_value' not in serialized
    assert all(len(r['top_three'])==3 for r in public)
    assert all(r['skip_probability']==1.0 for r in public)


def test_freeze_manifest_stable_without_model_loading():
    first=study.freeze_manifest()
    assert first==study.freeze_manifest()
    assert first['planned_forward_calls']==244
    assert len(first['invariants'])==60


@pytest.mark.skipif(os.getenv('RUN_CUA_GENERALIZATION_REAL')!='1',reason='explicit real checkpoint check')
@pytest.mark.asyncio
async def test_genuine_forward_and_same_runtime_deterministic_repeat():
    from backend.adapters.specialists import CuaS1Adapter
    from scripts.research.cua_diagnostics import verify_identity
    path=Path(os.environ['CUA_S1_MODEL_PATH'])
    verify_identity(path)
    adapter=CuaS1Adapter(device='cpu',diagnostics=True)
    adapter.path=str(path)
    adapter.endpoint=''
    case=study.public_snapshots()['contract-controls']
    a=(await adapter.score_fields(case['elements'][:1],case['profile']))[0]
    b=(await adapter.score_fields(case['elements'][:1],case['profile']))[0]
    assert a['inference_kind']==b['inference_kind']=='actual_model'
    assert a['action']==b['action']=='fill'
    assert a['entity_key']==b['entity_key']=='Email'
    assert a['model_input']==b['model_input']
    assert max(abs(x-y) for x,y in zip(a['distribution'],b['distribution'],strict=True))<=1e-7
