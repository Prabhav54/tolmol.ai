"""Local development server: python run.py  ->  http://127.0.0.1:8000"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("tolmol.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=True)
