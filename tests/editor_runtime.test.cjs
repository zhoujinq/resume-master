const test = require('node:test');
const assert = require('node:assert/strict');
const editor = require('../assets/editor-runtime.js');
const JSZip = require('../assets/vendor/jszip.min.js');

function fixture() {
  return {
    schema: 'resume-editor-state/v1',
    accent: '#2F5BEA',
    base: { yamlSha256: 'a'.repeat(64), pdfSha256: 'b'.repeat(64) },
    photo: null,
    pages: [[
      { id: 'name', kind: 'name', html: '林示例', style: { font: 'serif', size: 34, line: 40, before: 0, after: 6 } },
      { id: 'b1', kind: 'bullet', html: '负责<strong>重点客户</strong>，收入<span style="color:#2F5BEA">42%</span>', style: { font: 'sans', size: 9.3, line: 13.8, before: 0, after: 2 } },
    ]],
  };
}

test('X04 字号、行距与段距按 0.1pt 归一化，避免浮点尾数', () => {
  assert.equal(editor.measure(9.300000000000001, 6, 72, 9.5), 9.3);
  assert.equal(editor.measure(13.75, 7, 100, 13.8), 13.8);
  assert.equal(editor.measure(999, 6, 72, 9.5), 72);
  assert.equal(editor.measure('bad', 6, 72, 9.5), 9.5);
});

test('X05 DOCX 字号诚实映射到 0.5pt，行距保留 0.05pt 精度', () => {
  assert.equal(editor.docxHalfPoints(9.1), 18);
  assert.equal(editor.docxHalfPoints(9.2), 18);
  assert.equal(editor.docxHalfPoints(9.3), 19);
  assert.equal(editor.docxTwips(13.8), 276);
  assert.equal(editor.docxTwips(13.85), 277);
  assert.deepEqual(editor.docxPrecisionWarnings(fixture()), ['b1: 9.3pt → 9.5pt']);
});

test('X03 清理脚本、事件属性与危险链接，只保留有限行内格式', () => {
  const dirty = '正常<script>alert(1)</script><img src=x onerror=alert(1)><strong onclick="x">粗体</strong><a href="javascript:alert(1)">坏链</a><a href="https://example.com">好链</a>';
  const clean = editor.sanitizeHtml(dirty);
  assert.equal(clean.includes('script'), false);
  assert.equal(clean.includes('img'), false);
  assert.equal(clean.includes('onclick'), false);
  assert.equal(clean.includes('javascript:'), false);
  assert.match(clean, /<strong>粗体<\/strong>/);
  assert.match(clean, /<a href="https:\/\/example.com">好链<\/a>/);
});

test('X03 行内 HTML 转 Run 时保留粗体、颜色和文本', () => {
  const runs = editor.htmlToRuns(fixture().pages[0][1].html, '#2F5BEA');
  assert.equal(runs.map(run => run.text).join(''), '负责重点客户，收入42%');
  assert.equal(runs.find(run => run.text === '重点客户').bold, true);
  assert.equal(runs.find(run => run.text === '42%').color, '#2F5BEA');
});

test('X10 数字变化提示复核，普通同义措辞变化不误报', () => {
  assert.equal(editor.numericChanged('负责<strong>42%</strong>增长', '推动42%增长'), false);
  assert.equal(editor.numericChanged('负责42%增长', '负责43%增长'), true);
  assert.equal(editor.numericChanged('2024.01—2025.02', '2024.01—2025.03'), true);
});

test('X06 最新状态生成真实 DOCX ZIP，而不是旧文本或截图', async () => {
  const state = fixture();
  state.pages[0][1].html = '修订后的<strong>最新文本</strong>42%';
  const result = await editor.buildDocx(state, JSZip, 'nodebuffer');
  assert.ok(Buffer.isBuffer(result.data));
  assert.equal(result.data.subarray(0, 2).toString(), 'PK');
  const zip = await JSZip.loadAsync(result.data);
  const xml = await zip.file('word/document.xml').async('string');
  assert.match(xml, /修订后的/);
  assert.match(xml, /<w:b\/>/);
  assert.match(xml, /<w:sz w:val="19"\/>/);
  assert.equal(xml.includes('负责重点客户'), false);
  assert.equal(zip.file('word/document.xml').name.endsWith('.xml'), true);
});

