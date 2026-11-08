"""每周读取大连官方招聘列表与岗位表；按岗位学历筛选，不按公告全文推断。"""
import hashlib
import re
import sys
import time
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse
from life_common import ROOT, fetch, save_result, text

SOURCES = [
    ('事业单位', 'https://rsj.dl.gov.cn/col/col4341/index.html'),
    ('国企', 'https://gzw.dl.gov.cn/'),
]


def official(url):
    host = urlparse(url).hostname or ''
    return urlparse(url).scheme in ('http', 'https') and (host == 'dl.gov.cn' or host.endswith('.dl.gov.cn'))


class Page(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.links, self.rows, self.parts = [], [], []
        self.anchor, self.row, self.cell = None, None, None
        self.skip = 0
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        if tag == 'a':
            self.anchor = [attrs.get('href', ''), [attrs.get('title', '')]]
        if tag == 'tr':
            self.row = []
        if tag in ('td', 'th') and self.row is not None:
            self.cell = []
            self.span = (int(attrs.get('rowspan', 1)), int(attrs.get('colspan', 1)))

    def handle_data(self, value):
        if self.skip:
            return
        self.parts.append(value)
        if self.anchor is not None:
            self.anchor[1].append(value)
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag == 'a' and self.anchor is not None:
            self.links.append((self.anchor[0], text(' '.join(self.anchor[1]))))
            self.anchor = None
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append((text(' '.join(self.cell)), *self.span))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_comment(self, value):
        # Hanweb 列表常将 record/CDATA 放在注释中。
        if '<a ' in value:
            extra = Page(value.replace('<![CDATA[', '').replace(']]>', ''))
            self.links.extend(extra.links)


def html_rows(rows):
    """展开岗位表的合并单元格，避免将同单位后续岗位错配。"""
    pending = {}
    result = []
    for cells in rows:
        row = {}
        for col, (value, remaining) in list(pending.items()):
            row[col] = value
            if remaining == 1:
                del pending[col]
            else:
                pending[col] = (value, remaining - 1)
        col = 0
        for value, rowspan, colspan in cells:
            while col in row:
                col += 1
            for offset in range(colspan):
                row[col + offset] = value
                if rowspan > 1:
                    pending[col + offset] = (value, rowspan - 1)
            col += colspan
        result.append([row.get(i, '') for i in range(max(row, default=-1) + 1)])
    return result


def eligible(education):
    value = re.sub(r'\s+', '', education)
    return bool(re.search(r'(大专|专科)', value)) and not bool(re.search(r'专升本|专科起点|大专起点', value)) and not bool(re.search(r'不(?:含|包括|接受|招收).{0,4}(?:大专|专科)|(?:大专|专科).{0,4}(?:除外|不可|不得)', value))


def parse_rows(rows, title, url, kind, deadline=None, attachment=None):
    headers = None
    result = []
    patterns = {'unit': r'招聘单位(?:名称)?|用人单位(?:名称)?|单位名称|单位', 'position': r'岗位名称|招聘岗位|职位名称|岗位|职位',
                'education': r'学历(?:要求|条件|学位)?(?:要求)?|学历及学位(?:要求|条件)?', 'major': r'专业要求|专业条件|所学专业|专业', 'deadline': r'报名截止|截止时间|截止日期'}
    for row in rows:
        row = [str(value or '').strip() for value in row]
        found = {key: next((i for i, value in enumerate(row) if re.fullmatch(pattern, re.sub(r'\s+', '', value))), None)
                 for key, pattern in patterns.items()}
        if found['education'] is not None and found['position'] is not None:
            headers = found
            continue
        if not headers:
            continue
        def get(key):
            index = headers[key]
            return row[index] if index is not None and index < len(row) else ''
        education = get('education')
        if not eligible(education) or not get('position') or not get('unit'):
            continue
        major = get('major')
        identity = '|'.join([url, get('unit'), get('position'), education, major])
        result.append(dict(id=hashlib.sha256(identity.encode()).hexdigest()[:20], unit=get('unit'),
                           position=get('position'), education=education, major=major or '详见原公告',
                           unrestricted_major=bool(re.fullmatch(r'(?:不限|不限专业|专业不限|无专业限制)', major)),
                           deadline=get('deadline') or deadline, source_url=url, attachment_url=attachment,
                           title=title, category=kind))
    return result


def find_deadline(content):
    # 仅在报名语境中找完整年月日，保留上下文及小时，不取发布日期/面试日期。
    for sentence in re.split(r'[。；\n]', content):
        if '报名' not in sentence or not re.search(r'截止|至|到', sentence):
            continue
        if re.search(r'20\d{2}\s*[年/-]\s*\d{1,2}\s*[月/-]\s*\d{1,2}', sentence):
            return sentence.strip()[:240]
    return None


def spreadsheet(data):
    if data.startswith(b'PK'):
        import openpyxl
        book = openpyxl.load_workbook(BytesIO(data), read_only=False, data_only=True)
        for sheet in book:
            # 展开单位/学历等合并格。
            for region in list(sheet.merged_cells.ranges):
                value = sheet.cell(region.min_row, region.min_col).value
                sheet.unmerge_cells(str(region))
                for row in sheet.iter_rows(min_row=region.min_row, max_row=region.max_row,
                                           min_col=region.min_col, max_col=region.max_col):
                    for cell in row:
                        cell.value = value
            yield list(sheet.values)
        book.close()
    else:
        import xlrd
        book = xlrd.open_workbook(file_contents=data, formatting_info=True)
        for sheet in book.sheets():
            rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            for rlo, rhi, clo, chi in sheet.merged_cells:
                for r in range(rlo, rhi):
                    for c in range(clo, chi):
                        rows[r][c] = rows[rlo][clo]
            yield rows


def collect():
    items, warnings = [], []
    for kind, source in SOURCES:
        try:
            listing = Page(fetch(source))
            # 国资委首页先定位官方“通知公告”列表，而非全网搜索。
            if source == 'https://gzw.dl.gov.cn/':
                list_url = next((urljoin(source, href) for href, label in listing.links
                                 if label.strip() == '通知公告' and official(urljoin(source, href))), None)
                if not list_url:
                    raise ValueError('未识别国资委通知公告列表')
                listing = Page(fetch(list_url))
            articles = {}
            for href, title in listing.links:
                url = urljoin(source, href)
                if official(url) and re.search(r'招聘|招录', title) and re.search(r'公告|启事|简章', title) and not re.search(r'公示|面试|笔试|成绩|拟聘|取消|核减', title):
                    articles[url] = title
            if not listing.links or not any('/art/' in href or '.shtml' in href for href, _ in listing.links):
                raise ValueError('列表为空或结构变化')
            for url, title in list(articles.items())[:30]:
                try:
                    time.sleep(0.3)
                    page = Page(fetch(url))
                    content = text(' '.join(page.parts))
                    # 排除编外派遣与民营单位，不将其冒充国企/事业单位。
                    if re.search(r'劳务派遣|编外|购买服务', title):
                        continue
                    if kind == '国企' and not re.search(r'国有|国企|集团|有限公司', title):
                        continue
                    deadline = find_deadline(content)
                    matches = parse_rows(html_rows(page.rows), title, url, kind, deadline)
                    for href, label in page.links:
                        attachment = urljoin(url, href)
                        if official(attachment) and re.search(r'岗位|职位|计划', label) and re.search(r'\.xlsx?(?:[?&#]|$)', attachment, re.I):
                            for rows in spreadsheet(fetch(attachment)):
                                matches.extend(parse_rows(rows, title, url, kind, deadline, attachment))
                    if not matches and re.search(r'大专|专科|岗位表|岗位计划|职位表', content):
                        warnings.append(f'{title[:45]}：未能核验大专岗位表，请查原公告')
                    items.extend(matches)
                except Exception as exc:
                    warnings.append(f'{title[:45]}：读取失败（{type(exc).__name__}）')
        except Exception as exc:
            warnings.append(f'{kind}列表读取失败（{type(exc).__name__}）')
    if len(warnings) == len(SOURCES) and not items and all('列表读取失败' in w for w in warnings):
        raise ValueError('所有官方列表不可用')
    return list({item['id']: item for item in items}.values()), [source for _, source in SOURCES], warnings


if __name__ == '__main__':
    sys.exit(save_result(ROOT / 'jobs.json', collect))
