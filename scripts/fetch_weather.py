#!/usr/bin/env python3
"""大连天气引擎；仅标准库，凭据仅从环境变量读取。"""
import argparse
import gzip
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # 禁止认证头随重定向泄露

def get(url, params=None, headers=None):
    request = Request(url + ('?' + urlencode(params) if params else ''),
                      headers={'User-Agent': 'DalianWeather/1.0', **(headers or {})})
    for attempt in range(3):
        try:
            with build_opener(NoRedirect).open(request, timeout=25) as response:
                raw = response.read()
                if response.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception:
            if attempt == 2:
                raise RuntimeError('天气接口请求失败（网络、权限或响应异常）') from None
            time.sleep(attempt + 1)

def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def qweather(lat, lon):
    host = os.environ['QWEATHER_API_HOST'].strip()
    if not re.fullmatch(r'(?:[a-zA-Z0-9-]+\.)*re\.qweatherapi\.com', host):
        raise RuntimeError('QWEATHER_API_HOST 必须为账号的 re.qweatherapi.com 域名，不含协议或路径')
    def query(path, params=None):
        obj = get('https://' + host + path, params, {'X-QW-Api-Key': os.environ['QWEATHER_API_KEY']})
        if str(obj.get('code', '200')) != '200' or 'error' in obj:
            raise RuntimeError('和风接口不可用或无权限')
        return obj
    return qweather_data(query, lat, lon)

def qweather_data(query, lat, lon):
    loc = {'location': f'{lon},{lat}', 'lang': 'zh'}
    def row(r):
        return dict(time=r.get('obsTime', r.get('fxTime')), temperature=number(r.get('temp')),
                    text=r.get('text', '未知'), wind_speed=number(r.get('windSpeed')),
                    gust=number(r.get('windGust')), precipitation=number(r.get('precip')),
                    probability=number(r.get('pop')))
    current = row(query('/v7/weather/now', loc)['now'])
    hourly = [row(r) for r in query('/v7/weather/24h', loc)['hourly']][:24]
    daily = [dict(date=r['fxDate'], text=r['textDay'], temp_min=number(r['tempMin']),
                  temp_max=number(r['tempMax']), precipitation=number(r.get('precip')), probability=None)
             for r in query('/v7/weather/3d', loc)['daily']][:3]
    result = dict(source='qweather', current=current, hourly=hourly, daily=daily, limitations=[])
    for name, path, params in [
        ('minute', '/v7/minutely/5m', loc),
        ('air', f'/airquality/v1/current/{lat}/{lon}', None),
        ('indices', '/v7/indices/1d', {**loc, 'type': '0'})]:
        try: result[name] = query(path, params)
        except RuntimeError:
            result[name] = None
            result['limitations'].append(name + '暂不可用（权限、覆盖或网络限制）')
    result['limitations'].append('接口未提供的阵风或降水概率显示为未知，不以零代替')
    return result

def category(text):
    for word in ('雷', '雪', '雨', '雾'):
        if word in text: return word
    return '干燥'

