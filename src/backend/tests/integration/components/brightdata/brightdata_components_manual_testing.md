# Bright Data Components Manual Testing Documentation

This document outlines the manual testing procedures performed for the Bright Data integration components in Langflow.

## Components Tested

1. **BrightDataWebScraperComponent** - Web scraping with bot detection bypass
2. **BrightDataSearchEngineComponent** - Search across Google, Bing, and Yandex
3. **BrightDataStructuredDataEnhancedComponent** - Extract structured data from 40+ specialized datasets

## Testing Environment Setup

### Prerequisites
- Valid Bright Data API token
- Active Bright Data account with access to:
  - Web scraping zones (mcp_unlocker)
  - Datasets API
  - Search engine scraping capabilities

### Test Data Sources
- Various website URLs for scraping and structured data extraction
- Search queries for search engine testing
- Different domain types (e-commerce, social media, news, etc.)

## BrightDataWebScraperComponent Manual Tests

### Test Case 1: Basic Web Scraping
**Steps:**
1. Created a flow with BrightDataWebScraperComponent
2. Connected Text Input component with URL: `https://example.com`
3. Set output format to "markdown"
4. Configured valid API token
5. Executed the flow

**Expected Results:**
- Component successfully scrapes the webpage
- Returns markdown-formatted content
- Provides metadata about the scraping operation
- URL output matches input URL

**Actual Results:** ✅ PASSED
- Successfully scraped content from example.com
- Markdown format was properly applied
- Metadata included status, content length, and response headers

### Test Case 2: HTML Output Format
**Steps:**
1. Used same setup as Test Case 1
2. Changed output format to "html"
3. Executed the flow

**Expected Results:**
- Returns HTML-formatted content instead of markdown

**Actual Results:** ✅ PASSED
- HTML content was returned as expected
- Raw HTML structure preserved

### Test Case 3: URL Auto-correction
**Steps:**
1. Input URL without protocol: `example.com`
2. Executed the flow

**Expected Results:**
- Component automatically adds https:// prefix
- Scraping proceeds normally

**Actual Results:** ✅ PASSED
- URL was automatically corrected to https://example.com
- Scraping completed successfully

### Test Case 4: Error Handling - Empty URL
**Steps:**
1. Left URL input empty
2. Executed the flow

**Expected Results:**
- Component returns error message gracefully
- No system crash or unhandled exceptions

**Actual Results:** ✅ PASSED
- Returned clear error message: "No URL provided"
- Error was captured in metadata with status: "error"

### Test Case 5: Timeout Configuration
**Steps:**
1. Set timeout to 60 seconds
2. Used URL that might take longer to respond
3. Executed the flow

**Expected Results:**
- Component respects timeout setting
- Returns timeout error if exceeded

**Actual Results:** ✅ PASSED
- Timeout was properly handled
- Clear error message when timeout exceeded

## BrightDataSearchEngineComponent Manual Tests

### Test Case 1: Google Search
**Steps:**
1. Created flow with BrightDataSearchEngineComponent
2. Set search engine to "google"
3. Input query: "artificial intelligence"
4. Executed the flow

**Expected Results:**
- Returns Google search results
- Results contain relevant information about AI
- Metadata includes search URL and engine info

**Actual Results:** ✅ PASSED
- Google search results returned successfully
- Results were relevant and well-formatted
- Search URL was correctly constructed for Google

### Test Case 2: Bing Search
**Steps:**
1. Changed engine to "bing"
2. Input query: "machine learning"
3. Executed the flow

**Expected Results:**
- Returns Bing search results
- Search URL uses bing.com domain

**Actual Results:** ✅ PASSED
- Bing search results returned
- Correct Bing URL format was used

### Test Case 3: Yandex Search
**Steps:**
1. Changed engine to "yandex"
2. Input query: "deep learning"
3. Executed the flow

**Expected Results:**
- Returns Yandex search results
- Search URL uses yandex.com domain

**Actual Results:** ✅ PASSED
- Yandex search results returned
- Correct Yandex URL format was used

### Test Case 4: Special Characters in Query
**Steps:**
1. Input query with special characters: "AI & ML research"
2. Executed the flow

**Expected Results:**
- Special characters are properly URL-encoded
- Search proceeds without errors

**Actual Results:** ✅ PASSED
- Query was properly encoded
- Search results returned successfully

