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
        topics = self._extract_topics(prompt)
        search_queries = self._build_search_queries(topics)
        sources = self._search_sources(search_queries)
        response = self._build_response(prompt, topics, search_queries, sources)
        return {
            "prompt": prompt,
            "prompt_template": REQUIREMENTS_PROMPT,
            "topics": topics,
            "search_queries": search_queries,
            "sources": sources,
            "response": response,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        }

    def _extract_topics(self, prompt: str) -> List[str]:
        text = prompt.lower()
        topic_map = [
            (r"ecommerce|e-commerce|store|shop|marketplace", "ecommerce"),
            (r"product|catalog|listing", "product catalog"),
            (r"cart|checkout|basket", "cart checkout"),
            (r"inventory|stock|warehouse", "inventory management"),
            (r"payment|stripe|card|billing", "payments"),
            (r"refund|return|returns", "refunds and returns"),
            (r"shipping|fulfillment|delivery|tracking", "shipping and fulfillment"),
            (r"tax|vat|dut[y]|customs", "taxes"),
            (r"coupon|discount|promotion|promo", "promotions"),
            (r"email|notification|smtp", "email notifications"),
            (r"seo|search engine", "seo"),
            (r"mobile|responsive", "mobile responsive"),
            (r"postgres|database|sql", "postgres database"),
            (r"admin|merchant|dashboard", "merchant admin"),
        ]

        topics: List[str] = []
        for pattern, label in topic_map:
            if re.search(pattern, text):
                topics.append(label)

        if not topics:
            topics.append("general requirements")

        return list(dict.fromkeys(topics))[:8]

    def _build_search_queries(self, topics: List[str]) -> List[str]:
        queries = []
        if "ecommerce" in topics or "general requirements" in topics:
            queries.append("ecommerce requirements checkout inventory shipping payments best practices")
        if any(topic in topics for topic in ("cart checkout", "payments", "refunds and returns")):
            queries.append("online store payment refund checkout requirements")
        if any(topic in topics for topic in ("inventory management", "shipping and fulfillment", "product catalog")):
            queries.append("product catalog inventory fulfillment ecommerce requirements")
        if any(topic in topics for topic in ("taxes", "promotions", "email notifications", "merchant admin")):
            queries.append("online store tax promotions notifications admin requirements")
        if any(topic in topics for topic in ("mobile responsive", "seo", "postgres database")):
            queries.append("ecommerce mobile seo database best practices")
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

    def _build_response(self, prompt: str, topics: List[str], search_queries: List[str], sources: List[Dict[str, str]]) -> str:
        lines = [REQUIREMENTS_PROMPT, "", "User request:", prompt, "", "Inferred topics:"]
        for topic in topics:
            lines.append(f"- {topic}")
        lines.append("")
        lines.append("Search queries:")
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
            lines.append("")
            lines.append("Fallback analysis:")
            for topic in topics:
                lines.append(f"- Focus on {topic} in the requirements response.")
        return "\n".join(lines)

    def _normalize_prompt(self, prompt: str) -> str:
        return " ".join(prompt.strip().split())

    @staticmethod
    def _strip_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()


__all__ = ["RequirementsDocumentAgent", "REQUIREMENTS_PROMPT"]