def detect(weather, previous, now):
    """同一风险每次仅在新增、升档时提醒；24小时后仍持续则复核提醒。"""
    rows = [weather['current']] + weather['hourly']
    candidates = {}
    def add(key, score, message):
        candidates[key] = {'score': score, 'message': message}
    prob = max((r.get('probability') or 0 for r in rows), default=0)
    amount = sum(r.get('precipitation') or 0 for r in weather['hourly'])
    wet = {category(r['text']) for r in rows} & {'雨', '雪', '雷'}
    if prob >= 60 or amount >= 1 or wet:
        add('precipitation', 1 + int(prob >= 80) + int(amount >= 10) + int('雪' in wet or '雷' in wet),
            f'未来24小时有{"、".join(sorted(wet)) or "降水风险"}，最高降水概率{prob:g}%、预计降水{amount:.1f}毫米。' if any(r.get('probability') is not None for r in rows) else f'未来24小时有{"、".join(sorted(wet)) or "降水"}，预计降水{amount:.1f}毫米，概率未知。')
    wind = max((r.get('wind_speed') or 0 for r in rows), default=0)
    gust = max((r.get('gust') or 0 for r in rows), default=0)
    if wind >= 39 or gust >= 50:
        add('wind', 1 + int(wind >= 50 or gust >= 62) + int(wind >= 62 or gust >= 75),
            f'未来24小时大风：最大风速{wind:g}公里/小时，' + (f'阵风{gust:g}公里/小时。' if any(r.get('gust') is not None for r in rows) else '阵风数据未知。'))
    temps = [r['temperature'] for r in rows if r.get('temperature') is not None]
    base = weather['current']['temperature']
    if temps and base is not None:
        for key, delta in [('降温', base-min(temps)), ('升温', max(temps)-base)]:
            if delta >= 8: add(key, int(delta//4), f'未来24小时较当前{key}{delta:.1f}℃，注意调整衣物。')
    old_weather = previous.get('current', {})
    if old_weather and previous.get('checked_at') and now - datetime.fromisoformat(previous['checked_at']) <= timedelta(hours=6):
        delta = (base - old_weather['temperature']) if base is not None and old_weather.get('temperature') is not None else 0
        if abs(delta) >= 6: add('实况温变', int(abs(delta)//3), f'较上次检查气温变化{delta:+.1f}℃。')
    transitions = [r for r in weather['hourly'] if category(r['text']) != category(weather['current']['text']) and category(r['text']) != '干燥']
    if transitions:
        r = transitions[0]
        add('转折-' + category(r['text']), 1, f'{r["time"]}前后天气由{weather["current"]["text"]}转为{r["text"]}。')
    old = previous.get('risks', {}) if previous.get('source') == weather['source'] else {}
    changes = []
    for key, value in candidates.items():
        prior = old.get(key)
        if not prior or value['score'] > prior['score'] or now - datetime.fromisoformat(prior['notified_at']) >= timedelta(hours=24):
            changes.append({'type': key, 'level': '重要', **value})
            value['notified_at'] = now.isoformat()
        else: value['notified_at'] = prior['notified_at']
    text = f'大连沙河口天气｜{now:%Y-%m-%d %H:%M}（北京时间）\n' + (' '.join(c['message'] for c in changes) if changes else '无重要变化')
    return dict(checked_at=now.isoformat(), level='重要' if changes else '正常', changes=changes, text=text), dict(checked_at=now.isoformat(), source=weather['source'], current=weather['current'], risks=candidates)

def write(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--latitude', type=float, default=38.88)
    parser.add_argument('--longitude', type=float, default=121.53)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data', help='内部状态与兼容提醒目录；天气始终输出到仓库根目录')
    args = parser.parse_args()
    if not -90 <= args.latitude <= 90 or not -180 <= args.longitude <= 180: parser.error('坐标范围无效')
    now = datetime.now(TZ)
    folder = args.data_dir
    folder.mkdir(parents=True, exist_ok=True)
    try:
        previous = json.loads((folder/'state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): previous = {}
    try:
        missing = [name for name in ('QWEATHER_API_KEY', 'QWEATHER_API_HOST')
                   if not os.environ.get(name, '').strip()]
        if missing:
            raise RuntimeError('缺少环境变量 ' + '、'.join(missing))
        weather = qweather(args.latitude, args.longitude)
        if len(weather['hourly']) < 24 or len(weather['daily']) < 3: raise RuntimeError('预报数据不完整')
        if now - datetime.fromisoformat(weather['current']['time']) > timedelta(hours=3): raise RuntimeError('接口实况数据已过旧')
        weather.update(updated_at=now.isoformat(), status='ok', location={'name':'大连沙河口区', 'latitude':args.latitude, 'longitude':args.longitude}, units={'temperature':'℃', 'wind':'km/h', 'precipitation':'mm', 'probability':'%'})
        if previous.get('location') != weather['location']: previous = {}
        alerts, state = detect(weather, previous, now)
        state['location'] = weather['location']
        # alert_text 为当前风险摘要，changes/text 则保持新变化去重语义。
        summary, _ = detect(weather, {}, now)
        messages = dict.fromkeys(c['message'] for c in summary['changes'] + alerts['changes'])
        weather['alert_text'] = ' '.join(messages) or '无提醒'
        weather['alerts'] = alerts
        write(ROOT/'weather.json', weather)
        write(folder/'state.json', state)
        write(folder/'alerts.json', alerts)
        write(folder/'latest_alert.txt', alerts['text'] + '\n')
        print(alerts['text'])
        return 0
    except Exception:
        missing = [name for name in ('QWEATHER_API_KEY', 'QWEATHER_API_HOST')
                   if not os.environ.get(name, '').strip()]
        error = ('缺少环境变量 ' + '、'.join(missing)) if missing else '和风天气抓取失败（配置、网络、权限或数据异常）'
        # 不输出异常、URL、响应体，避免任何认证信息进入日志。
        alert = dict(checked_at=now.isoformat(), level='错误', changes=[], text=f'大连沙河口天气｜{now:%Y-%m-%d %H:%M}（北京时间）\n{error}；检查失败，无法判断重要变化，请勿沿用旧提醒。')
        # 失败状态不包含任何旧天气，不刷新最后成功更新时间。
        write(ROOT/'weather.json', dict(source='qweather', status='error', updated_at=None,
              checked_at=now.isoformat(), error=error, current=None, hourly=[], daily=[],
              minute=None, air=None, indices=None, alert_text='检查失败，无法判断提醒', alerts=alert))
        write(folder/'alerts.json', alert)
        write(folder/'latest_alert.txt', alert['text']+'\n')
        print(alert['text'], file=sys.stderr)
        return 1

if __name__ == '__main__': sys.exit(main())
