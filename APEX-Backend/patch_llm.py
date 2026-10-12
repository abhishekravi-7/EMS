from pathlib import Path
path = Path(r'c:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent\llm.py')
content = path.read_text(encoding='utf-8')
target = '''    async def generate(self, prompt: str) -> str:
        return await self.chat_llm.generate(prompt)'''
replacement = '''    async def generate(self, prompt: str) -> str:
        chunks = []
        async for chunk in self.chat_llm.stream_chat(system_prompt="You are a JSON-generating bot.", user_prompt=prompt):
            chunks.append(chunk)
        return "".join(chunks)'''
if target in content:
    content = content.replace(target, replacement)
    path.write_text(content, encoding='utf-8')
    print("Patched llm.py successfully.")
else:
    print("Target not found. It might already be patched.")
