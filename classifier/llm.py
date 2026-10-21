# -*- coding: utf-8 -*-
"""OpenAI 协议兼容客户端：纯标准库 urllib 实现，零第三方依赖。

支持任何 OpenAI 兼容服务（OpenAI / DeepSeek / 通义千问 / Kimi / 本地 Ollama 等）：
- base_url 填域名即可，自动补全 /v1（已含 /v1 或 /v2 等版本号时不重复添加）
- 认证方式：Authorization: Bearer <api_key>
"""
import json
import re
import urllib.request
import urllib.error


def normalize_base(base_url: str) -> str:
    """https://api.openai.com  ->  https://api.openai.com/v1"""
    url = base_url.strip().rstrip("/")
    if not re.search(r"/v\d+$", url):
        url += "/v1"
    return url


def chat(base_url: str, api_key: str, model: str, messages, timeout: int = 30) -> str:
    """调用 chat/completions 接口，返回模型回复文本。失败抛异常（含状态码与响应摘要）。"""
    endpoint = normalize_base(base_url) + "/chat/completions"
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}：{body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接到 {endpoint}：{e.reason}") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"响应格式异常：{json.dumps(data, ensure_ascii=False)[:300]}") from e


def _parse_json_dict(text: str) -> dict:
    """从模型回复中稳健地提取 JSON 对象（容忍 ``` 代码块、前后缀文本）。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            text = brace.group(0)
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("模型输出不是 JSON 对象")
    return obj


def classify_names(base_url: str, api_key: str, model: str, names, categories,
                   timeout: int = 60) -> dict:
    """把一批文件名交给大模型分类，返回 {名称: 分类}（非法分类名会被替换为 None）。"""
    system = (
        "你是文件整理助手。用户给你一组文件/文件夹名，请把每一个名称归入指定的分类之一。"
        "只输出一个 JSON 对象，格式为 {\"文件名\": \"分类名\"}，不要输出任何其他内容。"
        "如果实在无法判断，分类填 " + json.dumps(categories[-1]) + "。")
    user = "可选分类列表：\n" + "\n".join(categories) + \
           "\n\n待分类名称（JSON 数组）：\n" + json.dumps(list(names), ensure_ascii=False)
    content = chat(base_url, api_key, model,
                   [{"role": "system", "content": system},
                    {"role": "user", "content": user}], timeout=timeout)
    mapping = _parse_json_dict(content)
    result = {}
    for n in names:
        cat = mapping.get(n)
        result[n] = cat if cat in categories else None
    return result


def test_connection(base_url: str, api_key: str, model: str, timeout: int = 15) -> str:
    """发送一条最小请求验证配置，返回模型回复。"""
    return chat(base_url, api_key, model,
                [{"role": "user", "content": "回复两个字：成功"}], timeout=timeout).strip()[:50]
