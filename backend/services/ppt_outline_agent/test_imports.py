#!/usr/bin/env python3
"""
Test script to verify PPT Outline Agent import integrity
"""
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all key imports"""
    print("Testing PPT Outline Agent imports...")
    
    try:
        # Test core imports
        from core.plan_agent import build_plan_graph
        from core.state import PlanState
        from core.prompts import PLAN_SYSTEM_PROMPT
        print("✅ Core imports successful")
        
        # Test model imports
        from models.outline import Outline, SlideSpec, SlideElement
        print("✅ Model imports successful")
        
        # Test tool imports
        from tools.plan_tools import PLAN_TOOLS
        from tools.web_search import web_search
        from tools.research_pipeline import deep_research_pipeline
        print("✅ Tool imports successful")
        
        # Test service imports
        from services.search_service import SearchService
        from services.llm_service import LLMService
        print("✅ Service imports successful")
        
        # Test config import
        from config import settings
        print("✅ Config import successful")
        
        print("\n🎉 All imports successful! PPT Outline Agent is ready to use.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_key_functions():
    """Test key function instantiation"""
    try:
        from core.plan_agent import build_plan_graph
        from tools.plan_tools import PLAN_TOOLS, create_outline, confirm_outline
        
        # Test graph building
        graph = build_plan_graph()
        print("✅ Plan graph built successfully")
        
        # Test tool availability
        tools_count = len(PLAN_TOOLS)
        print(f"✅ {tools_count} tools available")
        
        return True
    except Exception as e:
        print(f"❌ Function test error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        test_key_functions()
    
    print("\nTest completed.")