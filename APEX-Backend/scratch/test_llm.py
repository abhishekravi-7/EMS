import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.infrastructure.llm.chat_llm import ChatLLM

async def main():
    chat = ChatLLM()
    try:
        async for chunk in chat.stream_chat('hi', 'hi'):
            print(chunk, end='')
    except Exception as e:
        print(repr(e))

if __name__ == '__main__':
    asyncio.run(main())
