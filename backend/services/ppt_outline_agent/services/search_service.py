from __future__ import annotations

import json
import logging
import re
from html import unescape
from urllib.parse import quote_plus

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str, image_url: str | None = None):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.image_url = image_url

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "image_url": self.image_url,
        }


def _strip_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", "", html)
    return unescape(text).strip()


class SearchService:
    """Web search via configurable provider (Tavily, SerpAPI, Bing, Baidu)."""

    def __init__(self):
        self.provider = settings.search_api_provider
        self.api_key = settings.search_api_key
        self.zhipu_mcp_url = settings.zhipu_mcp_url
        self.zhipu_mcp_api_key = settings.zhipu_mcp_api_key

    async def search(
        self,
        query: str,
        max_results: int = 10,
        include_images: bool = True,
    ) -> dict:
        """Search the web. Returns {"results": [...], "images": [...]}."""
        try:
            # Combined search: Bing + Zhipu Pro
            if self.provider == "bing+zhipu_pro":
                logger.info("Using combined Bing + Zhipu Pro search")
                bing_result = await self._bing_search(query, max_results // 2)
                if self.zhipu_mcp_api_key:
                    zhipu_result = await self._zhipu_mcp_search(query, max_results // 2)
                else:
                    zhipu_result = {"results": [], "images": []}
                
                # Merge results, avoiding duplicates by URL
                all_results = bing_result.get("results", [])
                seen_urls = {r["url"] for r in all_results}
                
                for r in zhipu_result.get("results", []):
                    if r["url"] not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r["url"])
                
                logger.info("Combined search: %d total results (%d from Bing, %d from Zhipu)", 
                            len(all_results), len(bing_result.get("results", [])), len(zhipu_result.get("results", [])))
                
                return {
                    "answer": "",
                    "results": all_results[:max_results],
                    "images": bing_result.get("images", []),
                }
            
            # Individual providers
            elif self.provider == "zhipu_mcp" and self.zhipu_mcp_api_key:
                return await self._zhipu_mcp_search(query, max_results)
            elif self.provider == "tavily" and self.api_key and not self.api_key.startswith("tvly-xxx"):
                return await self._tavily_search(query, max_results, include_images)
            elif self.provider == "serpapi" and self.api_key and not self.api_key.startswith("tvly-xxx"):
                return await self._serpapi_search(query, max_results, include_images)
            elif self.provider == "baidu":
                return await self._baidu_search(query, max_results)
            else:
                # Default: free Bing scraping (no API key needed)
                return await self._bing_search(query, max_results)
        except Exception as e:
            # Fallback to Bing if configured provider fails
            logger.warning("Search provider %s failed for query '%s': %s, falling back to Bing", 
                         self.provider, query[:50], e)
            return await self._bing_search(query, max_results)

    async def _bing_search(self, query: str, max_results: int) -> dict:
        """Scrape Bing search results directly (no API key required)."""
        url = f"https://www.bing.com/search?q={quote_plus(query)}&count={max_results}"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            html = resp.text

        results = []
        # Parse Bing organic results: <li class="b_algo ...">
        blocks = re.findall(r'<li[^>]+class="b_algo[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in blocks[:max_results]:
            # Extract link and title: <h2><a href="...">title</a></h2>
            link_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not link_match:
                continue
            href = link_match.group(1)
            title = _strip_tags(link_match.group(2))

            # Extract snippet from <p> or <div class="b_caption">
            snippet = ""
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if snippet_match:
                snippet = _strip_tags(snippet_match.group(1))
            if not snippet:
                cap_match = re.search(r'class="b_caption"[^>]*>(.*?)</div>', block, re.DOTALL)
                if cap_match:
                    snippet = _strip_tags(cap_match.group(1))

            results.append(SearchResult(title=title, url=href, snippet=snippet[:300]))

        logger.info("Bing search for '%s': %d results", query, len(results))
        return {
            "answer": "",
            "results": [r.to_dict() for r in results],
            "images": [],
        }

    async def _baidu_search(self, query: str, max_results: int) -> dict:
        """Scrape Baidu search results directly (no API key required)."""
        url = f"https://www.baidu.com/s?wd={quote_plus(query)}&rn={max_results}"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            html = resp.text

        results = []
        # Parse Baidu results: <div class="result c-container ...">
        blocks = re.findall(r'class="result c-container[^"]*"(.*?)<!--', html, re.DOTALL)
        for block in blocks[:max_results]:
            # Title and link
            link_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not link_match:
                continue
            href = link_match.group(1)
            title = _strip_tags(link_match.group(2))

            # Snippet
            snippet = ""
            snippet_match = re.search(
                r'class="c-font-normal c-color-text"[^>]*>(.*?)</span>', block, re.DOTALL
            )
            if snippet_match:
                snippet = _strip_tags(snippet_match.group(1))
            if not snippet:
                snippet_match = re.search(r'class="content-right_8Zs40">(.*?)</div>', block, re.DOTALL)
                if snippet_match:
                    snippet = _strip_tags(snippet_match.group(1))

            results.append(SearchResult(title=title, url=href, snippet=snippet[:300]))

        logger.info("Baidu search for '%s': %d results", query, len(results))
        return {
            "answer": "",
            "results": [r.to_dict() for r in results],
            "images": [],
        }

    async def _tavily_search(
        self, query: str, max_results: int, include_images: bool
    ) -> dict:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "include_images": include_images,
            "include_answer": True,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            ))

        images = []
        for img_url in data.get("images", []):
            if isinstance(img_url, str):
                images.append({"url": img_url, "description": "", "source": ""})
            elif isinstance(img_url, dict):
                images.append({
                    "url": img_url.get("url", ""),
                    "description": img_url.get("description", ""),
                    "source": img_url.get("source", ""),
                })

        return {
            "answer": data.get("answer", ""),
            "results": [r.to_dict() for r in results],
            "images": images,
        }

    async def _serpapi_search(
        self, query: str, max_results: int, include_images: bool
    ) -> dict:
        url = "https://serpapi.com/search"
        params = {
            "api_key": self.api_key,
            "q": query,
            "num": max_results,
            "engine": "google",
        }
        if include_images:
            params["tbm"] = "isch"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("organic_results", []):
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
            ))

        images = []
        for img in data.get("images_results", []):
            images.append({
                "url": img.get("original", ""),
                "description": img.get("title", ""),
                "source": img.get("source", ""),
            })

        return {
            "answer": "",
            "results": [r.to_dict() for r in results[:max_results]],
            "images": images[:max_results],
        }

    async def _zhipu_mcp_search(self, query: str, max_results: int) -> dict:
        """Search via Zhipu Web Search API."""
        
        # Check if API key is placeholder
        if not self.zhipu_mcp_api_key or self.zhipu_mcp_api_key.startswith("your-"):
            logger.warning("Zhipu API key not configured or is placeholder, skipping")
            raise ValueError("Zhipu API key not configured")
        
        # Correct Web Search API endpoint (verified from documentation)
        url = "https://open.bigmodel.cn/api/paas/v4/web_search"
        
        headers = {
            "Authorization": f"Bearer {self.zhipu_mcp_api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8",
        }

        payload = {
            "search_engine": "search_pro",
            "search_query": query,
            "count": max_results,
            "content_size": "medium",
            "search_recency_filter": "noLimit",
        }

        logger.info("Calling Zhipu Web Search API: query='%s'", query[:50])
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            
            logger.info("Zhipu Web Search response status: %d", resp.status_code)
            
            if resp.status_code >= 400:
                logger.error("Zhipu API error response: %s", resp.text[:500])
            
            resp.raise_for_status()
            
            data = resp.json()
            
            logger.info("Zhipu API response keys: %s", data.keys() if isinstance(data, dict) else "not a dict")
            
            # Parse response - supports both "web_search_result" and "search_result" fields
            results = []
            
            # Try to get search results from different possible fields
            search_results = None
            if "web_search_result" in data and isinstance(data["web_search_result"], list):
                search_results = data["web_search_result"]
            elif "search_result" in data and isinstance(data["search_result"], list):
                search_results = data["search_result"]
            else:
                logger.warning("No search results found in Zhipu response, data keys: %s", data.keys() if isinstance(data, dict) else "N/A")
                search_results = []
            
            for item in search_results:
                if not isinstance(item, dict):
                    logger.warning("Search result item is not a dict: %s", type(item))
                    continue
                    
                title = item.get("title", "")
                url = item.get("link", item.get("url", ""))
                snippet = item.get("content", "")
                
                if title:
                    results.append(SearchResult(title=title, url=url, snippet=snippet[:300]))
        
        logger.info("Zhipu Web Search for '%s': %d results", query, len(results))
        
        return {
            "answer": "",
            "results": [r.to_dict() for r in results[:max_results]],
            "images": [],
        }
