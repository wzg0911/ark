"""
ARK Auto-detection + Zero-config bootstrap
Auto-scans environment for agent frameworks and configures ARK accordingly.
"""

import sys
import importlib
from typing import Dict, List, Optional


def detect_frameworks() -> List[str]:
    """扫描环境中已安装的Agent框架"""
    frameworks = {
        "langchain_core": "LangChain",
        "crewai": "CrewAI", 
        "autogen": "AutoGen",
        "agno": "Agno",
        "openai": "OpenAI SDK",
        "anthropic": "Anthropic SDK",
        "google.generativeai": "Gemini SDK",
        "llama_index": "LlamaIndex",
    }
    detected = []
    for mod, name in frameworks.items():
        try:
            importlib.import_module(mod)
            detected.append(name)
        except ImportError:
            pass
    return detected


def auto_init() -> Dict:
    """一键初始化ARK — 零配置"""
    from .guard import IdempotencyGuard
    from .breaker import CircuitBreaker
    from .validator import OutputValidator
    from .score import ReliabilityScore
    from .schema_registry import SchemaRegistry
    
    frameworks = detect_frameworks()
    
    config = {
        "frameworks": frameworks,
        "mode": "standalone" if not frameworks else "integrated",
        "guard": IdempotencyGuard(),
        "breaker": CircuitBreaker("auto-detect"),
        "validator": OutputValidator(),
        "score": ReliabilityScore(),
        "registry": SchemaRegistry(),
    }
    
    # Auto-init framework hooks
    if "CrewAI" in frameworks:
        try:
            from .crewai import ARKCrewCallback
            config["crewai_callback"] = ARKCrewCallback
        except Exception:
            pass
    
    if "LangChain" in frameworks:
        try:
            from .langchain import ARKCallbackHandler
            config["langchain_handler"] = ARKCallbackHandler
        except Exception:
            pass
    
    return config
