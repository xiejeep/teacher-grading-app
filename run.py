"""试卷版面分析系统 - 后端启动入口
用法: python run.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
