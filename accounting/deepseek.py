"""Small real DeepSeek Chat Completions client; no SDK or secret in source."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

class APIError(RuntimeError):
    pass

class CallBudget(RuntimeError):
    pass

class DeepSeekClient:
    def __init__(self, max_calls=40, timeout=90):
        self.key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
        if not self.key:
            raise APIError('Set DEEPSEEK_API_KEY locally before running. Do not put it in source or chat.')
        self.model = os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash')
        self.max_calls, self.timeout = max_calls, timeout
        self.calls, self.usage = 0, []

    def chat(self, messages, *, role, tools=None, json_mode=False):
        if self.calls >= self.max_calls:
            raise CallBudget('Per-run API call limit reached')
        self.calls += 1
        payload = dict(model=self.model, messages=messages, stream=False,
                       max_tokens=4096, thinking={'type':'disabled'})
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'
        if json_mode:
            payload['response_format'] = {'type':'json_object'}
        req = urllib.request.Request('https://api.deepseek.com/chat/completions',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization':f'Bearer {self.key}', 'Content-Type':'application/json'}, method='POST')
        # No automatic network retry: an ambiguous timeout may already have been billed.
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            hints = {401:'Check your API key', 402:'Check your API balance',
                     429:'Rate limit: wait and retry a smaller batch', 400:'Check model and request compatibility'}
            raise APIError(f'DeepSeek HTTP {exc.code}: {hints.get(exc.code, "API request failed")}') from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise APIError(f'DeepSeek connection/response failed ({type(exc).__name__}); no automatic retry') from None
        self.usage.append(dict(role=role, model=data.get('model',self.model),
            response_id=data.get('id'), usage=data.get('usage',{}),
            timestamp=datetime.now(timezone.utc).isoformat()))
        try:
            choice = data['choices'][0]
            if choice.get('finish_reason') not in ('stop','tool_calls'):
                raise APIError(f'Model did not complete: {choice.get("finish_reason")}')
            message = choice['message']
            visible = json.dumps({k:v for k,v in message.items() if k != 'reasoning_content'}, ensure_ascii=False)
            if re.search(r'[\u3400-\u9fff]', visible):
                raise ValueError('Model returned non-English content; request an English response')
            # Preserve reasoning_content if returned; required for some tool conversations.
            return {k:v for k,v in message.items() if k in ('role','content','tool_calls','reasoning_content')}
        except (KeyError, IndexError, TypeError):
            raise APIError('Unexpected DeepSeek response structure') from None

    def json_object(self, system, value, *, role):
        message = self.chat([{'role':'system','content':system+'\nUse English only.'},
                             {'role':'user','content':json.dumps(value,ensure_ascii=False)}],
                            role=role, json_mode=True)
        try:
            obj = json.loads(message.get('content') or '')
            if not isinstance(obj,dict):
                raise ValueError('Expected object')
            return obj
        except (ValueError, TypeError):
            raise ValueError('Specialist returned empty or invalid JSON; request extraction/proposal again') from None