test('X06 超链接成为 DOCX 关系并可点击', async () => {
  const state = fixture();
  state.pages[0][1].html = '<a href="https://example.com/work">作品集</a>';
  const result = await editor.buildDocx(state, JSZip, 'nodebuffer');
  const zip = await JSZip.loadAsync(result.data);
  const document = await zip.file('word/document.xml').async('string');
  const rels = await zip.file('word/_rels/document.xml.rels').async('string');
  assert.match(document, /<w:hyperlink r:id=/);
  assert.match(rels, /Target="https:\/\/example.com\/work"/);
  assert.match(rels, /TargetMode="External"/);
});

test('X08 有照片时导出图片部件，无照片时不留空关系', async () => {
  const withPhoto = fixture();
  withPhoto.photo = { dataUri: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', widthMm: 22.005, heightMm: 30.7975, xMm: 171.185, yMm: 14.852 };
  const result = await editor.buildDocx(withPhoto, JSZip, 'nodebuffer');
  const zip = await JSZip.loadAsync(result.data);
  assert.ok(zip.file('word/media/photo.png'));
  const xml = await zip.file('word/document.xml').async('string');
  assert.match(xml, /<w:drawing>/);
  const without = await editor.buildDocx(fixture(), JSZip, 'nodebuffer');
  const plainZip = await JSZip.loadAsync(without.data);
  assert.equal(plainZip.file('word/media/photo.png'), null);
});

test('X08 极简状态不生成空章节或空链接段落', async () => {
  const state = { schema: 'resume-editor-state/v1', accent: '#2F5BEA', base: {}, photo: null, pages: [[{ id: 'body', kind: 'body', html: '只保留真实经历', style: { font: 'sans', size: 9.5, line: 13.8, before: 0, after: 2 } }]] };
  const result = await editor.buildDocx(state, JSZip, 'nodebuffer');
  const zip = await JSZip.loadAsync(result.data);
  const xml = await zip.file('word/document.xml').async('string');
  assert.match(xml, /只保留真实经历/);
  assert.equal(xml.includes('Vibe Coding'), false);
  assert.equal(xml.includes('<w:hyperlink'), false);
});

test('X09 编辑备份保留基哈希、当前内容和格式', () => {
  const state = fixture();
  state.base.docxBase64 = 'UEsDBgAAAA==';
  state.base.docxSha256 = 'd'.repeat(64);
  state.revision = 'v3.3.0-微调.2';
  const restored = editor.normalizeState(JSON.parse(JSON.stringify(state)));
  assert.equal(restored.base.pdfSha256, 'b'.repeat(64));
  assert.equal(restored.base.docxBase64, state.base.docxBase64);
  assert.equal(restored.base.docxSha256, state.base.docxSha256);
  assert.equal(restored.revision, state.revision);
  assert.equal(restored.pages[0][1].style.size, 9.3);
  assert.equal(editor.normalizeState({ pages: 'bad' }).pages.length, 0);
});

test('X11 XML 与 HTML 特殊字符不会破坏文档结构', () => {
  assert.equal(editor.xmlEscape('A&B<"北极星">'), 'A&amp;B&lt;&quot;北极星&quot;&gt;');
  const runs = editor.htmlToRuns('A&amp;B&nbsp;C', '#2F5BEA');
  assert.equal(runs.map(run => run.text).join(''), 'A&B\u00a0C');
  const normalizedXml = editor.singleXmlDeclaration('<?xml version="1.0"?><?xml version="1.0"?><x/>');
  assert.equal((normalizedXml.match(/<\?xml/g) || []).length, 1);
  assert.equal(normalizedXml.endsWith('<x/>'), true);
});

test('X09 不同封板 PDF 的编辑备份不能互相恢复', () => {
  const other = fixture();
  other.base.pdfSha256 = 'c'.repeat(64);
  assert.equal(editor.sameBase(fixture(), other), false);
  assert.equal(editor.sameBase(fixture(), fixture()), true);
  const oldStructure = fixture();
  oldStructure.pages[0].pop();
  assert.equal(editor.sameStructure(fixture(), oldStructure), false);
  assert.equal(editor.sameStructure(fixture(), fixture()), true);
});

test('X05 只有发生 DOCX 精度取整时才提示', () => {
  const state = fixture();
  state.pages[0][1].style.size = 9.5;
  assert.deepEqual(editor.docxPrecisionWarnings(state), []);
});