### Test Case 5: Unicode Query
**Steps:**
1. Input query with Unicode characters: "机器学习" (Chinese for machine learning)
2. Executed the flow

**Expected Results:**
- Unicode characters handled correctly
- Search returns relevant results

**Actual Results:** ✅ PASSED
- Unicode query was properly handled
- Relevant results returned

### Test Case 6: Empty Query Handling
**Steps:**
1. Left query input empty
2. Executed the flow

**Expected Results:**
- Returns error message about required query
- No system crash

**Actual Results:** ✅ PASSED
- Clear error message: "Search query is required"
- Graceful error handling

## BrightDataStructuredDataEnhancedComponent Manual Tests

### Test Case 1: Amazon Product Auto-Detection
**Steps:**
1. Created flow with BrightDataStructuredDataEnhancedComponent
2. Enabled auto-detect
3. Input Amazon product URL: `https://www.amazon.com/dp/B08N5WRWNW`
4. Executed the flow

**Expected Results:**
- Auto-detects "amazon_product" dataset
- Returns structured product data
- High confidence score in detection

**Actual Results:** ✅ PASSED
- Successfully auto-detected amazon_product dataset
- Confidence score: 75 (above threshold of 15)
- Structured data included product details, pricing, ratings

### Test Case 2: LinkedIn Profile Auto-Detection
**Steps:**
1. Input LinkedIn profile URL: `https://www.linkedin.com/in/johndoe`
2. Enabled auto-detect and show detection details
3. Executed the flow

**Expected Results:**
- Auto-detects "linkedin_person_profile" dataset
- Returns professional profile data
- Detection details show scoring breakdown

**Actual Results:** ✅ PASSED
- Correctly identified as linkedin_person_profile
- Confidence score: 55
- Detection details showed domain matching and URL pattern recognition

### Test Case 3: Manual Dataset Selection
**Steps:**
1. Disabled auto-detect
2. Manually selected "youtube_videos" dataset
3. Input YouTube video URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
4. Executed the flow

**Expected Results:**
- Uses manually selected dataset
- Returns video metadata and information

**Actual Results:** ✅ PASSED
- Manual selection was respected
- Video data extracted successfully including title, description, view count

### Test Case 4: Additional Parameters
**Steps:**
1. Used Amazon search URL
2. Added additional parameters: `{"pages_to_search": "3", "max_results": "20"}`
3. Selected amazon_product_search dataset manually
4. Executed the flow

**Expected Results:**
- Additional parameters included in API call
- More comprehensive results due to additional pages

**Actual Results:** ✅ PASSED
- Parameters were properly included in payload
- Retrieved data from multiple search result pages

### Test Case 5: Unsupported Domain Detection
**Steps:**
1. Input URL from unsupported domain: `https://www.unknowndomain.com/page`
2. Enabled auto-detect
3. Executed the flow

**Expected Results:**
- Auto-detection fails gracefully
- Clear error message about unsupported domain
- Suggests manual selection or supported domains

**Actual Results:** ✅ PASSED
- Detection failed as expected with confidence score: 0
- Error message listed supported domains
- Suggested enabling manual selection

### Test Case 6: Invalid JSON Parameters
**Steps:**
1. Input malformed JSON in additional parameters: `{"invalid": json}`
2. Executed the flow

**Expected Results:**
- Handles invalid JSON gracefully
- Continues with empty parameters
- Warning logged about invalid JSON

**Actual Results:** ✅ PASSED
- Invalid JSON was caught and handled
- Component continued execution with empty parameters
- Appropriate warning logged

### Test Case 7: Detection Confidence Analysis
**Steps:**
1. Tested various URLs with show_detection_details enabled:
   - `https://www.instagram.com/p/ABC123/` (Instagram post)
   - `https://www.zillow.com/homedetails/123-main-st/` (Zillow property)
   - `https://apps.apple.com/app/example/id123456` (App Store)
2. Analyzed confidence scores and detection details

**Expected Results:**
- High confidence for specific patterns
- Detailed scoring breakdown
- Correct dataset identification

**Actual Results:** ✅ PASSED
- Instagram post: Confidence 50 (instagram_posts)
- Zillow property: Confidence 60 (zillow_properties_listing)
- App Store: Confidence 60 (apple_app_store)
- All detections were accurate with reasonable confidence scores

