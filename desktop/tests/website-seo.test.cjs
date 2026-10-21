const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../docs');
const base = 'https://lulinlulu888-design.github.io/Atreia-Assistant/';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const htmlFiles = fs.readdirSync(root, { recursive: true })
  .filter(file => file.endsWith('.html')).map(file => file.replaceAll('\\', '/')).sort();
const attributes = tag => Object.fromEntries([...tag.matchAll(/([\w:-]+)="([^"]*)"/g)].map(match => [match[1], match[2]]));
const tags = (html, name) => [...html.matchAll(new RegExp(`<${name}\\b[^>]*>`, 'gi'))].map(match => attributes(match[0]));
const meta = (html, name) => tags(html, 'meta').filter(tag => tag.name === name || tag.property === name);
const title = html => html.match(/<title>([^<]+)<\/title>/)[1];
const canonical = html => tags(html, 'link').filter(tag => tag.rel === 'canonical');
const schema = html => JSON.parse(html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1]);
const pages = htmlFiles.map(file => ({ file, html: read(file), url: new URL(file === 'index.html' ? '' : file, base).href }));

function localPath(url) {
  assert.ok(url.href.startsWith(base), `URL outside project: ${url.href}`);
  let relative = decodeURIComponent(url.pathname.slice(new URL(base).pathname.length));
  if (!relative || relative.endsWith('/')) relative += 'index.html';
  const target = path.resolve(root, relative);
  assert.ok(target.startsWith(root + path.sep));
  return target;
}

for (const { file, html, url } of pages) {
  test(`${file}: crawlable static content, unique title and consistent search/social metadata`, () => {
    assert.match(html, /<html lang="zh-CN">/);
    assert.equal((html.match(/<title>/g) || []).length, 1);
    assert.match(title(html), /AION2/);
    assert.match(title(html), /亚特雷亚助手/);
    for (const name of ['description', 'robots', 'viewport', 'og:title', 'og:description', 'og:type',
      'og:locale', 'og:site_name', 'og:url', 'og:image', 'og:image:width', 'og:image:height', 'og:image:alt',
      'twitter:card', 'twitter:title', 'twitter:description', 'twitter:image', 'twitter:image:alt']) {
      assert.equal(meta(html, name).length, 1, `${name} missing or duplicated`);
      assert.ok(meta(html, name)[0].content.length > 0);
    }
    assert.ok(meta(html, 'description')[0].content.length >= 40);
    assert.equal(meta(html, 'og:title')[0].content, title(html));
    assert.equal(meta(html, 'twitter:title')[0].content, title(html));
    assert.equal(meta(html, 'og:locale')[0].content, 'zh_CN');
    assert.equal(meta(html, 'twitter:card')[0].content, 'summary_large_image');
    assert.equal(meta(html, 'og:image')[0].content, meta(html, 'twitter:image')[0].content);
    assert.equal(canonical(html).length, 1);
    assert.equal(canonical(html)[0].href, url);
    assert.equal(meta(html, 'og:url')[0].content, url);
    assert.match(meta(html, 'robots')[0].content, /max-image-preview:large/);
    assert.doesNotMatch(meta(html, 'robots')[0].content, /noindex|nofollow|none/);
    assert.equal((html.match(/<h1\b/g) || []).length, 1);
    assert.match(html, /<main[^>]*id="main"/);
    assert.doesNotMatch(html, /http-equiv="refresh"/i);
    assert.match(html, /<a[^>]*href="(?:\.\.\/)?#download"|id="download-button"/);
    for (const image of tags(html, 'img')) {
      assert.ok(Object.hasOwn(image, 'alt'), 'Each image needs an alt attribute');
      assert.ok(Number(image.width) > 0 && Number(image.height) > 0, 'Reserve image space to avoid layout shifts');
    }
  });

  test(`${file}: all local links, images, styles, scripts and fragment destinations exist`, () => {
    const refs = [...tags(html, 'a'), ...tags(html, 'link'), ...tags(html, 'img'), ...tags(html, 'script')];
    for (const ref of refs) {
      if (!ref.href && !ref.src) continue;
      const target = new URL(ref.href || ref.src, url);
      if (target.origin !== new URL(base).origin) continue;
      const targetPath = localPath(target);
      assert.ok(fs.existsSync(targetPath), `Broken reference: ${target.href}`);
      if (target.hash) {
        assert.ok(fs.readFileSync(targetPath, 'utf8').includes(`id="${decodeURIComponent(target.hash.slice(1))}"`), `Missing fragment: ${target.href}`);
      }
    }
    for (const name of ['og:image', 'twitter:image']) {
      assert.ok(fs.existsSync(localPath(new URL(meta(html, name)[0].content))));
    }
  });

  test(`${file}: JSON-LD identifies the real page without invented ratings`, () => {
    const data = schema(html);
    assert.equal(data['@context'], 'https://schema.org');
    assert.ok(Array.isArray(data['@graph']));
    const page = data['@graph'].find(item => item['@type'] === 'WebPage');
    assert.equal(page.url, url);
    assert.equal(page.name, title(html));
    assert.equal(page.inLanguage, 'zh-CN');
    assert.equal(page.isPartOf['@id'], `${base}#website`);
    assert.doesNotMatch(JSON.stringify(data), /"aggregateRating"|"review"|"ratingValue"/);
    if (file.startsWith('guides/')) {
      const breadcrumbs = data['@graph'].find(item => item['@type'] === 'BreadcrumbList');
      assert.equal(page.breadcrumb['@id'], breadcrumbs['@id']);
      assert.equal(breadcrumbs.itemListElement.length, 2);
      breadcrumbs.itemListElement.forEach((item, index) => {
        assert.equal(item['@type'], 'ListItem');
        assert.equal(item.position, index + 1);
        assert.ok(html.includes(`>${item.name}<`), 'Breadcrumb must match visible content');
      });
      assert.equal(breadcrumbs.itemListElement[0].item, base);
      assert.equal(breadcrumbs.itemListElement[1].item, url);
      assert.ok(html.includes(`datetime="${page.dateModified}"`));
      // Guides are readable without JavaScript and do not load the homepage API logic.
      assert.equal(tags(html, 'script').filter(tag => tag.src).length, 0);
    }
  });
}

