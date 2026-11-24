/* resume-master v3.3.0 editor runtime. No network dependency. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") {
    window.ResumeEditor = api;
    window.addEventListener("DOMContentLoaded", function () {
      if (window.RESUME_DATA && document.getElementById("editor")) api.initEditor(window.RESUME_DATA);
    });
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const FONT_SERIF = "思源宋体";
  const FONT_SANS = "思源黑体";
  const DEFAULTS = {
    name: { font: "serif", size: 34, line: 40, before: 0, after: 6 },
    role: { font: "sans", size: 10.5, line: 14, before: 0, after: 2 },
    contact: { font: "sans", size: 8, line: 12, before: 8, after: 2 },
    links: { font: "sans", size: 8, line: 12, before: 0, after: 0 },
    section: { font: "serif", size: 13, line: 16.5, before: 7.8, after: 4.9 },
    note: { font: "sans", size: 8.5, line: 12, before: 0, after: 2 },
    entry: { font: "sans", size: 9.5, line: 14, before: 7.8, after: 2 },
    bullet: { font: "sans", size: 9.5, line: 13.8, before: 0, after: 2 },
    body: { font: "sans", size: 9.5, line: 13.8, before: 0, after: 2 }
  };

  function measure(value, min, max, fallback) {
    const number = Number(value);
    const safe = Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
    return Math.round((safe + Number.EPSILON) * 10) / 10;
  }

  function docxHalfPoints(pt) {
    return Math.round((Number(pt) + Number.EPSILON) * 2);
  }

  function docxTwips(pt) {
    return Math.round((Number(pt) + Number.EPSILON) * 20);
  }

  function xmlEscape(value) {
    return String(value == null ? "" : value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
  }

  function normalizeColor(value, fallback) {
    const text = String(value || "").trim();
    const short = /^#([0-9a-f]{3})$/i.exec(text);
    if (short) return "#" + short[1].split("").map(function (c) { return c + c; }).join("").toUpperCase();
    if (/^#[0-9a-f]{6}$/i.test(text)) return text.toUpperCase();
    const rgb = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,[^)]*)?\)$/i.exec(text);
    if (rgb) return "#" + rgb.slice(1, 4).map(function (part) { return Math.min(255, Number(part)).toString(16).padStart(2, "0"); }).join("").toUpperCase();
    return fallback || "";
  }

  function decodeEntities(value) {
    const named = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'", "&nbsp;": "\u00a0" };
    return String(value || "").replace(/&(amp|lt|gt|quot|apos|nbsp);/gi, function (token) { return named[token.toLowerCase()] || token; }).replace(/&#(x[0-9a-f]+|\d+);/gi, function (_, code) {
      const number = code[0].toLowerCase() === "x" ? parseInt(code.slice(1), 16) : parseInt(code, 10);
      return Number.isFinite(number) && number >= 0 && number <= 0x10ffff ? String.fromCodePoint(number) : "";
    });
  }

  function safeHref(tag) {
    const match = /\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i.exec(tag);
    const href = decodeEntities(match ? (match[1] || match[2] || match[3] || "") : "").trim();
    return /^(https?:\/\/|mailto:|tel:)/i.test(href) ? href : "";
  }

  function sanitizeHtml(input) {
    let source = String(input == null ? "" : input);
    source = source.replace(/<!--[\s\S]*?-->/g, "");
    source = source.replace(/<\s*(script|style|iframe|object|embed|svg|math|form)\b[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, "");
    return source.replace(/<[^>]*>/g, function (tag) {
      const closing = /^<\s*\//.test(tag);
      const nameMatch = /^<\s*\/?\s*([a-z0-9]+)/i.exec(tag);
      const name = nameMatch ? nameMatch[1].toLowerCase() : "";
      if (name === "br") return "<br>";
      if (name === "div" || name === "p") return closing ? "<br>" : "";
      if (name === "strong" || name === "b") return closing ? "</strong>" : "<strong>";
      if (name === "a") {
        if (closing) return "</a>";
        const href = safeHref(tag);
        return href ? '<a href="' + xmlEscape(href) + '">' : "";
      }
      if (name === "span" || name === "font") {
        if (closing) return "</span>";
        const styles = [];
        const colorMatch = /(?:color\s*:\s*|color\s*=\s*["']?)(#[0-9a-f]{3,6}|rgba?\([^)"']+\))/i.exec(tag);
        const color = colorMatch ? normalizeColor(colorMatch[1], "") : "";
        if (color) styles.push("color:" + color);
        if (/font-weight\s*:\s*(bold|[6-9]00)/i.test(tag)) styles.push("font-weight:bold");
        const accent = /class\s*=\s*["'][^"']*\baccent\b/i.test(tag) ? ' class="accent"' : "";
        return "<span" + accent + (styles.length ? ' style="' + styles.join(";") + '"' : "") + ">";
      }
      return "";
    });
  }

  function htmlToRuns(input, accent) {
    const source = sanitizeHtml(input);
    const tokens = source.split(/(<[^>]+>)/);
    const stack = [{ bold: false, color: "", href: "" }];
    const runs = [];
    function current() { return stack[stack.length - 1]; }
    function pushRun(run) {
      const previous = runs[runs.length - 1];
      if (run.text && previous && !previous.break && !run.break && previous.bold === run.bold && previous.color === run.color && previous.href === run.href) previous.text += run.text;
      else runs.push(run);
    }
    tokens.forEach(function (token) {
      if (!token) return;
      if (token[0] !== "<") {
        const text = decodeEntities(token).replace(/\r/g, "");
        if (text) pushRun({ text: text, bold: current().bold, color: current().color, href: current().href });
        return;
      }
      if (/^<br>$/i.test(token)) {
        runs.push({ break: true, bold: current().bold, color: current().color, href: current().href });
        return;
      }
      const closing = /^<\//.test(token);
      if (closing) {
        if (stack.length > 1) stack.pop();
        return;
      }
      const next = { bold: current().bold, color: current().color, href: current().href };
      if (/^<strong>$/i.test(token)) next.bold = true;
      if (/^<span/i.test(token)) {
        if (/class="accent"/i.test(token)) { next.color = accent; next.bold = true; }
        const color = /color:(#[0-9A-F]{6})/i.exec(token);
        if (color) next.color = color[1].toUpperCase();
        if (/font-weight:bold/i.test(token)) next.bold = true;
      }
      if (/^<a /i.test(token)) next.href = safeHref(token);
      stack.push(next);
    });
    return runs;
  }

  function plainText(input) {
    return htmlToRuns(input, "#000000").map(function (run) { return run.break ? "\n" : run.text || ""; }).join("");
  }

  function numericTokens(input) {
    return (plainText(input).match(/[A-Za-z]*\d[\dA-Za-z./:%—–~-]*/g) || []).sort();
  }

  function numericChanged(before, after) {
    return JSON.stringify(numericTokens(before)) !== JSON.stringify(numericTokens(after));
  }

  function normalizeStyle(kind, style) {
    const base = DEFAULTS[kind] || DEFAULTS.body;
    const value = style || {};
    return {
      font: value.font === "serif" ? "serif" : (value.font === "sans" ? "sans" : base.font),
      size: measure(value.size == null ? base.size : value.size, 6, 72, base.size),
      line: measure(value.line == null ? base.line : value.line, 7, 100, base.line),
      before: measure(value.before == null ? base.before : value.before, 0, 60, base.before),
      after: measure(value.after == null ? base.after : value.after, 0, 60, base.after)
    };
  }

  function normalizeBlock(block, index) {
    const kind = DEFAULTS[block && block.kind] ? block.kind : "body";
    const result = {
      id: String(block && block.id || "block-" + index).replace(/[^a-zA-Z0-9_-]/g, "-"),
      kind: kind,
      html: sanitizeHtml(block && block.html || ""),
      style: normalizeStyle(kind, block && block.style)
    };
    if (block && block.fields) {
      result.fields = {};
      ["org", "role", "date", "note"].forEach(function (key) { result.fields[key] = sanitizeHtml(block.fields[key] || ""); });
      if (block.fields.url && /^(https?:\/\/|mailto:)/i.test(block.fields.url)) result.fields.url = block.fields.url;
    }
    return result;
  }

  function sameBase(left, right) {
    const leftHash = left && left.base && left.base.pdfSha256;
    const rightHash = right && right.base && right.base.pdfSha256;
    return Boolean(leftHash && rightHash && leftHash === rightHash);
  }

  function sameStructure(left, right) {
    function ids(input) {
      const result = [];
      (input && input.pages || []).forEach(function (page) { page.forEach(function (block) { result.push(block.id + ":" + block.kind); }); });
      return result;
    }
    const a = ids(left), b = ids(right);
    return a.length === b.length && a.every(function (value, index) { return value === b[index]; });
  }

  function normalizeState(input) {
    const source = input && typeof input === "object" ? input : {};
    const result = {
      schema: "resume-editor-state/v1",
      revision: String(source.revision || "v3.3.0-微调.1").slice(0, 60),
      accent: normalizeColor(source.accent, "#2F5BEA"),
      base: source.base && typeof source.base === "object" ? {
        yamlSha256: String(source.base.yamlSha256 || ""), pdfSha256: String(source.base.pdfSha256 || ""),
        docxSha256: String(source.base.docxSha256 || ""), docxBase64: String(source.base.docxBase64 || "")
      } : {},
      photo: null,
      pages: []
    };
    if (source.photo && /^data:image\/(png|jpeg);base64,/i.test(source.photo.dataUri || "")) {
      result.photo = {
        dataUri: source.photo.dataUri,
        widthMm: Number(source.photo.widthMm) || 22.005,
        heightMm: Number(source.photo.heightMm) || 30.7975,
        xMm: Number(source.photo.xMm) || 171.185,
        yMm: Number(source.photo.yMm) || 14.852
      };
    }
    if (Array.isArray(source.pages)) {
      result.pages = source.pages.map(function (page) {
        return (Array.isArray(page) ? page : []).map(normalizeBlock).filter(function (block) {
          return plainText(block.html).trim() || block.fields && Object.values(block.fields).some(function (value) { return plainText(value).trim(); });
        });
      }).filter(function (page) { return page.length > 0; });
    }
    return result;
  }

  function eachBlock(state, callback) {
    state.pages.forEach(function (page, pageIndex) { page.forEach(function (block, blockIndex) { callback(block, pageIndex, blockIndex); }); });
  }

  function docxPrecisionWarnings(input) {
    const state = normalizeState(input);
    const warnings = [];
    eachBlock(state, function (block) {
      const rounded = docxHalfPoints(block.style.size) / 2;
      if (Math.abs(rounded - block.style.size) > 0.001) warnings.push(block.id + ": " + block.style.size.toFixed(1) + "pt → " + rounded.toFixed(1) + "pt");
    });
    return warnings;
  }

  function runProperties(run, block, accent, overrides) {
    const options = overrides || {};
    const fontName = (options.font || block.style.font) === "serif" ? FONT_SERIF : FONT_SANS;
    const bold = options.bold != null ? options.bold : run.bold || ["name", "role", "section"].includes(block.kind);
    const defaultColor = block.kind === "role" ? accent : (block.kind === "contact" || block.kind === "links" || block.kind === "note" ? "#5A6069" : "#2B3038");
    const color = normalizeColor(options.color || run.color || defaultColor, "#2B3038").slice(1);
    const size = docxHalfPoints(options.size || block.style.size);
    return "<w:rPr><w:rFonts w:ascii=\"" + fontName + "\" w:eastAsia=\"" + fontName + "\" w:hAnsi=\"" + fontName + "\"/>" +
      (bold ? "<w:b/><w:bCs/>" : "") + "<w:color w:val=\"" + color + "\"/><w:sz w:val=\"" + size + "\"/><w:szCs w:val=\"" + size + "\"/>" +
      (run.href ? '<w:u w:val="single"/>' : "") + '<w:lang w:val="zh-CN" w:eastAsia="zh-CN"/></w:rPr>';
  }

  function runXml(run, block, state, relationships, overrides) {
    if (run.break) return "<w:r>" + runProperties(run, block, state.accent, overrides) + "<w:br/></w:r>";
    const properties = runProperties(run, block, state.accent, overrides);
    let content = "";
    const parts = String(run.text || "").split("\n");
    parts.forEach(function (part, index) {
      if (index) content += "<w:br/>";
      if (part) content += "<w:t xml:space=\"preserve\">" + xmlEscape(part) + "</w:t>";
    });
    if (!content) return "";
    const xml = "<w:r>" + properties + content + "</w:r>";
    if (run.href) {
      const id = "rIdEditLink" + (++relationships.linkCount);
      relationships.items.push({ id: id, type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", target: run.href, mode: "External" });
      return '<w:hyperlink r:id="' + id + '" w:history="1">' + xml + "</w:hyperlink>";
    }
    return xml;
  }

  function runsXml(html, block, state, relationships, overrides) {
    return htmlToRuns(html, state.accent).map(function (run) { return runXml(run, block, state, relationships, overrides); }).join("");
  }

  function photoDrawing(relationshipId, photo) {
    const cx = Math.round(photo.widthMm * 36000);
    const cy = Math.round(photo.heightMm * 36000);
    const x = Math.round(photo.xMm * 36000);
    const y = Math.round(photo.yMm * 36000);
    return '<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251659264" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">' +
      '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>' + x + '</wp:posOffset></wp:positionH><wp:positionV relativeFrom="page"><wp:posOffset>' + y + '</wp:posOffset></wp:positionV>' +
      '<wp:extent cx="' + cx + '" cy="' + cy + '"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/><wp:docPr id="1" name="简历照片"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>' +
      '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="photo"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="' + relationshipId + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + cx + '" cy="' + cy + '"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>';
  }

  function paragraphXml(block, state, relationships, photoRelationship, suppressBullet) {
    const style = block.style;
    const properties = ['<w:spacing w:before="' + docxTwips(style.before) + '" w:after="' + docxTwips(style.after) + '" w:line="' + docxTwips(style.line) + '" w:lineRule="exact"/>'];
    if (["name", "role", "contact", "links", "section", "entry"].includes(block.kind)) properties.push("<w:keepNext/>");
    if (block.kind === "section") properties.push('<w:pBdr><w:bottom w:val="single" w:sz="5" w:space="5" w:color="1A1D22"/></w:pBdr>');
    if (block.kind === "role") properties.push('<w:pBdr><w:bottom w:val="single" w:sz="7" w:space="6" w:color="1A1D22"/></w:pBdr>');
    if (block.kind === "bullet" && !suppressBullet) properties.push('<w:ind w:left="270" w:hanging="270"/>');
    let content = "";
    if (block.kind === "entry" && block.fields) {
      properties.push('<w:tabs><w:tab w:val="right" w:pos="9978"/></w:tabs>');
      content += runsXml(block.fields.org, block, state, relationships, { bold: true });
      if (plainText(block.fields.role).trim()) content += runsXml(" — " + block.fields.role, block, state, relationships, { color: "#5A6069" });
      if (block.fields.url) {
        content += runXml({ text: " ↗", href: block.fields.url, bold: false, color: state.accent }, block, state, relationships, {});
      }
      content += "<w:r>" + runProperties({}, block, state.accent, { font: "serif", color: "#857F74" }) + "<w:tab/></w:r>";
      content += runsXml(block.fields.date, block, state, relationships, { font: "serif", color: "#857F74" });
    } else if (block.kind === "section" && block.fields && plainText(block.fields.note).trim()) {
      properties.push('<w:tabs><w:tab w:val="right" w:pos="9978"/></w:tabs>');
      content += runsXml(block.html, block, state, relationships, {});
      content += "<w:r>" + runProperties({}, block, state.accent, { font: "sans", color: "#5A6069", size: 8, bold: false }) + "<w:tab/></w:r>";
      content += runsXml(block.fields.note, block, state, relationships, { font: "sans", color: "#5A6069", size: 8, bold: false });
    } else {
      if (block.kind === "bullet" && !suppressBullet) content += runXml({ text: "• ", bold: false, color: "#2B3038", href: "" }, block, state, relationships, {});
      content += runsXml(block.html, block, state, relationships, {});
    }
    if (block.kind === "name" && photoRelationship) content += photoDrawing(photoRelationship.id, state.photo);
    if (!content) return "";
    return "<w:p><w:pPr>" + properties.join("") + "</w:pPr>" + content + "</w:p>";
  }

  function bytesFromDataUri(dataUri) {
    const match = /^data:image\/(png|jpeg);base64,(.+)$/i.exec(dataUri || "");
    if (!match) throw new Error("照片 data URI 无效");
    const base64 = match[2];
    if (typeof Buffer !== "undefined") return { bytes: Buffer.from(base64, "base64"), extension: match[1].toLowerCase() === "jpeg" ? "jpg" : "png" };
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
    return { bytes: bytes, extension: match[1].toLowerCase() === "jpeg" ? "jpg" : "png" };
  }

  function singleXmlDeclaration(xml) {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + String(xml).replace(/^(?:\s*<\?xml[^>]*\?>\s*)+/, "");
  }

  async function buildDocxFromBase(state, JSZip, outputType) {
    if (typeof DOMParser === "undefined" || typeof XMLSerializer === "undefined") throw new Error("当前环境不能解析封板 DOCX XML");
    const binary = atob(state.base.docxBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const zip = await JSZip.loadAsync(bytes);
    const documentPart = zip.file("word/document.xml");
    const relationshipsPart = zip.file("word/_rels/document.xml.rels");
    if (!documentPart || !relationshipsPart) throw new Error("封板 DOCX 缺少正文或关系部件");
    const parser = new DOMParser();
    const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
    const documentXml = await documentPart.async("string");
    const doc = parser.parseFromString(documentXml, "application/xml");
    if (doc.getElementsByTagName("parsererror").length) throw new Error("封板 DOCX 正文 XML 无法解析");
    const body = doc.getElementsByTagNameNS(W, "body")[0];
    const paragraphs = Array.from(body.children).filter(function (node) { return node.localName === "p"; });
    const blocks = [];
    state.pages.forEach(function (page) { page.forEach(function (block) { blocks.push(block); }); });
    if (paragraphs.length !== blocks.length) throw new Error("封板 DOCX 段落数 " + paragraphs.length + " 与编辑器区块数 " + blocks.length + " 不一致，请使用对应的最终 DOCX 重新生成编辑器");
    const relationships = { items: [], linkCount: 0 };
    function directChild(element, localName) {
      return Array.from(element.childNodes).find(function (node) { return node.nodeType === 1 && node.localName === localName; }) || null;
    }
    paragraphs.forEach(function (original, index) {
      const originalPpr = directChild(original, "pPr");
      const suppressBullet = Boolean(originalPpr && directChild(originalPpr, "numPr"));
      const generatedDoc = parser.parseFromString('<w:document xmlns:w="' + W + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' + paragraphXml(blocks[index], state, relationships, null, suppressBullet) + '</w:document>', "application/xml");
      const generated = generatedDoc.getElementsByTagNameNS(W, "p")[0];
      if (!generated) throw new Error("第 " + (index + 1) + " 段没有可导出的内容");
      const generatedPpr = directChild(generated, "pPr");
      const ppr = originalPpr ? originalPpr.cloneNode(true) : (generatedPpr ? generatedPpr.cloneNode(true) : null);
      const newSpacing = generatedPpr && directChild(generatedPpr, "spacing");
      if (ppr && newSpacing) {
        const oldSpacing = directChild(ppr, "spacing");
        const importedSpacing = doc.importNode(newSpacing, true);
        if (oldSpacing) ppr.replaceChild(importedSpacing, oldSpacing);
        else ppr.insertBefore(importedSpacing, ppr.firstChild);
      }
      const drawings = Array.from(original.childNodes).filter(function (node) {
        return node.nodeType === 1 && node.localName === "r" && node.getElementsByTagNameNS(W, "drawing").length;
      }).map(function (node) {
        let sibling = node.nextSibling, followingText = "";
        while (sibling) {
          const text = String(sibling.textContent || "").trim();
          if (text) { followingText = text.slice(0, 48); break; }
          sibling = sibling.nextSibling;
        }
        return { node: node.cloneNode(true), followingText: followingText };
      });
      while (original.firstChild) original.removeChild(original.firstChild);
      if (ppr) original.appendChild(ppr);
      Array.from(generated.childNodes).forEach(function (node) {
        if (node.nodeType === 1 && node.localName === "pPr") return;
        original.appendChild(doc.importNode(node, true));
      });
      drawings.forEach(function (record) {
        const target = record.followingText ? Array.from(original.childNodes).find(function (node) {
          return node.nodeType === 1 && node.localName !== "pPr" && String(node.textContent || "").includes(record.followingText);
        }) : null;
        if (target) original.insertBefore(record.node, target);
        else original.appendChild(record.node);
      });
    });
    const relDoc = parser.parseFromString(await relationshipsPart.async("string"), "application/xml");
    const relRoot = relDoc.documentElement;
    relationships.items.forEach(function (item) {
      const relation = relDoc.createElementNS(relRoot.namespaceURI, "Relationship");
      relation.setAttribute("Id", item.id);
      relation.setAttribute("Type", item.type);
      relation.setAttribute("Target", item.target);
      if (item.mode) relation.setAttribute("TargetMode", item.mode);
      relRoot.appendChild(relation);
    });
    const serializer = new XMLSerializer();
    zip.file("word/document.xml", singleXmlDeclaration(serializer.serializeToString(doc)));
    zip.file("word/_rels/document.xml.rels", singleXmlDeclaration(serializer.serializeToString(relDoc)));
    const data = await zip.generateAsync({ type: outputType || "blob", compression: "DEFLATE" });
    return { data: data, warnings: docxPrecisionWarnings(state), state: state, template: "frozen-docx" };
  }

  async function buildDocx(input, JSZip, outputType) {
    if (!JSZip) throw new Error("缺少内联 JSZip，无法导出 DOCX");
    const state = normalizeState(input);
    if (state.base.docxBase64) return buildDocxFromBase(state, JSZip, outputType);
    const zip = new JSZip();
    const relationships = { items: [], linkCount: 0 };
    let photoRelationship = null;
    let photoInfo = null;
    if (state.photo) {
      photoInfo = bytesFromDataUri(state.photo.dataUri);
      photoRelationship = { id: "rIdPhoto", type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", target: "media/photo." + photoInfo.extension };
      relationships.items.push(photoRelationship);
      zip.file("word/media/photo." + photoInfo.extension, photoInfo.bytes);
    }
    relationships.items.push({ id: "rIdStyles", type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", target: "styles.xml" });
    relationships.items.push({ id: "rIdSettings", type: "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings", target: "settings.xml" });
    const body = [];
    state.pages.forEach(function (page, pageIndex) {
      if (pageIndex) body.push('<w:p><w:r><w:br w:type="page"/></w:r></w:p>');
      page.forEach(function (block) { body.push(paragraphXml(block, state, relationships, photoRelationship)); });
    });
    body.push('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="964" w:bottom="1021" w:left="964" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>');
    const documentXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>' + body.join("") + "</w:body></w:document>";
    const stylesXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="思源黑体" w:eastAsia="思源黑体" w:hAnsi="思源黑体"/><w:sz w:val="19"/><w:szCs w:val="19"/><w:lang w:val="zh-CN" w:eastAsia="zh-CN"/></w:rPr></w:rPrDefault><w:pPrDefault/></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>';
    const contentTypes = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' + (photoInfo ? '<Default Extension="' + photoInfo.extension + '" ContentType="image/' + (photoInfo.extension === "jpg" ? "jpeg" : "png") + '"/>' : "") + '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>';
    const documentRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + relationships.items.map(function (item) { return '<Relationship Id="' + item.id + '" Type="' + item.type + '" Target="' + xmlEscape(item.target) + '"' + (item.mode ? ' TargetMode="' + item.mode + '"' : "") + "/>"; }).join("") + "</Relationships>";
    const rootRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>';
    const core = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>封板后微调简历</dc:title><dc:creator>resume-master v3.3.0</dc:creator><cp:lastModifiedBy>resume-master v3.3.0</cp:lastModifiedBy><dc:description>派生编辑；YAML ' + xmlEscape(state.base.yamlSha256 || "") + "；PDF " + xmlEscape(state.base.pdfSha256 || "") + "</dc:description></cp:coreProperties>";
    zip.file("[Content_Types].xml", contentTypes);
    zip.file("_rels/.rels", rootRels);
    zip.file("word/document.xml", documentXml);
    zip.file("word/styles.xml", stylesXml);
    zip.file("word/settings.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:defaultTabStop w:val="420"/></w:settings>');
    zip.file("word/_rels/document.xml.rels", documentRels);
    zip.file("docProps/core.xml", core);
    const data = await zip.generateAsync({ type: outputType || "blob", compression: "DEFLATE" });
    return { data: data, warnings: docxPrecisionWarnings(state), state: state };
  }

  function download(data, filename, type) {
    const blob = data instanceof Blob ? data : new Blob([data], { type: type || "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  }

  function initEditor(initialData) {
    const editor = document.getElementById("editor");
    if (!editor) return null;
    const initial = normalizeState(initialData);
    let state = normalizeState(initialData);
    let lastBlockId = null;
    let savedRange = null;
    let saveTimer = null;
    const storageKey = "resume-master-editor:" + String(initial.base.pdfSha256 || "local").slice(0, 20);
    const $ = function (id) { return document.getElementById(id); };
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const candidate = normalizeState(JSON.parse(saved));
        if (sameBase(candidate, initial) && sameStructure(candidate, initial) && candidate.pages.length) state = candidate;
      }
    } catch (error) { console.warn("无法恢复本地编辑状态", error); }

    function status(message, warning) {
      $("status").textContent = message;
      $("status").classList.toggle("warning", Boolean(warning));
    }

    function blockSignature(block) {
      if (block.kind === "entry" && block.fields) return [block.fields.org, block.fields.role, block.fields.date].join("\n");
      if (block.kind === "section" && block.fields) return [block.html, block.fields.note].join("\n");
      return block.html;
    }

    function findBlock(id, source) {
      let found = null;
      eachBlock(source || state, function (block) { if (block.id === id) found = block; });
      return found;
    }

    function blockElement(id) {
      return Array.from(editor.querySelectorAll("[data-block]")).find(function (element) { return element.dataset.id === id; }) || null;
    }

    function blockHtml(block) {
      const style = '--fs:' + block.style.size + 'pt;--lh:' + block.style.line + 'pt;--before:' + block.style.before + 'pt;--after:' + block.style.after + 'pt';
      const open = '<div class="resume-block block-' + block.kind + '" data-block="1" data-id="' + block.id + '" style="' + style + '">';
      if (block.kind === "entry" && block.fields) {
        const link = block.fields.url ? '<a class="entry-link" href="' + xmlEscape(block.fields.url) + '" contenteditable="false" title="链接">↗</a>' : "";
        return open + '<div class="entry-line"><span class="entry-org" contenteditable="true" data-field="org">' + block.fields.org + '</span><span class="entry-role" contenteditable="true" data-field="role">' + block.fields.role + '</span>' + link + '<span class="entry-date" contenteditable="true" data-field="date">' + block.fields.date + '</span></div></div>';
      }
      if (block.kind === "section" && block.fields && plainText(block.fields.note).trim()) {
        return open + '<div class="section-line"><span class="editable" contenteditable="true" data-editable="html">' + block.html + '</span><span class="section-note" contenteditable="true" data-field="note">' + block.fields.note + "</span></div></div>";
      }
      return open + '<div class="editable" contenteditable="true" data-editable="html" spellcheck="false">' + block.html + "</div></div>";
    }

    function render() {
      document.documentElement.style.setProperty("--accent", state.accent);
      $("accentColor").value = state.accent;
      $("revision").value = state.revision;
      editor.innerHTML = state.pages.map(function (page, pageIndex) {
        const photo = pageIndex === 0 && state.photo ? '<img class="resume-photo" alt="照片" src="' + state.photo.dataUri + '">' : "";
        return '<section class="resume-page" data-page="' + pageIndex + '" aria-label="简历第' + (pageIndex + 1) + '页">' + photo + page.map(blockHtml).join("") + "</section>";
      }).join("");
      lastBlockId = null;
      savedRange = null;
      requestAnimationFrame(updateWarnings);
    }

    function syncFromDom() {
      state.pages.forEach(function (page, pageIndex) {
        const pageElement = editor.querySelector('[data-page="' + pageIndex + '"]');
        if (!pageElement) return;
        page.forEach(function (block) {
          const element = Array.from(pageElement.querySelectorAll("[data-block]")).find(function (node) { return node.dataset.id === block.id; });
          if (!element) return;
          if (block.kind === "entry" && block.fields) {
            ["org", "role", "date"].forEach(function (key) {
              const field = element.querySelector('[data-field="' + key + '"]');
              if (field) block.fields[key] = sanitizeHtml(field.innerHTML);
            });
          } else if (block.kind === "section" && block.fields) {
            const note = element.querySelector('[data-field="note"]');
            const title = element.querySelector('[data-editable]');
            if (note) block.fields.note = sanitizeHtml(note.innerHTML);
            if (title) block.html = sanitizeHtml(title.innerHTML);
          } else {
            const editable = element.querySelector("[data-editable]");
            if (editable) block.html = sanitizeHtml(editable.innerHTML);
          }
        });
      });
      return state;
    }

    function save() {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () {
        try {
          localStorage.setItem(storageKey, JSON.stringify(state));
          const time = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
          status("已自动保存 · " + time, false);
        } catch (error) { status("自动保存失败，请立即备份编辑数据", true); }
      }, 180);
    }

    function updateWarnings() {
      let changed = 0;
      eachBlock(state, function (block) {
        const original = findBlock(block.id, initial);
        if (original && numericChanged(blockSignature(original), blockSignature(block))) changed += 1;
      });
      $("factWarning").hidden = changed === 0;
      $("factWarning").textContent = changed ? "有 " + changed + " 段数字发生变化。可以继续编辑和导出，但请重新核对事实、归属与时间。" : "";
      let overflow = 0;
      editor.querySelectorAll(".resume-page").forEach(function (page) {
        const capacity = Math.ceil(297 / 25.4 * 96) + 4;
        if (page.scrollHeight > capacity) overflow += 1;
      });
      $("overflowWarning").hidden = overflow === 0;
      $("overflowWarning").textContent = overflow ? "有 " + overflow + " 页内容可能增页。打印前请检查分页，系统不会裁掉内容。" : "";
    }

    function changed(message) {
      syncFromDom();
      save();
      updateWarnings();
      if (message) status(message, false);
    }

    function selectionInside() {
      const selection = window.getSelection();
      return selection && selection.rangeCount && editor.contains(selection.anchorNode) ? selection : null;
    }

    function rememberSelection() {
      const selection = selectionInside();
      if (!selection) return;
      savedRange = selection.getRangeAt(0).cloneRange();
      const element = selection.anchorNode.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection.anchorNode.parentElement;
      const block = element && element.closest("[data-block]");
      if (block) {
        lastBlockId = block.dataset.id;
        const current = findBlock(lastBlockId);
        if (current) {
          $("fontSize").value = current.style.size.toFixed(1);
          $("lineHeight").value = current.style.line.toFixed(1);
          $("paragraphSpace").value = current.style.after.toFixed(1);
        }
      }
    }

    function restoreSelection() {
      if (!savedRange) return false;
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange);
      return true;
    }

    function exec(command, value) {
      restoreSelection();
      document.execCommand("styleWithCSS", false, true);
      document.execCommand(command, false, value == null ? null : value);
      rememberSelection();
      changed();
    }

    function targetBlocks() {
      const current = findBlock(lastBlockId);
      if (!current) return [];
      const scope = $("styleScope").value;
      const targets = [];
      eachBlock(state, function (block) {
        if (scope === "all" || scope === "kind" && block.kind === current.kind || scope === "current" && block.id === current.id) targets.push(block);
      });
      return targets;
    }

    function applyTypography() {
      syncFromDom();
      const targets = targetBlocks();
      if (!targets.length) { status("请先把光标放进要调整的段落", true); return; }
      targets.forEach(function (block) {
        block.style.size = measure($("fontSize").value, 6, 72, block.style.size);
        block.style.line = measure($("lineHeight").value, 7, 100, block.style.line);
        block.style.after = measure($("paragraphSpace").value, 0, 60, block.style.after);
        const element = blockElement(block.id);
        if (element) {
          element.style.setProperty("--fs", block.style.size + "pt");
          element.style.setProperty("--lh", block.style.line + "pt");
          element.style.setProperty("--after", block.style.after + "pt");
        }
      });
      save();
      updateWarnings();
      status("已按 0.1pt 调整 " + targets.length + " 个段落", false);
    }

    function resetTypography() {
      syncFromDom();
      const targets = targetBlocks();
      targets.forEach(function (block) {
        const original = findBlock(block.id, initial);
        if (original) block.style = normalizeStyle(block.kind, original.style);
      });
      render();
      save();
      status("已恢复所选范围的封板字号与行距", false);
    }

    function fileStem() {
      const nameBlock = state.pages[0] && state.pages[0].find(function (block) { return block.kind === "name"; });
      const name = nameBlock ? plainText(nameBlock.html).trim() : "简历";
      const revision = String(state.revision || "微调.1").replace(/[\\/:*?"<>|]/g, "_").slice(0, 60);
      return (name || "简历").replace(/[\\/:*?"<>|]/g, "_").slice(0, 60) + "_" + revision;
    }

    editor.addEventListener("input", function () { changed(); });
    editor.addEventListener("paste", function (event) {
      event.preventDefault();
      const text = event.clipboardData.getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    editor.addEventListener("keydown", function (event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        rememberSelection();
        exec("bold");
      }
    });
    editor.addEventListener("click", function (event) { if (event.target.closest("a")) event.preventDefault(); });
    document.addEventListener("selectionchange", function () { if (selectionInside()) rememberSelection(); });
    $("bold").addEventListener("click", function () { exec("bold"); });
    $("applyColor").addEventListener("click", function () { exec("foreColor", $("textColor").value); });
    $("emphasize").addEventListener("click", function () { exec("foreColor", state.accent); exec("bold"); });
    $("accentColor").addEventListener("change", function () {
      state.accent = normalizeColor($("accentColor").value, "#2F5BEA");
      document.documentElement.style.setProperty("--accent", state.accent);
      save();
    });
    $("applyTypography").addEventListener("click", applyTypography);
    $("resetTypography").addEventListener("click", resetTypography);
    $("revision").addEventListener("input", function () {
      state.revision = $("revision").value.trim() || "微调.1";
      save();
    });
    $("downloadOriginal").addEventListener("click", function () {
      if (!initial.base.docxBase64) { status("未嵌入封板 DOCX，请用对应最终 DOCX 重新生成编辑器", true); return; }
      const binary = atob(initial.base.docxBase64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      download(bytes, "封板原版.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
      status("已下载未修改的封板 Word", false);
    });
    $("exportDocx").addEventListener("click", async function () {
      syncFromDom();
      status("正在生成可编辑 DOCX…", false);
      try {
        const result = await buildDocx(state, window.JSZip, "blob");
        download(result.data, fileStem() + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        save();
        if (result.warnings.length) alert("标准 DOCX 字号按 0.5pt 存储，以下段落已取最近值：\n\n" + result.warnings.join("\n") + "\n\n网页和浏览器 PDF 仍保留 0.1pt。");
        status("DOCX 已按当前修改导出", false);
      } catch (error) { status("DOCX 导出失败：" + error.message, true); }
    });
    $("exportPdf").addEventListener("click", function () {
      syncFromDom();
      save();
      const oldTitle = document.title;
      document.title = fileStem();
      window.print();
      document.title = oldTitle;
    });
    window.addEventListener("beforeprint", syncFromDom);
    $("backup").addEventListener("click", function () {
      syncFromDom();
      download(JSON.stringify(state, null, 2), fileStem() + "_编辑数据.json", "application/json");
      status("编辑数据已备份", false);
    });
    $("restore").addEventListener("change", async function (event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      try {
        const candidate = normalizeState(JSON.parse(await file.text()));
        if (!candidate.pages.length) throw new Error("备份没有有效页面");
        if (!sameBase(candidate, initial)) throw new Error("备份属于另一份封板 PDF，已停止导入");
        if (!sameStructure(candidate, initial)) throw new Error("备份段落结构与当前封板模板不同，已停止导入");
        state = candidate;
        render();
        save();
        status("已恢复编辑备份", false);
      } catch (error) { alert(error.message); }
      event.target.value = "";
    });
    $("resetAll").addEventListener("click", function () {
      if (!confirm("放弃当前微调并恢复到封板原版？已导出的文件不受影响。")) return;
      state = normalizeState(initialData);
      try { localStorage.removeItem(storageKey); } catch (error) { console.warn(error); }
      render();
      save();
      status("已恢复到封板原版", false);
    });

    render();
    status("可直接编辑 · 修改后自动保存在本机", false);
    const instance = { getState: function () { return syncFromDom(); }, reset: function () { state = normalizeState(initialData); render(); }, save: save, sync: syncFromDom, render: render, updateWarnings: updateWarnings };
    window.ResumeEditor.instance = instance;
    return instance;
  }

  return {
    measure: measure,
    docxHalfPoints: docxHalfPoints,
    docxTwips: docxTwips,
    docxPrecisionWarnings: docxPrecisionWarnings,
    xmlEscape: xmlEscape,
    singleXmlDeclaration: singleXmlDeclaration,
    sanitizeHtml: sanitizeHtml,
    htmlToRuns: htmlToRuns,
    plainText: plainText,
    numericTokens: numericTokens,
    numericChanged: numericChanged,
    sameBase: sameBase,
    sameStructure: sameStructure,
    normalizeState: normalizeState,
    buildDocx: buildDocx,
    initEditor: initEditor
  };
});
