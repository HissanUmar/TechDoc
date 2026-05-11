from __future__ import annotations

import html
import json
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


REQUIREMENTS_PROMPT = "\n".join(
    [
        "You are a requirements analyst.",
        "Read the user request and write a clear requirements response.",
        "Use the web search results to improve the answer when helpful.",
        "Focus on goals, core features, assumptions, and risks.",
        "Keep the response concise but complete.",
        "Do not invent details that are not supported by the prompt or search results.",
    ]
)


class RequirementsDocumentAgent:
    def __init__(self, max_search_results: int = 3, search_timeout: float = 8.0):
        self.max_search_results = max_search_results
        self.search_timeout = search_timeout

    def run(self, prompt: str) -> Dict[str, Any]:
        prompt = self._normalize_prompt(prompt)
        search_queries = self._build_search_queries(prompt)
        sources = self._search_sources(search_queries)
        response = self._build_response(prompt, search_queries, sources)
        return {
            "prompt": prompt,
            "prompt_template": REQUIREMENTS_PROMPT,
            "search_queries": search_queries,
            "sources": sources,
            "response": response,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        }

    def _build_search_queries(self, prompt: str) -> List[str]:
        text = prompt.lower()
        queries = [prompt]
        if any(w in text for w in ("ecommerce", "e-commerce", "store", "shop", "checkout")):
            queries.append("ecommerce requirements checkout inventory shipping payments best practices")
        if any(w in text for w in ("payment", "refund", "tax")):
            queries.append("online store payment refund tax requirements")
        if any(w in text for w in ("catalog", "product", "inventory")):
            queries.append("product catalog inventory management ecommerce requirements")
        return list(dict.fromkeys(queries))[:4]

    def _search_sources(self, queries: List[str]) -> List[Dict[str, str]]:
        sources: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        for query in queries:
            for result in self._duckduckgo_search(query):
                url = result.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                sources.append(result)
                if len(sources) >= self.max_search_results:
                    return sources
        return sources

    def _duckduckgo_search(self, query: str) -> List[Dict[str, str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )

        try:
            with urlopen(request, timeout=self.search_timeout) as response:
                html_text = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return []

        results: List[Dict[str, str]] = []
        for block in re.findall(r'<div class="result__body">(.*?)</div>\s*</div>', html_text, re.DOTALL):
            title_match = re.search(r'class="result__a" href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', block, re.DOTALL)
            if not title_match:
                continue
            href = html.unescape(title_match.group("url"))
            title = self._strip_tags(html.unescape(title_match.group("title")))
            snippet = self._strip_tags(html.unescape(snippet_match.group("snippet"))) if snippet_match else ""
            results.append({"title": title, "url": urljoin("https://html.duckduckgo.com", href), "snippet": snippet})
        return results

    def _build_response(self, prompt: str, search_queries: List[str], sources: List[Dict[str, str]]) -> str:
        lines = [REQUIREMENTS_PROMPT, "", "User request:", prompt, "", "Search queries:"]
        for query in search_queries:
            lines.append(f"- {query}")
        lines.append("")
        lines.append("Search results:")
        if sources:
            for source in sources:
                title = source.get("title", "Unknown source")
                url = source.get("url", "")
                snippet = source.get("snippet", "")
                lines.append(f"- {title}")
                if url:
                    lines.append(f"  {url}")
                if snippet:
                    lines.append(f"  {snippet}")
        else:
            lines.append("- No search results were returned.")
        return "\n".join(lines)

    def _normalize_prompt(self, prompt: str) -> str:
        return " ".join(prompt.strip().split())

    @staticmethod
    def _strip_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()


__all__ = ["RequirementsDocumentAgent", "REQUIREMENTS_PROMPT"]
