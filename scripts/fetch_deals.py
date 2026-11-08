"""每日读取春秋航空公开大连出发低价页；仅接受原页面明确标价的航线。"""
import re
import sys
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
from life_common import ROOT, fetch, save_result, text

SOURCE = 'https://flights.ch.com/DLC-from.html'


class Routes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.block = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            if self.block is None:
                self.block = {'text': [], 'links': []}
            self.depth += 1
        if self.block is not None and tag == 'a' and attrs.get('href'):
            self.block['links'].append(attrs['href'])

    def handle_data(self, value):
        if self.block is not None:
            self.block['text'].append(value)

    def handle_endtag(self, tag):
        if tag == 'li' and self.block is not None:
            self.depth -= 1
            if not self.depth:
                self.items.append(self.block)
                self.block = None


def parse_deals(page):
    parser = Routes()
    parser.feed(page)
    result = {}
    for block in parser.items:
        label = text(' '.join(block['text']))
        route = re.search(r'大连\s*[—–－\-→]+\s*([^¥￥|]+?)\s*[|]?\s*[¥￥]\s*([\d,]+(?:\.\d+)?)', label)
        if not route:
            continue
        link = next((urljoin(SOURCE, x) for x in block['links']
                     if re.search(r'/DLC-[A-Z]{3}\.html', urljoin(SOURCE, x), re.I)), None)
        if not link or urlparse(link).hostname != 'flights.ch.com':
            continue
        price = float(route[2].replace(',', ''))
        if price <= 0:
            continue
        # 日期必须来自原文或购票链接，不把抓取日期当出行日期。
        dates = re.findall(r'20\d{2}-\d{2}-\d{2}', label)
        query_date = parse_qs(urlparse(link).query).get('FDate', [None])[0]
        date_start = dates[0] if dates else query_date
        date_end = dates[-1] if dates else query_date
        result[link] = dict(id=link, origin='大连', destination=route[1].strip(' |'),
                            price=price, currency='CNY', date_start=date_start, date_end=date_end,
                            date_note='来源未公布适用日期，请进入官网查价' if not date_start else '',
                            booking_url=link, source_url=SOURCE, source='春秋航空',
                            price_note='官网展示起价；税费、余票及适用日期以购票页为准')
    if not result:
        raise ValueError('未解析到可核验的大连出发报价')
    return sorted(result.values(), key=lambda x: x['price'])


def collect():
    return parse_deals(fetch(SOURCE)), [SOURCE], []


if __name__ == '__main__':
    sys.exit(save_result(ROOT / 'deals.json', collect))
