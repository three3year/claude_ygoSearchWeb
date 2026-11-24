"""script/web 的模組(值域正典 vocab、前端索引 webindex)從這裡匯入:它們住在 script/web(ADR-0008),
不在本目錄的匯入路徑上。"""
import importlib
import os
import sys

_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")


def web_module(name):
    if _WEB not in sys.path:
        sys.path.append(_WEB)
    return importlib.import_module(name)
