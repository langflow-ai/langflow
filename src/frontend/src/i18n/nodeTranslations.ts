/**
 * nodeTranslations.ts
 * 前端节点字段名翻译覆盖表（P1 方案）
 * 用于翻译来自后端 API 的组件定义字符串（字段名、节点标题、描述等）
 *
 * 使用方式：
 *   import { translateNodeField } from "@/i18n/nodeTranslations";
 *   const label = translateNodeField(fieldDisplayName);
 */

/** 节点字段名翻译表 */
export const nodeFieldTranslations: Record<string, string> = {
    // ── 常用节点标题 ──────────────────────────────
    "Chat Input": "对话输入",
    "Chat Output": "对话输出",
    "Text Input": "文本输入",
    "Text Output": "文本输出",
    "Language Model": "语言模型",
    "Language Model*": "语言模型*",
    "Prompt Template": "提示词模板",
    Webhook: "Webhook",
    "Data Sources": "数据源",
    "Data Template": "数据模板",

    // ── Chat Input/Output 字段 ────────────────────
    "Input Text": "输入文本",
    "Input Placeholder": "输入占位符",
    "Chat Message": "聊天消息",
    "Output Message": "输出消息",
    "Store Messages": "存储消息",
    "Sender Type": "发送者类型",
    "Sender Name": "发送者名称",
    "Session ID": "会话 ID",
    "Context ID": "上下文 ID",
    "Basic Clean Data": "基础数据清理",
    "Background Color": "背景颜色",
    "Chat Icon": "聊天图标",
    "Text Color": "文字颜色",

    // ── Language Model / LLM 字段 ─────────────────
    "System Message": "系统提示",
    "Model Response": "模型响应",
    "System Prompt": "系统提示词",
    "User Payload": "用户消息",
    Temperature: "温度",
    "Max Tokens": "最大 Token 数",
    "Top P": "Top P",
    "Stream Mode": "流式模式",
    Stream: "流式输出",
    "API Key": "API 密钥",
    Model: "模型",
    "Model Name": "模型名称",
    Provider: "提供商",
    "API Base": "API 地址",
    Timeout: "超时时间",
    "Max Retries": "最大重试次数",

    // ── Prompt Template 字段 ──────────────────────
    Template: "模板",
    Prompt: "提示词",
    Instructions: "指令",
    Context: "上下文",
    Question: "问题",

    // ── 通用字段 ──────────────────────────────────
    Input: "输入",
    Output: "输出",
    Inputs: "输入",
    Outputs: "输出",
    Name: "名称",
    Description: "描述",
    URL: "URL",
    Text: "文本",
    Data: "数据",
    Key: "键",
    Value: "值",
    Type: "类型",
    Format: "格式",
    Content: "内容",
    Message: "消息",
    Messages: "消息记录",
    Metadata: "元数据",
    Files: "文件",
    File: "文件",
    Path: "路径",
    Query: "查询",
    Result: "结果",
    Response: "响应",
    Code: "代码",
    Script: "脚本",
    Language: "语言",
    Separator: "分隔符",
    Delimiter: "定界符",
    Encoding: "编码",
    Retries: "重试次数",

    // ── 数据处理字段 ──────────────────────────────
    "Chunk Size": "分块大小",
    "Chunk Overlap": "分块重叠",
    "Max Chunks": "最大分块数",
    Collection: "集合",
    Namespace: "命名空间",
    Dimension: "维度",
    "Search Type": "搜索类型",
    "Number of Results": "结果数量",
    "Top K": "Top K",
    Embedding: "嵌入向量",
    Embeddings: "嵌入",
    "Vector Store": "向量存储",

    // ── 流程控制字段 ──────────────────────────────
    Condition: "条件",
    "True Branch": "真值分支",
    "False Branch": "假值分支",
    Loop: "循环",
    Iterator: "迭代器",
    Stop: "停止",

    // ── 节点描述文字 ──────────────────────────────
    "Get chat inputs from the Playground.": "从体验区获取对话输入。",
    "Display a chat message in the Playground.": "在体验区展示聊天消息。",
    "Configure your Model Provider": "配置您的模型提供商",
    "Setup Provider": "配置提供商",
    "Receiving input": "正在接收输入...",
    "Type something...": "请输入...",
    "Select an option": "请选择",
    Untitled: "未命名",
    Never: "从未",
};

/**
 * 使用翻译覆盖表翻译节点字段名或文字。
 * 如果翻译表中没有对应条目，则返回原始字符串。
 */
export function translateNodeField(text: string): string {
    return nodeFieldTranslations[text] ?? text;
}
