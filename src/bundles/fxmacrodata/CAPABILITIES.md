# Supported operations

Every operation is registered as `fxmd_<operation>` in the native tool surface. The original response is preserved alongside its record view.

| Operation | Contract | Native surface |
| --- | --- | --- |
| `health` | `GET /v1/health` | Langflow StructuredTool, Table/DataFrame |
| `ping` | `GET /v1/ping` | Langflow StructuredTool, Table/DataFrame |
| `forex` | `GET /v1/forex/{base}/{quote}` | Langflow StructuredTool, Table/DataFrame |
| `intraday_reference_rates` | `GET /v1/fx/intraday-reference-rates/{base}/{quote}` | Langflow StructuredTool, Table/DataFrame |
| `fx_sources` | `GET /v1/fx/sources` | Langflow StructuredTool, Table/DataFrame |
| `fx_source_universe` | `GET /v1/fx/source-universe` | Langflow StructuredTool, Table/DataFrame |
| `data_catalogue` | `GET /v1/data_catalogue/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `release_calendar` | `GET /v1/calendar/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `market_sessions` | `GET /v1/market_sessions` | Langflow StructuredTool, Table/DataFrame |
| `rate_differentials` | `GET /v1/rate_differentials/{base}/{quote}` | Langflow StructuredTool, Table/DataFrame |
| `curves` | `GET /v1/curves/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `financial_prices` | `GET /v1/financial_prices/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `press_releases` | `GET /v1/press-releases/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `risk_sentiment` | `GET /v1/risk_sentiment` | Langflow StructuredTool, Table/DataFrame |
| `factors` | `GET /v1/factors/{currency}/{factor}` | Langflow StructuredTool, Table/DataFrame |
| `event_predictions` | `GET /v1/predictions/{currency}/{indicator}` | Langflow StructuredTool, Table/DataFrame |
| `latest_announcements` | `GET /v1/announcements/{currency}/latest` | Langflow StructuredTool, Table/DataFrame |
| `indicator_history` | `GET /v1/announcements/{currency}/{indicator}` | Langflow StructuredTool, Table/DataFrame |
| `cot` | `GET /v1/cot/{currency}` | Langflow StructuredTool, Table/DataFrame |
| `latest_commodities` | `GET /v1/commodities/latest` | Langflow StructuredTool, Table/DataFrame |
| `commodities` | `GET /v1/commodities/{indicator}` | Langflow StructuredTool, Table/DataFrame |
| `announcement_changes` | `GET /v1/announcements/changes` | Langflow StructuredTool, Table/DataFrame |
| `stream_events` | `GET /v1/stream/events` | Langflow StructuredTool, Table/DataFrame |
| `mcp_ping` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_mcp_capabilities` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_mcp_auth_guide` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_subscribe_for_mcp_access` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_data_catalogue` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_risk_sentiment` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_news` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_release_calendar` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_release_calendar_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_event_predictions` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_latest_announcements` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_announcement_changes` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_press_releases` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_factor` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_fx_reference_sources` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_fx_reference_universe` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_fx_intraday_reference_rates` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_rate_curve` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_rate_differentials` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_latest_commodities` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_forex` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_seasonality` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_indicator_query` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_plot_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_indicator_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_forex_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_commodities_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_cot_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_policy_rate_differential_visual_artifact` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_briefing_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_indicator_intel_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_pair_intel_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_heatmap_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_policy_scenario_modeler_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_war_room_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_event_impact_replay_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_quant_scenario_lab_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_known_at_time_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_regime_classifier_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_release_risk_score_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_portfolio_risk_engine_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_fx_trade_setup_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_fx_backtest_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_macro_research_pack_task` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_market_sessions` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_cot_data` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_commodities` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_financial_prices` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |
| `mcp_official_dataset_family` | `MCP /mcp` | Langflow StructuredTool, Table/DataFrame |

REST supplies 23 operations and hosted MCP supplies 49 tools. The `mcp_` prefix distinguishes MCP capabilities from REST operations. Parameters retain their complete documented JSON schemas, including required fields, arrays, nested objects and enums.

USD catalogue, macro history and release-calendar examples are no-key. Access to other datasets follows the service's published access rules; a tool being discoverable is not a guarantee of account entitlement.

SSE event collection is finite: `max_events` and `max_seconds` bound the stream. MCP analytical operations retain their hosted semantics. MCP Apps resources and visual artifacts remain in the original response; these integrations expose data, documents and tools but do not embed an MCP Apps iframe renderer.

Forecasts retain their product labels. FXMacroData-generated predictions must not be relabelled as market consensus. No timestamps, missing observations or future release dates are inferred.
