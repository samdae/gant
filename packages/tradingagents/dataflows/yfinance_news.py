"""yfinance-based news data fetching functions."""

import yfinance as yf
from datetime import datetime, timezone, date, timedelta



def _extract_article_data(article: dict) -> dict:
    """Extract article data from yfinance news format (handles nested 'content' structure)."""
    content = article.get("content") or article
    if not isinstance(content, dict):
        content = {}
    provider = content.get("provider") or {}
    url = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
    published = None
    try:
        if content.get("pubDate"):
            timestamp = datetime.fromisoformat(content["pubDate"].replace("Z", "+00:00"))
            if timestamp.tzinfo is not None:
                published = timestamp.astimezone(timezone.utc)
        elif article.get("providerPublishTime") is not None:
            published = datetime.fromtimestamp(float(article["providerPublishTime"]), timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        pass
    return {
        "title": content.get("title") or "",
        "summary": content.get("summary") or "",
        "publisher": (provider.get("displayName") if isinstance(provider, dict) else None)
                     or content.get("publisher") or "Unknown",
        "link": (url.get("url") if isinstance(url, dict) else None) or content.get("link") or "",
        "pub_date": published,
    }


def _format_news(articles, start, end, limit):
    eligible = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        data = _extract_article_data(article)
        published = data["pub_date"]
        if published and start <= published.date() <= end and data["title"]:
            eligible.append(data)
    entries = {}
    for data in sorted(eligible, key=lambda item: item["pub_date"], reverse=True):
        if len(entries) >= limit:
            break
        title = data["title"]
        if title in entries:
            continue
        parts = [f"### {title} (source: {data['publisher']}, {data['pub_date'].date()} UTC)"]
        if data["summary"]:
            parts.append(data["summary"])
        if data["link"]:
            parts.append(f"Link: {data['link']}")
        entries[title] = "\n".join(parts)
    return "\n\n".join(entries.values())


def get_news_yfinance(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Retrieve news for a specific stock ticker using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted string containing news articles
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.get_news(count=20)

        if not news:
            return f"No news found for {ticker}"

        news_str = _format_news(news, date.fromisoformat(start_date), date.fromisoformat(end_date), 20)
        if not news_str:
            return f"No news found for {ticker} between {start_date} and {end_date}"

        return f"## {ticker} News, from {start_date} to {end_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"


def get_global_news_yfinance(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    Retrieve global/macro economic news using yfinance Search.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted string containing global news articles
    """
    # Search queries for macro/global news
    search_queries = [
        "stock market economy",
        "Federal Reserve interest rates",
        "inflation economic outlook",
        "global markets trading",
    ]

    all_news = []
    try:
        end = date.fromisoformat(curr_date)
        start_date = end - timedelta(days=look_back_days)
        for query in search_queries:
            search = yf.Search(query=query, news_count=limit, enable_fuzzy_query=True)
            all_news.extend(search.news or [])
        news_str = _format_news(all_news, start_date, end, limit)
        if not news_str:
            return f"No global news found for {curr_date}"

        return f"## Global Market News, from {start_date} to {curr_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching global news: {str(e)}"
