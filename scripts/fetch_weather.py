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

LAYERS = {'fast': ('current', 'minute'), 'medium': ('hourly', 'air'), 'slow': ('daily', 'indices')}

def slot(layer, now):
    now = now.astimezone(TZ)
    if layer == 'fast': return now.replace(minute=now.minute//10*10, second=0, microsecond=0).isoformat()
    if layer == 'medium': return now.replace(minute=0, second=0, microsecond=0).isoformat()
    anchor = now.replace(hour=5, minute=50, second=0, microsecond=0)
    return (anchor + timedelta(hours=6 * int((now-anchor).total_seconds()//21600))).isoformat()

def client():
    host = os.environ['QWEATHER_API_HOST'].strip()
    if not re.fullmatch(r'(?:[a-zA-Z0-9-]+\.)*re\.qweatherapi\.com', host):
        raise RuntimeError('和风配置无效')
    def query(path, params=None):
        obj = get('https://' + host + path, params, {'X-QW-Api-Key': os.environ['QWEATHER_API_KEY']})
        if str(obj.get('code', '200')) != '200' or 'error' in obj:
            raise RuntimeError('和风接口不可用或无权限')
        return obj
    return query

def fetch_field(query, name, lat, lon, now):
    loc = {'location': f'{lon},{lat}', 'lang': 'zh'}
    def row(r):
        return dict(time=r.get('obsTime', r.get('fxTime')), temperature=number(r.get('temp')),
                    text=r.get('text', '未知'), wind_speed=number(r.get('windSpeed')),
                    gust=number(r.get('windGust')), precipitation=number(r.get('precip')),
                    probability=number(r.get('pop')))
    if name == 'current':
        result = row(query('/v7/weather/now', loc)['now'])
        if abs((now-datetime.fromisoformat(result['time'])).total_seconds()) > 10800:
            raise RuntimeError('实况已过旧')
        return result
    if name == 'hourly':
        result = [row(r) for r in query('/v7/weather/24h', loc)['hourly']][:24]
        if len(result) != 24: raise RuntimeError('逐小时预报不完整')
        return result
    if name == 'daily':
        result = [dict(date=r['fxDate'], text=r['textDay'], temp_min=number(r['tempMin']),
                       temp_max=number(r['tempMax']), precipitation=number(r.get('precip')), probability=None)
                  for r in query('/v7/weather/3d', loc)['daily']][:3]
        if len(result) != 3: raise RuntimeError('逐日预报不完整')
        return result
    paths = {'minute': ('/v7/minutely/5m', loc),
             'air': (f'/airquality/v1/current/{lat}/{lon}', None),
             'indices': ('/v7/indices/1d', {**loc, 'type': '0'})}
    return query(*paths[name])

def refresh_layers(weather, query, lat, lon, now, config_error=None):
    import copy
    weather = copy.deepcopy(weather)
    layers = weather.setdefault('layers', {})
    fields = weather.setdefault('fields', {})
    for layer, names in LAYERS.items():
        meta = layers.setdefault(layer, {})
        current_slot = slot(layer, now)
        if meta.get('slot') == current_slot: continue
        meta.update(slot=current_slot, checked_at=now.isoformat())
        errors = []
        for name in names:
            field = fields.setdefault(name, {})
            field['checked_at'] = now.isoformat()
            try:
                if config_error: raise RuntimeError(config_error)
                weather[name] = fetch_field(query, name, lat, lon, now)
                field.update(status='ok', updated_at=now.isoformat(), error=None)
            except Exception:
                field.update(status='error', error=config_error or '和风接口抓取失败（网络、权限或数据异常）；保留值为历史数据')
                errors.append(name)
        meta.update(status='error' if errors else 'ok', failed_fields=errors)
        if not errors: meta['updated_at'] = now.isoformat()
    weather.update(source='qweather', checked_at=now.isoformat(),
                   location={'name':'大连沙河口区','latitude':lat,'longitude':lon},
                   units={'temperature':'℃','wind':'km/h','precipitation':'mm','probability':'%'})
    failures = [name for name, field in fields.items() if field['status'] == 'error']
    weather['status'] = 'error' if failures else 'ok'
    weather['error'] = (config_error or '以下字段抓取失败，保留值仅为历史数据：' + '、'.join(failures)) if failures else None
    weather['updated_at'] = fields.get('current', {}).get('updated_at')
    weather['limitations'] = ['接口未提供的值显示为未知；每层及字段更新时间独立记录']
    return weather

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
    minute_amount = sum(number(r.get('precip')) or 0 for r in (weather.get('minute') or {}).get('minutely', []))
    if minute_amount > 0:
        add('分钟降水', 1 + int(minute_amount >= 5), f'未来两小时分钟预报有降水，合计约{minute_amount:.1f}毫米，请留意雨雪。')
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
        weather = json.loads((ROOT/'weather.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): weather = {}
    if weather.get('location', {}).get('latitude') != args.latitude or weather.get('location', {}).get('longitude') != args.longitude or weather.get('source') != 'qweather':
        weather, previous = {}, {}
    missing = [name for name in ('QWEATHER_API_KEY', 'QWEATHER_API_HOST') if not os.environ.get(name, '').strip()]
    config_error = '缺少环境变量 ' + '、'.join(missing) if missing else None
    query = None
    if not config_error:
        try: query = client()
        except Exception: config_error = '和风配置无效，请检查环境变量 QWEATHER_API_KEY、QWEATHER_API_HOST'
    weather = refresh_layers(weather, query, args.latitude, args.longitude, now, config_error)
    current_meta = weather['fields'].get('current', {})
    usable = current_meta.get('status') == 'ok' and weather.get('current') and now-datetime.fromisoformat(current_meta['updated_at']) < timedelta(hours=3)
    if usable:
        # 仅使用有效、尚未过期且时间在未来的预报生成提醒。
        view = dict(weather)
        hourly_meta = weather['fields'].get('hourly', {})
        view['hourly'] = [r for r in weather.get('hourly', []) if datetime.fromisoformat(r['time']) >= now] if hourly_meta.get('status') == 'ok' and now-datetime.fromisoformat(hourly_meta['updated_at']) < timedelta(hours=3) else []
        minute_meta = weather['fields'].get('minute', {})
        if minute_meta.get('status') != 'ok' or now-datetime.fromisoformat(minute_meta['updated_at']) > timedelta(minutes=30): view['minute'] = None
        alerts, state = detect(view, previous, now)
        summary, _ = detect(view, {}, now)
        messages = dict.fromkeys(c['message'] for c in summary['changes'] + alerts['changes'])
        weather['alert_text'] = ' '.join(messages) or '无提醒'
        state['location'] = weather['location']
        write(folder/'state.json', state)
    else:
        alerts = dict(checked_at=now.isoformat(), level='错误', changes=[], text='检查失败，无法判断重要变化；请勿沿用历史天气。')
        weather['alert_text'] = '检查失败，无法判断提醒'
    if weather['status'] == 'error':
        alerts['text'] += '\n' + weather['error']
        if alerts['level'] == '正常': alerts['level'] = '错误'
    weather['alerts'] = alerts
    write(ROOT/'weather.json', weather)
    write(folder/'alerts.json', alerts)
    write(folder/'latest_alert.txt', alerts['text']+'\n')
    print(alerts['text'])
    return 1 if weather['status'] == 'error' else 0

if __name__ == '__main__': sys.exit(main())
