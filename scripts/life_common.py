"""生活频道公共 IO；不会访问或写入天气文件。"""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def fetch(url):
    if urlparse(url).scheme not in ('https', 'http'):
        raise ValueError('不支持的来源协议')
    request = Request(url, headers={'User-Agent': 'DalianLifeStation/1.0 (public information reader)'})
    with urlopen(request, timeout=25) as response:
        data = response.read(8_000_001)
        if len(data) > 8_000_000:
            raise ValueError('来源文件超过 8 MB')
        charset = response.headers.get_content_charset()
    if data.startswith(b'PK') or data.startswith(bytes.fromhex('d0cf11e0')):
        return data
    charset = charset or (re.search(br'charset=["\s]*([\w-]+)', data[:4000], re.I) or [None, b'utf-8'])[1].decode()
    return data.decode(charset, errors='replace')


def text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value))).strip()


def save_result(path, collector):
    """失败保留 items 与 updated_at；checked_at 始终表示本次检查。"""
    old = json.loads(path.read_text()) if path.exists() else {'items': [], 'updated_at': None}
    checked = now()
    try:
        items, sources, warnings = collector()
        if warnings:
            # 部分失败也保留遗漏的旧条目，避免某来源故障导致数据被清空。
            seen = {item['id'] for item in items}
            items += [dict(item, historical=True) for item in old['items'] if item['id'] not in seen]
        result = dict(items=items, sources=sources, checked_at=checked,
                      updated_at=old.get('updated_at') if warnings else checked,
                      status='partial' if warnings else 'ok', message='；'.join(warnings) or '检查完成')
    except Exception as exc:
        # 不输出远端响应或环境变量。
        result = dict(old, checked_at=checked, status='error',
                      message=f'抓取失败（{type(exc).__name__}），保留上次数据；尚无成功数据时为空。')
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)
    print(f'{path.name}: {result["status"]}, {len(result["items"])} 条')
    return 0 if result['status'] == 'ok' else 1
