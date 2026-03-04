from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Settings for PPT Outline Agent.
    
    Reads from environment variables only to avoid import conflicts.
    """
    
    # Chat Model (Plan Agent + Build Agent)
    chat_model_base_url: str = "https://api.openai.com/v1"
    chat_model_api_key: str = ""
    chat_model_name: str = "gpt-4o"

    # Web Search (tavily | serpapi | bing | baidu | zhipu_mcp)
    search_api_provider: str = "tavily"
    search_api_key: str = ""

    # Zhipu MCP Web Search Service
    zhipu_mcp_url: str = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    zhipu_mcp_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 优先从环境变量读取（避免导入冲突）
        # 如果环境变量未设置，使用 pydantic-settings 读取的值（默认值）
        if os.getenv('CHAT_MODEL_BASE_URL'):
            self.chat_model_base_url = os.getenv('CHAT_MODEL_BASE_URL')
        elif os.getenv('OPENAI_API_BASE'):
            self.chat_model_base_url = os.getenv('OPENAI_API_BASE')
            
        if os.getenv('CHAT_MODEL_API_KEY'):
            self.chat_model_api_key = os.getenv('CHAT_MODEL_API_KEY')
        elif os.getenv('OPENAI_API_KEY'):
            self.chat_model_api_key = os.getenv('OPENAI_API_KEY')
            
        if os.getenv('CHAT_MODEL_NAME'):
            self.chat_model_name = os.getenv('CHAT_MODEL_NAME')
        elif os.getenv('TEXT_MODEL'):
            self.chat_model_name = os.getenv('TEXT_MODEL')
            
        if os.getenv('SEARCH_API_PROVIDER'):
            self.search_api_provider = os.getenv('SEARCH_API_PROVIDER')
            
        if os.getenv('SEARCH_API_KEY'):
            self.search_api_key = os.getenv('SEARCH_API_KEY')
            
        if os.getenv('ZHIPU_MCP_URL'):
            self.zhipu_mcp_url = os.getenv('ZHIPU_MCP_URL')
            
        if os.getenv('ZHIPU_MCP_API_KEY'):
            self.zhipu_mcp_api_key = os.getenv('ZHIPU_MCP_API_KEY')


# 延迟初始化，避免导入时立即读取配置
_settings = None

def get_settings():
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# 为了向后兼容，提供 settings 对象
settings = get_settings()
