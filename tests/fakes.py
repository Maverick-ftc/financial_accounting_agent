"""Scripted model responses used ONLY by tests. Never imported by runtime code."""
import json

def tool_call(name,**kwargs):
    return {'role':'assistant','content':None,'tool_calls':[{'id':'test_'+name,'type':'function',
        'function':{'name':name,'arguments':json.dumps(kwargs)}}]}

class ScriptedModel:
    is_test_double=True
    model='scripted-test-double-not-a-live-model'
    def __init__(self,records):
        self.records=records;self.calls=0;self.usage=[];self.sequence=0

    def json_object(self,system,value,*,role):
        self.calls+=1
        r=dict(self.records[value['document_id']]);text=value['text']
        # Exact source quotes are still checked by the real extraction validator.
        return {'record':r,'evidence':[{'field':k,'quote':text} for k,v in r.items() if v is not None and k not in ('type','description')]}

    def chat(self,messages,*,role,tools=None):
        self.calls+=1
        initial=json.loads(messages[1]['content'])
        checks=initial['initial_checks']
        for m in messages:
            if m['role']=='tool':
                try:
                    output=json.loads(m['content'])
                    if 'issue_codes' in output and 'passed' in output:
                        checks=output
                except ValueError:
                    pass
        extracted={json.loads(m['content'])['document_id'] for m in []}
        # Collect actual extraction tools completed in this local conversation.
        completed=set()
        for m in messages:
            for call in m.get('tool_calls') or []:
                if call['function']['name'] in ('extract_document','reextract_document'):
                    completed.add(json.loads(call['function']['arguments'])['document_id'])
        for did in checks.get('unparsed_document_ids',[]):
            if did not in completed:
                return tool_call('extract_document',document_id=did)
        last=messages[-1]
        if last['role']=='tool':
            output=json.loads(last['content'])
            if 'lines' in output and 'validation' in output:
                return tool_call('finish_case',outcome='ready',explanation='Scripted control-flow test: controls passed.',questions=[])
        if checks.get('unparsed_document_ids'):
            return tool_call('check_case')
        if checks.get('passed'):
            return tool_call('build_draft')
        return tool_call('finish_case',outcome='review',explanation='Scripted control-flow test: source evidence needs review.',
                         questions=['Please resolve the flagged source discrepancy.'])