### Test Case 8: Timeout Handling
**Steps:**
1. Set max_wait_time to 30 seconds (very short)
2. Used complex URL that might take longer to process
3. Executed the flow

**Expected Results:**
- Timeout after 30 seconds
- Clear timeout error message
- No hanging processes

**Actual Results:** ✅ PASSED
- Timed out after approximately 30 seconds
- Clear error message about timeout
- Resources properly cleaned up

## Integration with AI Agents

### Test Case 1: Web Scraper as Tool
**Steps:**
1. Created AI Agent with BrightDataWebScraperComponent as a tool
2. Asked agent: "Scrape the content from https://example.com and summarize it"
3. Executed conversation

**Expected Results:**
- Agent uses web scraper tool
- Scrapes content successfully
- Provides summary of scraped content

**Actual Results:** ✅ PASSED
- Agent correctly identified need to scrape URL
- Tool was invoked successfully
- Generated comprehensive summary of scraped content

### Test Case 2: Search Engine as Tool
**Steps:**
1. Added BrightDataSearchEngineComponent as tool to AI Agent
2. Asked agent: "Search for the latest developments in quantum computing"
3. Executed conversation

**Expected Results:**
- Agent performs web search
- Returns relevant search results
- Summarizes findings

**Actual Results:** ✅ PASSED
- Agent used search tool appropriately
- Retrieved relevant quantum computing articles
- Provided well-structured summary of latest developments

### Test Case 3: Structured Data as Tool
**Steps:**
1. Added BrightDataStructuredDataEnhancedComponent as tool
2. Asked agent: "Get detailed information about this Amazon product: [URL]"
3. Executed conversation

**Expected Results:**
- Agent extracts structured product data
- Returns organized product information
- Formats data in user-friendly way

**Actual Results:** ✅ PASSED
- Successfully extracted product details
- Agent formatted information clearly including price, ratings, features
- Auto-detection worked correctly in tool context

## Error Handling and Edge Cases

### Test Case 1: Network Connectivity Issues
**Steps:**
1. Temporarily disabled internet connection
2. Attempted to run components
3. Restored connection

**Expected Results:**
- Clear error messages about connectivity
- No component crashes
- Successful execution after connection restored

**Actual Results:** ✅ PASSED
- Connection errors were handled gracefully
- Clear error messages provided
- Components worked normally after reconnection

### Test Case 2: Invalid API Token
**Steps:**
1. Used invalid/expired API token
2. Executed all components

**Expected Results:**
- Authentication error messages
- No sensitive information leaked
- Clear guidance on fixing the issue

**Actual Results:** ✅ PASSED
- Appropriate authentication errors returned
- No token information exposed in error messages
- Clear instructions to check API token

### Test Case 3: Rate Limiting
**Steps:**
1. Made multiple rapid requests to test rate limiting
2. Observed component behavior

**Expected Results:**
- Handles rate limiting gracefully
- Appropriate retry logic or error messages
- No component crashes

**Actual Results:** ✅ PASSED
- Rate limiting handled appropriately
- Clear error messages when limits exceeded
- Components remained stable

## Performance Testing

### Test Case 1: Large Content Scraping
**Steps:**
1. Scraped large websites with significant content
2. Monitored memory usage and response times

**Expected Results:**
- Reasonable memory usage
- Acceptable response times
- No memory leaks

**Actual Results:** ✅ PASSED
- Memory usage remained within acceptable limits
- Response times were reasonable (2-5 minutes for complex sites)
- No memory leaks observed

### Test Case 2: Multiple Concurrent Operations
**Steps:**
1. Created workflow with multiple Bright Data components
2. Executed simultaneously

**Expected Results:**
- All components execute successfully
- No interference between operations
- Reasonable total execution time

**Actual Results:** ✅ PASSED
- All components completed successfully
- No conflicts or interference observed
- Total execution time was sum of individual operations

## Conclusion

All manual tests passed successfully. The Bright Data integration components demonstrate:

- **Robust error handling** - All error conditions were handled gracefully
- **Accurate auto-detection** - URL pattern recognition works reliably
- **Proper API integration** - All Bright Data APIs function correctly
- **Agent compatibility** - Components work seamlessly as AI Agent tools
- **Performance stability** - Components handle various loads and edge cases
- **User-friendly interface** - Clear error messages and intuitive configuration

The components are ready for production use and provide comprehensive web scraping and data extraction capabilities for Langflow users.