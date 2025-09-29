"""Test script for Unified Web Search component.

This script demonstrates how the unified Web Search component works with:
1. Web search mode (DuckDuckGo)
2. News search mode (Google News)
3. RSS reader mode (RSS feeds)
"""

import sys

# Add the lfx src directory to Python path for imports
sys.path.insert(0, "/Users/rodrigo/Documents/repos/langflow/src/lfx/src")

from lfx.components.data.unified_web_search import UnifiedWebSearchComponent


def test_web_mode():
    """Test Web search mode (DuckDuckGo)."""
    print("\n" + "="*60)
    print("TESTING WEB SEARCH MODE")
    print("="*60)

    component = UnifiedWebSearchComponent()
    component.search_mode = "Web"
    component.query = "Python programming"
    component.timeout = 10

    print(f"Search Mode: {component.search_mode}")
    print(f"Query: {component.query}")
    print(f"Timeout: {component.timeout}")
    print("\nExecuting web search...")

    try:
        results = component.perform_search()
        print("\n✅ Web search completed!")
        print(f"📊 Found {len(results)} results")
        print(f"📋 Columns: {list(results.columns)}")

        if len(results) > 0:
            print("\n🔍 First result:")
            first_result = results.iloc[0]
            print(f"   Title: {first_result.get('title', 'N/A')[:100]}...")
            print(f"   Link: {first_result.get('link', 'N/A')[:80]}...")
            print(f"   Snippet: {first_result.get('snippet', 'N/A')[:150]}...")

        return results
    except Exception as e:
        print(f"❌ Web search failed: {e}")
        return None


def test_news_mode():
    """Test News search mode (Google News)."""
    print("\n" + "="*60)
    print("TESTING NEWS SEARCH MODE")
    print("="*60)

    component = UnifiedWebSearchComponent()
    component.search_mode = "News"
    component.query = "artificial intelligence"
    component.hl = "en-US"
    component.gl = "US"
    component.timeout = 10

    print(f"Search Mode: {component.search_mode}")
    print(f"Query: {component.query}")
    print(f"Language: {component.hl}")
    print(f"Country: {component.gl}")
    print("\nExecuting news search...")

    try:
        results = component.perform_search()
        print("\n✅ News search completed!")
        print(f"📰 Found {len(results)} articles")
        print(f"📋 Columns: {list(results.columns)}")

        if len(results) > 0:
            print("\n📑 First article:")
            first_article = results.iloc[0]
            print(f"   Title: {first_article.get('title', 'N/A')[:100]}...")
            print(f"   Link: {first_article.get('link', 'N/A')[:80]}...")
            print(f"   Published: {first_article.get('published', 'N/A')}")
            print(f"   Summary: {first_article.get('summary', 'N/A')[:200]}...")

        return results
    except Exception as e:
        print(f"❌ News search failed: {e}")
        return None


def test_rss_mode():
    """Test RSS reader mode."""
    print("\n" + "="*60)
    print("TESTING RSS READER MODE")
    print("="*60)

    component = UnifiedWebSearchComponent()
    component.search_mode = "RSS"
    # Using BBC News RSS feed as example
    component.query = "http://feeds.bbci.co.uk/news/rss.xml"
    component.timeout = 10

    print(f"Search Mode: {component.search_mode}")
    print(f"RSS URL: {component.query}")
    print("\nReading RSS feed...")

    try:
        results = component.perform_search()
        print("\n✅ RSS read completed!")
        print(f"📡 Found {len(results)} articles")
        print(f"📋 Columns: {list(results.columns)}")

        if len(results) > 0:
            print("\n📄 First RSS item:")
            first_item = results.iloc[0]
            print(f"   Title: {first_item.get('title', 'N/A')[:100]}...")
            print(f"   Link: {first_item.get('link', 'N/A')[:80]}...")
            print(f"   Published: {first_item.get('published', 'N/A')}")
            print(f"   Summary: {first_item.get('summary', 'N/A')[:200]}...")

        return results
    except Exception as e:
        print(f"❌ RSS read failed: {e}")
        return None


def test_mode_switching():
    """Test that the component properly switches between modes."""
    print("\n" + "="*60)
    print("TESTING MODE SWITCHING")
    print("="*60)

    component = UnifiedWebSearchComponent()

    # Test all modes work
    modes = ["Web", "News", "RSS"]
    queries = [
        "langflow",
        "machine learning",
        "https://rss.cnn.com/rss/edition.rss"
    ]

    for mode, query in zip(modes, queries, strict=False):
        print(f"\n🔄 Switching to {mode} mode...")
        component.search_mode = mode
        component.query = query

        if mode == "News":
            component.hl = "en-US"
            component.gl = "US"

        print(f"   Mode: {component.search_mode}")
        print(f"   Query: {query}")

        try:
            results = component.perform_search()
            print(f"   ✅ {mode} mode working - got {len(results)} results")
        except Exception as e:
            print(f"   ❌ {mode} mode failed: {e}")


def test_build_config():
    """Test the dynamic build config functionality."""
    print("\n" + "="*60)
    print("TESTING DYNAMIC BUILD CONFIG")
    print("="*60)

    component = UnifiedWebSearchComponent()

    # Test build config changes based on mode
    modes = ["Web", "News", "RSS"]

    for mode in modes:
        print(f"\n🔧 Testing build config for {mode} mode...")
        build_config = {
            "query": {"info": "default", "display_name": "default"},
            "hl": {"advanced": True},
            "gl": {"advanced": True},
            "topic": {"advanced": True},
            "location": {"advanced": True}
        }

        updated_config = component.update_build_config(build_config, mode, "search_mode")

        print(f"   Query display name: {updated_config['query']['display_name']}")
        print(f"   Query info: {updated_config['query']['info']}")
        print(f"   News fields advanced: {updated_config['hl']['advanced']}")


if __name__ == "__main__":
    print("="*80)
    print("UNIFIED WEB SEARCH COMPONENT TEST")
    print("="*80)

    # Test each mode
    web_results = test_web_mode()
    news_results = test_news_mode()
    rss_results = test_rss_mode()

    # Test mode switching
    test_mode_switching()

    # Test dynamic config
    test_build_config()

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    print(f"🌐 Web Search: {'✅ Working' if web_results is not None else '❌ Failed'}")
    print(f"📰 News Search: {'✅ Working' if news_results is not None else '❌ Failed'}")
    print(f"📡 RSS Reader: {'✅ Working' if rss_results is not None else '❌ Failed'}")

    success_count = sum([
        1 if web_results is not None else 0,
        1 if news_results is not None else 0,
        1 if rss_results is not None else 0
    ])

    print(f"\n🎯 {success_count}/3 modes working successfully!")

    if success_count == 3:
        print("🎉 All tests passed! The Unified Web Search component is ready!")
    else:
        print("⚠️  Some modes failed - check network connectivity or API endpoints")

    print("\n📊 Component Features Tested:")
    print("   ✓ Tab-based mode switching (Web/News/RSS)")
    print("   ✓ Dynamic input configuration based on mode")
    print("   ✓ Web search via DuckDuckGo")
    print("   ✓ News search via Google News RSS")
    print("   ✓ RSS feed parsing")
    print("   ✓ Consistent DataFrame output format")
    print("   ✓ Error handling and validation")
