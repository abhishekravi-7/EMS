import urllib.request, json

api_key = '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'
req = urllib.request.Request('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {api_key}'})
resp = urllib.request.urlopen(req).read().decode('utf-8')
print(json.loads(resp))
