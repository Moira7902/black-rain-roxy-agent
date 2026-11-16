"""Validate dataset structure; optionally sanity-check deterministic expectations.

No API calls. This does not evaluate dialogue quality or the deployed website.
"""
import argparse, copy, importlib.util, json, re
from pathlib import Path

def read(root,name):return json.loads((root/name).read_text(encoding='utf8'))
def schema_check(v,s,path='$'):
    # Implements exactly the JSON Schema keywords used by case_schema.json.
    supported={'$schema','title','type','required','properties','pattern','minLength','items','minItems','enum','const'}
    assert set(s)<=supported,('Unsupported schema keyword',set(s)-supported)
    types={'object':dict,'array':list,'string':str}
    if 'type' in s:assert isinstance(v,types[s['type']]),(path,s['type'])
    if 'const' in s:assert v==s['const'],path
    if 'enum' in s:assert v in s['enum'],path
    if 'pattern' in s:assert re.search(s['pattern'],v),path
    if 'minLength' in s:assert len(v)>=s['minLength'],path
    if 'minItems' in s:assert len(v)>=s['minItems'],path
    if isinstance(v,dict):
        assert set(s.get('required',[]))<=set(v),path
        for k,ss in s.get('properties',{}).items():
            if k in v:schema_check(v[k],ss,path+'.'+k)
    if isinstance(v,list) and 'items' in s:
        for i,x in enumerate(v):schema_check(x,s['items'],path+f'[{i}]')
def module(root,name):
    spec=importlib.util.spec_from_file_location('roxy_eval_'+name,root/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def value_at(obj,path):
    for k in path.split('.'):
        obj=obj[int(k)] if isinstance(obj,list) else obj[k]
    return obj
def check(obj,c):
    v=value_at(obj,c['path']);w=c.get('value');op=c['op']
    if op=='eq':return v==w
    if op=='neq':return v!=w
    if op=='contains':return w in v
    if op=='not_contains':return w not in v
    if op=='not_in':return v not in w
    if op=='length_eq':return len(v)==w
    if op in ['contains_record','not_contains_record']:
        found=any(all(x.get(k)==vv for k,vv in w.items()) for x in v)
        return found if op=='contains_record' else not found
    raise ValueError('Unsupported sanity-check operation '+op)
def execute_rule(c,profiles,g,m):
    st=copy.deepcopy(profiles[c['profile_id']]);op=c['operation'];name=op['name']
    if name=='apply_rules':
        st,events=g.apply_turn_rules(op['player_input'],op['npc_output'],st);st['events']=events
    elif name=='rules_sequence':
        for turn in op['turns']:st,events=g.apply_turn_rules(turn['player_input'],turn['npc_output'],st)
    elif name=='enforce_emotion':st['emotion']=g.enforce_emotion(op['npc_output'],st)
    elif name=='recent_capacity':
        for i in range(1,op['count']+1):
            st['turn_count']=i;m.add_recent_turn(st,f'受控输入{i}',{'dialogue':f'受控回复{i}'})
    elif name=='long_capacity':
        for i in range(1,op['count']+1):
            st['turn_count']=i;m.add_long_term_memory(st,{'should_write':True,'memory_type':'event','content':f'测试事实{i}','importance':3 if i==1 else 1})
    elif name=='memory_duplicate':
        st['turn_count']=1;m.add_long_term_memory(st,{'should_write':True,'memory_type':'event','content':'玩家来自城里','importance':1})
        st['turn_count']=2;m.add_long_term_memory(st,{'should_write':True,'memory_type':'event','content':'  玩家来自城里  ','importance':3})
    else:raise ValueError(name)
    return st
def validate(root,product_dir=None):
    cases=[json.loads(s) for s in (root/'cases.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
    profiles=read(root,'profiles.json');rubrics=read(root,'rubrics.json');manifest=read(root,'manifest.json');questions=read(root,'open_questions.json')
    ids=set();validreq={f'R{i:02}' for i in range(1,16)};covered=set();qids={q['id'] for q in questions}
    schema=read(root,'case_schema.json');required=schema['required']
    for c in cases:
        schema_check(c,schema)
        assert all(k in c for k in required),c.get('case_id')
        assert re.fullmatch(r'RXY-[DRSQ]\d{3}',c['case_id']) and c['case_id'] not in ids,c['case_id']
        ids.add(c['case_id']);assert c['profile_id'] in profiles
        assert c['must'] and c['must_not'] and set(c['rubric_ids'])<=set(rubrics)
        assert set(c['requirement_ids'])<=validreq;covered.update(c['requirement_ids'])
        assert c['source']['product_commit']==manifest['product_commit']
        assert c['source']['kind']=='self_authored'
        assert c['review_status']=='draft' and c['execution_status']=='not_run' and c['split']=='development'
        if c['selection_status']=='blocked':assert c['case_type']=='pending_spec' and set(c['blocked_by'])<=qids and c['blocked_by']
        else:assert not c['blocked_by']
        if c['case_type']=='dialogue':assert c['steps'] and c['rubric_ids']
        if c['case_type'] in ['deterministic','runtime_scenario']:assert c.get('operation')
        for cc in c['checks']:
            assert cc['phase'] in ['final','normalized','observation']
            assert cc['path'] and cc['op'] in ['eq','neq','contains','not_contains','not_in','length_eq','contains_record','not_contains_record','unchanged','exists']
            if cc['op'] not in ['unchanged','exists']:assert 'value' in cc
    assert covered==validreq,'Missing requirements '+str(validreq-covered)
    assert manifest['counts']=={'total':len(cases),'eligible':sum(c['selection_status']=='eligible' for c in cases),'blocked':sum(c['selection_status']=='blocked' for c in cases)}
    for name,st in profiles.items():
        assert 0<=st['suspicion']<=100 and len(st['recent_history'])<=12 and len(st['long_term_memories'])<=30,name
        for item in st['inventory'].values():
            if item.get('consumed') or item.get('given') or item.get('surrendered'):assert not item['owned'],name
    for c in cases:
        if c['operation']['name']=='batch_plan' if c.get('operation') else False:
            assert set(c['operation']['case_ids'])<=ids
    report={'dataset_version':manifest['version'],'structure':'passed','schema_used_keywords':'passed','counts':manifest['counts'],'requirements_represented':len(covered),'model_evaluation':'not_run','website_evaluation':'not_run','rule_expectation_sanity_checks':[]}
    if product_dir:
        g=module(product_dir,'game_logic');m=module(product_dir,'memory_manager')
        for c in cases:
            if c['case_type']!='deterministic':continue
            result=execute_rule(c,profiles,g,m)
            failures = [dict(cc, actual=value_at(result, cc['path'])) for cc in c['checks'] if not check(result, cc)]
            entry = {'case_id': c['case_id'], 'result': 'mismatch' if failures else 'matched_pinned_implementation'}
            if failures:
                entry['failed_checks'] = failures
            report['rule_expectation_sanity_checks'].append(entry)
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--product-dir',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    result=validate(Path(__file__).resolve().parent,args.product_dir)
    if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if any(entry['result'] == 'mismatch' for entry in result['rule_expectation_sanity_checks']):
        raise SystemExit(1)