test('all public pages have distinct titles and descriptions and appear in the sitemap exactly once', () => {
  assert.deepEqual(htmlFiles, ['guides/combat.html', 'guides/localization.html', 'index.html']);
  assert.equal(new Set(pages.map(page => title(page.html))).size, pages.length);
  assert.equal(new Set(pages.map(page => meta(page.html, 'description')[0].content)).size, pages.length);
  const sitemap = read('sitemap.xml');
  assert.match(sitemap, /<urlset xmlns="http:\/\/www.sitemaps.org\/schemas\/sitemap\/0.9">/);
  const entries = [...sitemap.matchAll(/<url>\s*<loc>([^<]+)<\/loc>\s*<lastmod>([^<]+)<\/lastmod>\s*<\/url>/g)];
  assert.deepEqual(entries.map(entry => entry[1]).sort(), pages.map(page => page.url).sort());
  for (const [, url, date] of entries) {
    assert.match(date, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(Number.isFinite(Date.parse(date)));
    assert.ok(new Date(date) <= new Date(Date.now() + 86400000), 'No fabricated future modification date');
    const page = pages.find(page => page.url === url);
    const pageData = schema(page.html)['@graph'].find(item => item['@type'] === 'WebPage');
    if (pageData.dateModified) assert.equal(date, pageData.dateModified);
    assert.ok(tags(page.html, 'link').some(tag => tag.rel === 'sitemap' && new URL(tag.href, url).href === `${base}sitemap.xml`));
  }
});

test('homepage exposes real software facts and crawlable links to both player guides', () => {
  const html = read('index.html');
  const app = schema(html)['@graph'].find(item => item['@type'] === 'SoftwareApplication');
  assert.equal(app.name, '亚特雷亚助手');
  assert.equal(app.operatingSystem, 'Windows x64');
  assert.equal(app.applicationCategory, 'UtilitiesApplication');
  assert.equal(app.isAccessibleForFree, true);
  assert.equal(app.offers.price, 0);
  assert.match(html, /免费开源/);
  const release = JSON.parse(read('updates/latest.json'));
  assert.equal(app.softwareVersion, release.tag_name.replace(/^v/, ''));
  assert.equal(app.downloadUrl, release.assets.find(asset => asset.name.endsWith('_x64.msi')).browser_download_url);
  assert.equal(app.offers.url, `${base}#download`);
  assert.ok(fs.existsSync(localPath(new URL(app.screenshot))));
  assert.ok(fs.existsSync(localPath(new URL(app.image))));
  assert.match(html, /href="guides\/localization.html"/);
  assert.match(html, /href="guides\/combat.html"/);
  assert.match(html, /Steam \/ Global 与 PURPLE/);
  assert.match(html, /<h3>AION2 DPS 战斗统计<\/h3>/);
});

test('JSON-LD graph references resolve across the published pages', () => {
  const nodes = pages.flatMap(page => schema(page.html)['@graph']);
  const ids = new Set(nodes.map(node => node['@id']));
  assert.equal(ids.size, nodes.length);
  function check(value) {
    if (!value || typeof value !== 'object') return;
    if (value['@id']) assert.ok(ids.has(value['@id']), `Unresolved entity ${value['@id']}`);
    Object.values(value).forEach(check);
  }
  nodes.forEach(check);
});

test('project robots file does not claim to replace host-root rules', () => {
  const robots = read('robots.txt');
  assert.match(robots, /only use \/robots\.txt at the host root/);
  assert.match(robots, /User-agent: \*/);
  assert.doesNotMatch(robots, /^Disallow:\s*\//m);
  assert.ok(robots.includes(`Sitemap: ${base}sitemap.xml`));
});

test('homepage targets relevant searches without claiming unreleased downloads', () => {
  const html=read('index.html');
  const app=schema(html)['@graph'].find(item=>item['@type']==='SoftwareApplication');
  assert.deepEqual(app.keywords,['AION2 汉化','永恒之塔2 汉化','AION2 DPS 统计','Steam 汉化','PURPLE 汉化','亚特雷亚助手']);
  assert.match(html,/开发版真实截图/);assert.match(html,/尚未包含在当前正式安装包中/);
  assert.match(html,/assets\/home.css/);assert.doesNotMatch(html,/12,871|159\.6|演示数据/);
  assert.match(html,/assets\/screenshots\/launcher-dev.jpg/);
  assert.match(html,/assets\/screenshots\/localization-dev.jpg/);
  assert.equal(meta(html,'keywords').length,0);
});
