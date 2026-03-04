#!/usr/bin/env python3
"""
Example usage of PPT Outline Agent
"""
import asyncio
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plan_agent import build_plan_graph
from core.state import PlanState
from langchain_core.messages import HumanMessage

async def create_rag_outline():
    """Example: Create a RAG technology presentation outline"""
    
    # Build the plan graph
    graph = build_plan_graph()
    
    # Initial state
    initial_state = {
        "messages": [
            HumanMessage(content="请帮我创建一个关于RAG技术的PPT大纲，需要包含市场分析、技术架构和应用案例")
        ],
        "outline": None,
        "outline_confirmed": False,
        "phase": "planning",
        "gathered_content": "",
        "topic": "RAG技术"
    }
    
    print("🚀 Starting PPT Outline Agent...")
    print("📋 User request: Create a RAG technology presentation outline")
    
    # Simulate the interaction (in real usage, this would handle user feedback)
    result = await graph.ainvoke(initial_state)
    
    if result.get("outline_confirmed"):
        outline = result["outline"]
        print("\n✅ Outline created successfully!")
        print(f"📊 Title: {outline.get('title', 'Untitled')}")
        print(f"📑 Slides: {len(outline.get('slides', []))}")
        
        print("\n📝 Slide previews:")
        for i, slide in enumerate(outline.get("slides", [])[:3], 1):
            print(f"{i}. {slide.get('title', 'No title')}")
            print(f"   Type: {slide.get('slide_type', 'content')}")
            print(f"   Elements: {len(slide.get('elements', []))}")
        
        if len(outline.get("slides", [])) > 3:
            print(f"... and {len(outline.get('slides', [])) - 3} more slides")
    else:
        print("❌ Outline creation incomplete")
    
    return result

async def test_research_pipeline():
    """Example: Test the research pipeline"""
    from tools.research_pipeline import deep_research_pipeline
    
    print("\n🔍 Testing deep research pipeline...")
    report = await deep_research_pipeline("RAG technology market analysis")
    print(f"📄 Research report generated: {len(report)} characters")
    print(f"📖 Preview: {report[:200]}...")
    return report

async def test_search_service():
    """Example: Test the search service"""
    from services.search_service import SearchService
    
    print("\n🌐 Testing search service...")
    search = SearchService()
    
    if search.provider == "zhipu_mcp":
        print(f"🔧 Using Zhipu MCP search provider")
    else:
        print(f"🔧 Using search provider: {search.provider}")
    
    result = await search.search("RAG technology", max_results=5)
    print(f"📊 Found {len(result.get('results', []))} results")
    return result

if __name__ == "__main__":
    print("=" * 60)
    print("PPT Outline Agent - Usage Example")
    print("=" * 60)
    
    try:
        # Test basic functionality
        asyncio.run(create_rag_outline())
        
        # Uncomment to test research pipeline
        # asyncio.run(test_research_pipeline())
        
        # Uncomment to test search service
        # asyncio.run(test_search_service())
        
        print("\n🎉 Example completed successfully!")
        print("💡 To use in production, integrate with your chat interface")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()