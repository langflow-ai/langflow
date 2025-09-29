# Unified Web Search Component

A consolidated Langflow component that combines Web Search, News Search, and RSS Reader functionality into a single component with a tabbed interface.

## Overview

The Unified Web Search component replaces three separate components (Web Search, News Search, RSS Reader) with a single, more intuitive interface. Users can switch between different search modes using tabs, making it easier to search across different types of web content.

## Features

### 🔄 **Tab-Based Interface**
- **Web**: DuckDuckGo web search with content extraction  
- **News**: Google News RSS search with multiple filters
- **RSS**: Direct RSS feed reader for any RSS URL

### 🎯 **Dynamic UI**
- Input fields change based on selected tab
- News-specific options only visible in News mode
- Context-sensitive help text and placeholders

### 📊 **Consistent Output**
All modes return DataFrame with standardized columns:
- `title`: Article/page title
- `link`: URL to the content  
- `snippet/summary`: Brief description
- `content`: Full content (Web mode) or summary (News/RSS)
- `published`: Publication date (News/RSS modes)

## Tab Modes

### 1. Web Search Tab
**Purpose**: General web search using DuckDuckGo
**Input**: Search query (keywords)
**Features**:
- HTML content extraction from result pages
- URL validation and normalization
- Rate limiting protection
- Content sanitization

**Example Usage**:
```
Mode: Web
Query: "langflow tutorial"
```

**Output**: DataFrame with web search results including full page content.

### 2. News Search Tab  
**Purpose**: News article search via Google News RSS
**Input**: Search query, language, country, topic, location
**Features**:
- Multiple search modes: keyword, topic-based, location-based
- Language and country filtering
- Category support (WORLD, BUSINESS, TECHNOLOGY, etc.)
- Clean HTML parsing

**Example Usage**:
```
Mode: News
Query: "artificial intelligence"
Language: en-US
Country: US
Topic: TECHNOLOGY
```

**Output**: DataFrame with news articles including titles, summaries, and publication dates.

### 3. RSS Reader Tab
**Purpose**: Direct RSS feed parsing
**Input**: RSS feed URL  
**Features**:
- XML validation
- Feed parsing with fallback handling
- Support for various RSS formats
- Error handling for malformed feeds

**Example Usage**:
```
Mode: RSS
RSS Feed URL: https://feeds.bbci.co.uk/news/rss.xml
```

**Output**: DataFrame with RSS feed items.

## Configuration Options

### Basic Settings
- **Search Mode**: Tab selection (Web/News/RSS)
- **Query/URL**: Search keywords or RSS URL
- **Timeout**: Request timeout in seconds

### Advanced Settings (News Mode)
- **Language (hl)**: Language code (e.g., en-US, fr, de)
- **Country (gl)**: Country code (e.g., US, FR, DE)  
- **Topic**: News category (WORLD, BUSINESS, TECHNOLOGY, etc.)
- **Location**: Geographic location for local news

## Use Cases

### 1. **General Research**
Use Web mode for comprehensive web search with full content extraction:
```
Mode: Web
Query: "machine learning best practices"
```

### 2. **News Monitoring** 
Use News mode for current events and news tracking:
```
Mode: News  
Query: "climate change"
Country: US
Language: en-US
```

### 3. **Content Aggregation**
Use RSS mode to pull content from specific feeds:
```
Mode: RSS
URL: https://techcrunch.com/feed/
```

### 4. **Multi-Source Research**
Switch between modes in the same flow:
1. Web search for background information
2. News search for recent developments  
3. RSS feeds from specific sources

## Integration Examples

### With Agents
```python
# Agent can use different search modes based on query type
agent_prompt = """
You have access to a Web Search tool with multiple modes:
- Use Web mode for general information
- Use News mode for recent news and events  
- Use RSS mode for specific feed content

User question: What are the latest developments in AI?
"""
# Agent will automatically choose News mode for "latest developments"
```

### With Data Processing
```python
# Process search results through other components:
Web Search (Web mode) → 
  Filter Data (by relevance) →
    Text Processing → 
      Summary Generation
```

### With Knowledge Bases
```python
# Build knowledge base from multiple sources:
Web Search (RSS mode) → 
  DataFrame Operations (filter/clean) →
    Vector Store (embed content) →
      Knowledge Base
```

## Dynamic Behavior

### Input Adaptation
The component automatically adapts its interface based on the selected tab:

**Web Mode**:
- Query field: "Search Query"
- Advanced news fields hidden
- Focus on web search parameters

**News Mode**:
- Query field: "Search Query"  
- Advanced news fields visible (language, country, topic, location)
- News-specific help text

**RSS Mode**:
- Query field: "RSS Feed URL"
- Advanced news fields hidden
- URL validation and RSS-specific help

### Error Handling
Each mode has specific error handling:
- **Web**: Network timeouts, invalid URLs, parsing errors
- **News**: RSS feed issues, invalid parameters, no results
- **RSS**: Invalid URLs, malformed XML, empty feeds

## Migration from Separate Components

### Before (3 components):
```
Web Search Component → DataFrame
News Search Component → DataFrame  
RSS Reader Component → DataFrame
```

### After (1 unified component):
```
Web Search Component [Web|News|RSS tabs] → DataFrame
```

### Benefits:
- **Simplified UI**: One component instead of three
- **Consistent Interface**: Same input/output patterns
- **Easier Discovery**: All web search functionality in one place
- **Reduced Complexity**: Less component management

## Technical Implementation

### Tab Management
- Uses `TabInput` with options: `["Web", "News", "RSS"]`
- `update_build_config()` method handles dynamic UI changes
- Real-time refresh enabled for immediate tab switching

### Search Routing
- `perform_search()` method routes to appropriate search function
- `perform_web_search()` - DuckDuckGo implementation
- `perform_news_search()` - Google News RSS implementation  
- `perform_rss_read()` - Direct RSS parsing implementation

### Output Standardization
All search modes return DataFrames with consistent column structure:
```python
columns = ["title", "link", "snippet/summary", "content", "published"]
```

## Performance Considerations

### Caching
- No built-in caching (relies on browser/network caching)
- Consider adding caching layer for frequently accessed content

### Rate Limits
- Web mode: DuckDuckGo rate limiting applies
- News mode: Google News RSS generally more permissive
- RSS mode: Depends on individual feed providers

### Timeouts
- Configurable timeout for all network requests
- Default: 5 seconds (recommended: 5-15 seconds)

## Best Practices

### Query Optimization
- **Web mode**: Use specific keywords, avoid stop words
- **News mode**: Use current event terms, consider location/topic filters
- **RSS mode**: Verify RSS URLs are active and properly formatted

### Error Recovery
- Always handle network errors gracefully
- Provide fallback content for failed requests
- Log errors for debugging without breaking workflows

### Performance
- Set appropriate timeouts based on use case
- Consider request volume to avoid rate limiting
- Monitor response times and adjust accordingly

## Future Enhancements

### Potential Features
- **Custom Search Engines**: Add support for other search engines
- **Result Caching**: Built-in caching for improved performance
- **Content Filtering**: Advanced filtering options for each mode
- **Batch Processing**: Support for multiple queries/URLs at once
- **Export Options**: Direct export to different formats

### API Integrations
- **Paid APIs**: Integration with premium search APIs for better results
- **Authentication**: Support for authenticated feeds and APIs
- **Analytics**: Usage tracking and performance metrics

This unified component provides a more streamlined and powerful web search experience while maintaining all the functionality of the original three components.