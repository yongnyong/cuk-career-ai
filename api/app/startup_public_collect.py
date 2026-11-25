"""Bounded public KISED/K-Startup collection with robots audit and separate startup DB."""
import argparse
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from .startup_collect import build_posting, source_record
from .startup_db import DEFAULT_DB, connect, initialize, save_posting, summary
from .startup_nodes import rebuild_nodes

UA = 'CUK-Startup-Demo/0.2 (public student project)'
KSTARTUP = 'https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do'
KISED = 'https://www.kised.or.kr/misAnnouncement/index.es?mid=a10302000000'
HOSTS = {'www.k-startup.go.kr', 'www.kised.or.kr'}


def robots_allowed(text, url, agent=UA):
    """Longest matching rule wins; Allow wins ties, with wildcard and end anchors."""
    groups, agents, rules = [], [], []
    for raw in text.lstrip('\ufeff').splitlines():
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        key, value = (p.strip() for p in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            if rules:
                groups.append((agents, rules)); agents, rules = [], []
            agents.append(value.lower())
        elif agents and key in ('allow', 'disallow', 'crawl-delay', 'request-rate'):
            rules.append((key, value))
    if agents:
        groups.append((agents, rules))
    if not groups or re.search(r'<(?:html|!doctype)', text, re.I):
        raise ValueError('Unverified robots response')
    ranked = [(max((len(a) for a in agents if a != '*' and a in agent.lower()), default=0), agents, rules) for agents, rules in groups]
    best = max(r[0] for r in ranked)
    selected = [rules for rank, agents, rules in ranked if (best and rank == best) or (not best and '*' in agents)]
    parts = urllib.parse.urlsplit(url)
    path = parts.path + ('?' + parts.query if parts.query else '')
    matches = []
    for rules in selected:
        for action, value in rules:
            if action in ('crawl-delay', 'request-rate'):
                raise ValueError('Robots timing directives require explicit support')
            if not value:
                continue
            pattern = '^' + re.escape(value).replace(r'\*', '.*')
            if value.endswith('$'):
                pattern = pattern[:-2] + '$'
            if re.search(pattern, path):
                matches.append((len(value.replace('*', '').rstrip('$')), action == 'allow'))
    return max(matches, default=(0, True))[1]


class Fetcher:
    def __init__(self, audit):
        self.audit, self.policies, self.last = audit, {}, 0

    def download(self, url):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        time.sleep(max(0, 3 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as r:
            data = r.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('Response too large')
            return data.decode('utf-8-sig')

    def get(self, url):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != 'https' or parts.hostname not in HOSTS:
            raise ValueError('Unconfigured source host')
        origin = 'https://' + parts.netloc
        if origin not in self.policies:
            text = self.download(origin + '/robots.txt')
            robots_allowed(text, url)
            self.policies[origin] = text
            (self.audit / (parts.hostname + '-robots.txt')).write_text(text, encoding='utf-8')
        if not robots_allowed(self.policies[origin], url):
            raise ValueError('Robots disallows URL: ' + url)
        return self.download(url)


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        if self.tag == 'br':
            return '\n'
        if self.tag in ('script', 'style'):
            return ''
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()


class DOM(HTMLParser):
    def __init__(self, page):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in ('br', 'img', 'input', 'meta', 'link', 'hr', 'source', 'area', 'wbr', 'embed', 'param', 'col', 'base'):
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(re.sub(r'\s+', ' ', data))


def listing(page):
    found = {}
    for a in DOM(page).root.walk():
        if a.tag != 'a':
            continue
        href = a.attrs.get('href', '')
        match = re.search(r'go_view\((\d+)\)', href) or re.search(r'pbancSn=(\d+)', href)
        if match and a.text() and not re.fullmatch(r'자세히\s*보기', a.text()):
            found[match[1]] = next((n.text() for n in a.walk() if n.has_class('tit') or n.has_class('ls_tit')), a.text())
    return found


def parse_detail(page):
    root = DOM(page).root
    title = next((n.text() for n in root.walk() if n.tag == 'h3'), '')
    blocks = []
    for node in root.walk():
        if node.tag != 'p' or not node.has_class('tit') or not node.parent:
            continue
        name = node.text()
        ancestor = node.parent
        inside = False
        while ancestor:
            inside |= ancestor.has_class('information_list')
            ancestor = ancestor.parent
        if not inside and name not in ('지원분야', '대상연령', '기관구분', '지역', '접수기간', '주관기관명', '대상', '창업업력'):
            continue
        if name in ('연락처', '문의처') or len(name) > 40:
            continue
        siblings = node.parent.children
        value = ' '.join(n.text() for n in siblings[siblings.index(node) + 1:] if isinstance(n, Node) and n.tag in ('p', 'div', 'ul'))
        if value:
            blocks.extend(name + ': ' + line.strip() for line in value.splitlines() if line.strip())
    if not title or not any(b.startswith('신청대상:') for b in blocks):
        raise ValueError('Missing title/eligibility block: review layout')
    return title, '\n'.join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--pages', type=int, default=2)
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--audit-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.pages < 1 or args.limit < 1 or args.db.name in ('career.db', 'dev.db'):
        parser.error('Use positive limits and a dedicated startup DB')
    initialize(args.db)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    audit = args.audit_dir / stamp
    audit.mkdir(parents=True)
    fetcher = Fetcher(audit)
    discovered, origins, skipped, failures, saved = {}, {}, [], [], []
    with sqlite3.connect(args.db) as original, sqlite3.connect(audit / 'startup-before.db') as backup:
        original.backup(backup)
    for source, url in [('창업진흥원', KISED)] + [('K-Startup', KSTARTUP + '?page=' + str(i)) for i in range(1, args.pages + 1)]:
        page = fetcher.get(url)
        for pid, title in listing(page).items():
            discovered[pid] = title
            origins.setdefault(pid, []).append({'source': source, 'url': url})
    with connect(args.db) as db:
        before = summary(db)
        for pid, title in discovered.items():
            if len(saved) >= args.limit:
                break
            if re.search(r'주관기관|운영기관|운영사|수행기관|입찰|용역|학생인턴|평가단|위원단|심사위원|Service Provider', title, re.I):
                skipped.append({'id': pid, 'title': title, 'reason': '창업팀 대상 아님'})
                continue
            url = KSTARTUP + '?schM=view&pbancSn=' + pid
            try:
                page = fetcher.get(url)
                title, body = parse_detail(page)
                now = datetime.now(timezone.utc).isoformat()
                sources = [source_record('kstartup-' + pid, url, 'html', body, now)]
                posting, requirements = build_posting(url, title, None, sources, [], now)
                notes = json.loads(posting['review_notes']) + ['공개 HTML 본문만 확보. 첨부·이미지의 추가 요건은 원문 확인 필요']
                posting['review_notes'] = json.dumps(notes, ensure_ascii=False)
                for requirement in requirements:
                    if requirement['evidence_quote'] not in sources[0]['content']:
                        raise ValueError('Ungrounded submission evidence')
                save_posting(db, posting, sources, [], requirements)
                saved.append({'id': posting['id'], 'title': title, 'requirements': len(requirements), 'status': posting['application_status']})
                (audit / (pid + '.html')).write_text(page, encoding='utf-8')
                print(json.dumps(saved[-1], ensure_ascii=False), flush=True)
            except urllib.error.HTTPError as exc:
                failures.append({'id': pid, 'error': str(exc)})
                if exc.code in (401, 403, 429):
                    break
            except (ValueError, OSError) as exc:
                failures.append({'id': pid, 'error': str(exc)})
        rebuild_nodes(db)
        report = {'observed_at': stamp, 'user_agent': UA, 'discovered': len(discovered), 'saved': saved,
                  'origins': origins, 'skipped': skipped, 'failures': failures, 'before': before, 'after': summary(db),
                  'scope': 'Bounded recent listing pages; not complete site coverage. HTML only.'}
    (audit / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'saved': len(saved), 'failures': failures, 'after': report['after'], 'audit': str(audit)}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
