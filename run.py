import sys
import asyncio
import uvicorn

if __name__ == "__main__":
    # 1. Force Windows to use the correct loop policy BEFORE launching anything else
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("💡 Windows Proactor Event Loop Policy explicitly configured.")

    # 2. Launch Uvicorn programmatically with reloading enabled
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        workers=1
    )