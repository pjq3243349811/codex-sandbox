"""解析夹具仅用于测试，不发布为真实价格/招聘数据。"""
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_deals as deals
import fetch_jobs as jobs
from life_common import save_result


class LifeTests(unittest.TestCase):
    def test_only_dalian_outbound_quotes_with_source_links(self):
        page = '''<ul><li><a href="/DLC-SHA.html">大连 — 上海</a><a href="/DLC-SHA.html">¥260 起</a></li>
        <li><a href="/SHA-DLC.html">上海 — 大连 ¥100 起</a></li>
        <li><a href="https://evil.example/DLC-PEK.html">大连 — 北京 ¥1 起</a></li>
        <li><a href="/DLC-CAN.html">大连 — 广州 暂无报价</a></li></ul>'''
        result = deals.parse_deals(page)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['price'], 260)
        self.assertEqual(result[0]['destination'], '上海')
        self.assertIsNone(result[0]['date_start'])
        self.assertIn('未公布', result[0]['date_note'])

    def test_flight_date_comes_from_source_not_check_time(self):
        result = deals.parse_deals('<li><a href="/DLC-SHA.html?FDate=2026-12-01">大连—上海 ¥260 起</a></li>')
        self.assertEqual(result[0]['date_start'], '2026-12-01')
        with self.assertRaises(ValueError):
            deals.parse_deals('<html>验证码</html>')

    def test_failure_preserves_old_items_and_success_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'deals.json'
            old = dict(items=[{'id': 'old', 'price': 260}], updated_at='2025-01-01T00:00:00Z')
            path.write_text(json.dumps(old))
            def fail():
                raise OSError('not available')
            self.assertEqual(save_result(path, fail), 1)
            result = json.loads(path.read_text())
            self.assertEqual(result['items'], old['items'])
            self.assertEqual(result['updated_at'], old['updated_at'])
            self.assertEqual(result['status'], 'error')
            self.assertTrue(result['checked_at'])

    def test_partial_failure_keeps_missing_old_records_marked_historical(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'jobs.json'
            path.write_text(json.dumps(dict(items=[{'id': 'old'}], updated_at='2025-01-01T00:00:00Z')))
            save_result(path, lambda: ([{'id': 'new'}], ['source'], ['one list failed']))
            result = json.loads(path.read_text())
            self.assertEqual(result['items'][1], {'id': 'old', 'historical': True})
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['updated_at'], '2025-01-01T00:00:00Z')

    def test_row_specific_education_and_major(self):
        rows = [['单位名称', '岗位名称', '学历要求', '专业要求'],
                ['大连测试事业单位', '技术员', '大专及以上', '不限专业'],
                ['大连测试事业单位', '研究员', '本科及以上', '不限专业'],
                ['大连测试事业单位', '财务', '专科及以上', '会计学'],
                ['大连测试事业单位', '测试', '本科（不含专科）', '不限专业'],
                ['大连测试事业单位', '升本', '专科起点本科', '不限专业']]
        result = jobs.parse_rows(rows, '招聘公告', 'https://rsj.dl.gov.cn/art/test.html', '事业单位')
        self.assertEqual([r['position'] for r in result], ['技术员', '财务'])
        self.assertTrue(result[0]['unrestricted_major'])
        self.assertFalse(result[1]['unrestricted_major'])
        self.assertIsNone(result[0]['deadline'])

    def test_merged_unit_cells_and_commented_official_list(self):
        page = jobs.Page('''<!-- <record><![CDATA[<a href="/art/2026/1/1/a.html">大连事业单位招聘公告</a>]]></record> -->
        <table><tr><th>单位</th><th>岗位</th><th>学历</th><th>专业</th></tr>
        <tr><td rowspan="2">大连单位</td><td>技术</td><td>专科</td><td>不限</td></tr>
        <tr><td>文员</td><td>本科</td><td>中文</td></tr></table>''')
        self.assertEqual(page.links[0][0], '/art/2026/1/1/a.html')
        result = jobs.parse_rows(jobs.html_rows(page.rows), '招聘公告', 'https://rsj.dl.gov.cn/test', '事业单位')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['unit'], '大连单位')

    def test_no_inference_from_whole_article(self):
        page = jobs.Page('<p>本次大专可报，部分岗位不限专业。请下载岗位表。</p>')
        self.assertEqual(jobs.parse_rows(jobs.html_rows(page.rows), '公告', 'url', '事业单位'), [])
        self.assertIsNone(jobs.find_deadline('发布时间：2026年1月1日。面试时间：2026年3月1日'))
        self.assertIn('2026年2月3日', jobs.find_deadline('报名时间：2026年2月1日至2026年2月3日17时。'))
        self.assertFalse(jobs.official('https://rsj.dl.gov.cn.evil.example/'))

    def test_empty_or_blocked_lists_are_errors(self):
        with patch.object(jobs, 'fetch', return_value='<html>访问验证</html>'):
            with self.assertRaises(ValueError):
                jobs.collect()

    def test_spreadsheet_merged_cells(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest('岗位表解析依赖未安装')
        book = openpyxl.Workbook()
        sheet = book.active
        for row in [['单位', '岗位', '学历', '专业'], ['大连单位', 'A', '专科', '不限'], [None, 'B', '本科', '不限']]:
            sheet.append(row)
        sheet.merge_cells('A2:A3')
        stream = BytesIO()
        book.save(stream)
        rows = list(jobs.spreadsheet(stream.getvalue()))[0]
        self.assertEqual(rows[2][0], '大连单位')
        self.assertEqual(len(jobs.parse_rows(rows, '公告', 'url', '事业单位')), 1)


if __name__ == '__main__':
    unittest.main()
