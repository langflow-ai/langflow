#!/usr/bin/env python3
"""
check_missing_translations.py
═══════════════════════════════════════════════════════════════════════════════
Langflow 汉化遗漏检查工具 —— "发现 → 汉化 → 检查" 闭环

使用方式：
  # 1. 启动 Langflow 后端（确保 localhost:3100 可访问）
  # 2. 运行检查
  python3 check_missing_translations.py

  # 或指定自定义端口
  python3 check_missing_translations.py --port 7860

输出：
  - 控制台：分类输出遗漏的节点名 / 字段名 / 输出字段名
  - 文件：missing_translations.txt（可直接粘贴到 zh_cn_translations.py 中补充）

工作流程：
  1. 从 /api/v1/all（英文）获取所有组件数据
  2. 与 zh_cn_translations.py 中的三个字典对比
  3. 报告未覆盖的条目，并给出覆盖率百分比
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── 加载翻译字典 ──────────────────────────────────────────────────────────
def load_translation_dicts():
    """动态 import zh_cn_translations，获取三个字典。"""
    translations_path = Path(__file__).parent / "zh_cn_translations.py"
    if not translations_path.exists():
        print(f"[ERROR] 找不到翻译文件: {translations_path}", file=sys.stderr)
        sys.exit(1)

    namespace: dict = {}
    with open(translations_path, encoding="utf-8") as f:
        exec(compile(f.read(), str(translations_path), "exec"), namespace)

    node_names = set(namespace.get("NODE_DISPLAY_NAMES", {}).keys())
    field_names = set(namespace.get("FIELD_DISPLAY_NAMES", {}).keys())
    output_names = set(namespace.get("OUTPUT_DISPLAY_NAMES", {}).keys())
    return node_names, field_names, output_names


# ── 获取认证 token ────────────────────────────────────────────────────────
def get_token(base_url: str, username: str = "admin", password: str = "admin") -> str:
    """尝试通过账号密码登录获取 access_token。"""
    url = f"{base_url}/api/v1/login"
    body = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            token = data.get("access_token", "")
            if token:
                print(f"[INFO] 自动登录成功，获取到 token（前20字符）: {token[:20]}...")
            return token
    except Exception as e:
        print(f"[WARN] 自动登录失败: {e}")
        return ""


# ── 从 API 获取所有组件数据 ────────────────────────────────────────────────
def fetch_all_types(base_url: str, token: str = "") -> dict:
    """以英文请求 /api/v1/all，返回解析后的 JSON dict。"""
    url = f"{base_url}/api/v1/all"
    headers = {
        "Accept-Language": "en",
        "Accept-Encoding": "identity",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"[ERROR] 403 Forbidden: API 需要认证", file=sys.stderr)
            print("  解决方案（任选其一）：", file=sys.stderr)
            print("  1. --token <your_jwt_token>  （从浏览器 localStorage['access_token_lf'] 复制）", file=sys.stderr)
            print("  2. --username admin --password <your_password>  （自动登录获取 token）", file=sys.stderr)
        else:
            print(f"[ERROR] HTTP {e.code}: {e}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] 无法连接到 {url}: {e}", file=sys.stderr)
        print("  请确认 Langflow 后端已启动，或使用 --port 指定正确端口。", file=sys.stderr)
        sys.exit(1)

    # 尝试 gzip 解压
    try:
        import gzip
        raw = gzip.decompress(raw)
    except Exception:
        pass  # 不是 gzip，直接使用原始数据

    return json.loads(raw)


# ── 从 JSON 提取所有字符串 ─────────────────────────────────────────────────
def extract_strings(all_types: dict) -> tuple[set, set, set]:
    """遍历所有组件，提取 node/field/output display_name。"""
    node_names: set[str] = set()
    field_names: set[str] = set()
    output_names: set[str] = set()

    for category, components in all_types.items():
        if not isinstance(components, dict):
            continue
        for comp_type, comp_data in components.items():
            if not isinstance(comp_data, dict):
                continue

            # 节点名
            dn = comp_data.get("display_name", "")
            if dn:
                node_names.add(dn)

            # 字段名
            template = comp_data.get("template", {})
            if isinstance(template, dict):
                for field_key, field_val in template.items():
                    if isinstance(field_val, dict):
                        fdn = field_val.get("display_name", "")
                        if fdn:
                            field_names.add(fdn)

            # 输出字段名
            for out in comp_data.get("outputs", []):
                if isinstance(out, dict):
                    odn = out.get("display_name", "")
                    if odn:
                        output_names.add(odn)

    return node_names, field_names, output_names


# ── 格式化报告 ────────────────────────────────────────────────────────────
def format_report(
    label: str,
    missing: set[str],
    total: int,
    covered: int,
) -> str:
    lines = [
        f"\n{'═'*60}",
        f"  {label}",
        f"  覆盖率: {covered}/{total} ({covered/max(total,1)*100:.1f}%)",
        f"  遗漏: {len(missing)} 条",
        f"{'─'*60}",
    ]
    if missing:
        for s in sorted(missing):
            lines.append(f'    "{s}": "",')
    else:
        lines.append("  ✅ 全部已翻译！")
    return "\n".join(lines)


# ── 主函数 ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="检查 Langflow 汉化遗漏",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", type=int, default=3100, help="Langflow 后端端口（默认 3100）")
    parser.add_argument("--host", default="localhost", help="Langflow 后端主机（默认 localhost）")
    parser.add_argument("--output", default="missing_translations.txt", help="输出文件路径")
    parser.add_argument("--token", default="", help="JWT access token（从浏览器 localStorage['access_token_lf'] 复制）")
    parser.add_argument("--username", default="", help="自动登录用户名")
    parser.add_argument("--password", default="", help="自动登录密码")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print(f"[INFO] 连接到 {base_url} ...")

    # 处理 token
    token = args.token
    if not token and args.username:
        token = get_token(base_url, args.username, args.password)

    # 加载本地翻译字典
    t_nodes, t_fields, t_outputs = load_translation_dicts()
    print(f"[INFO] 当前字典: 节点={len(t_nodes)}, 字段={len(t_fields)}, 输出={len(t_outputs)}")

    # 从 API 提取
    all_types = fetch_all_types(base_url, token)
    api_nodes, api_fields, api_outputs = extract_strings(all_types)
    print(f"[INFO] API 数据: 节点={len(api_nodes)}, 字段={len(api_fields)}, 输出={len(api_outputs)}")

    # 计算遗漏
    missing_nodes = api_nodes - t_nodes
    missing_fields = api_fields - t_fields
    missing_outputs = api_outputs - t_outputs

    # 生成报告
    report_parts = [
        "# Langflow 汉化遗漏报告",
        f"# 生成时间: {__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "# 以下是遗漏的条目，格式为 Python dict 条目，",
        "# 请复制到对应的翻译字典中并填写中文翻译：",
        "",
        "# ── 新增到 NODE_DISPLAY_NAMES ──",
        format_report(
            "节点名（NODE_DISPLAY_NAMES）",
            missing_nodes,
            len(api_nodes),
            len(api_nodes) - len(missing_nodes),
        ),
        "",
        "# ── 新增到 FIELD_DISPLAY_NAMES ──",
        format_report(
            "字段名（FIELD_DISPLAY_NAMES）",
            missing_fields,
            len(api_fields),
            len(api_fields) - len(missing_fields),
        ),
        "",
        "# ── 新增到 OUTPUT_DISPLAY_NAMES ──",
        format_report(
            "输出字段名（OUTPUT_DISPLAY_NAMES）",
            missing_outputs,
            len(api_outputs),
            len(api_outputs) - len(missing_outputs),
        ),
    ]

    report = "\n".join(report_parts)

    # 控制台输出摘要
    print("\n" + "═"*60)
    total_missing = len(missing_nodes) + len(missing_fields) + len(missing_outputs)
    total_all = len(api_nodes) + len(api_fields) + len(api_outputs)
    total_covered = total_all - total_missing
    print(f"  总覆盖率: {total_covered}/{total_all} ({total_covered/max(total_all,1)*100:.1f}%)")
    print(f"  节点遗漏: {len(missing_nodes)} / {len(api_nodes)}")
    print(f"  字段遗漏: {len(missing_fields)} / {len(api_fields)}")
    print(f"  输出遗漏: {len(missing_outputs)} / {len(api_outputs)}")
    print("═"*60)

    if total_missing == 0:
        print("\n✅ 恭喜！所有字符串均已翻译覆盖！")
    else:
        print(f"\n⚠️  发现 {total_missing} 条遗漏，详情见: {args.output}")
        # 写入文件
        output_path = Path(__file__).parent / args.output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"   已写入: {output_path}")
        print("\n建议工作流：")
        print("  1. 打开 missing_translations.txt")
        print("  2. 将遗漏条目复制到 zh_cn_translations.py 对应字典中")
        print("  3. 同步到 nodeTranslations.ts（前端兜底层）")
        print("  4. 重新运行此脚本验证覆盖率")


if __name__ == "__main__":
    main()
