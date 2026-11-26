"""로컬 공고 DB(api/career.db)를 운영 서버의 공고 DB에 올린다. 관리자 계정이 필요하다.

    python -m app.push_postings --server https://43-200-13-8.sslip.io --user 내아이디 --dry-run
    python -m app.push_postings --server https://43-200-13-8.sslip.io --user 내아이디

비밀번호는 실행 중에 묻는다(화면에 보이지 않고 저장하지 않는다). 같은 공고를 다시 올려도 바뀐 것만 반영된다.
"""
import argparse
import getpass
import http.cookiejar
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_SOURCE = Path(__file__).resolve().parent.parent / 'career.db'
BATCH = 100


def read_rows(source, prefixes=()):
    with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id, raw_hash, data FROM postings ORDER BY id').fetchall()
    return [{'id': pid, 'raw_hash': digest, 'data': json.loads(data) if data else None}
            for pid, digest, data in rows if not prefixes or pid.startswith(tuple(prefixes))]


def push(rows, post):
    """post(path, body) -> dict. 100건씩 나눠 보내고 결과를 합친다."""
    total = {'added': 0, 'updated': 0, 'unchanged': 0, 'rejected': []}
    for start in range(0, len(rows), BATCH):
        result = post('/api/admin/postings/import', {'rows': rows[start:start + BATCH]})
        for key in ('added', 'updated', 'unchanged'):
            total[key] += result[key]
        total['rejected'] += result['rejected']
    return total


def client(server):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(path, body):
        request = urllib.request.Request(server.rstrip('/') + path, data=json.dumps(body).encode('utf-8'),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with opener.open(request, timeout=120) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', 'replace')[:300]
            raise SystemExit(f'서버가 거절했어요({error.code}): {detail}') from None
    return post


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--server', required=True, help='예: https://43-200-13-8.sslip.io')
    parser.add_argument('--user', required=True, help='관리자 아이디')
    parser.add_argument('--prefix', action='append', default=[], help='이 글자로 시작하는 공고 id만 올린다(여러 번 가능)')
    parser.add_argument('--dry-run', action='store_true', help='올리지 않고 건수만 본다')
    args = parser.parse_args()
    rows = read_rows(args.source, args.prefix)
    live = sum(row['data'] is not None for row in rows)
    print(f'{args.source}: 공고 {len(rows)}건(게시 {live}, 내림 {len(rows) - live})')
    if args.dry_run or not rows:
        return
    post = client(args.server)
    post('/api/auth/login', {'id': args.user, 'password': getpass.getpass('비밀번호: ')})
    result = push(rows, post)
    print(f"새로 추가 {result['added']}, 수정 {result['updated']}, 그대로 {result['unchanged']}, 거절 {len(result['rejected'])}")
    if result['rejected']:
        print('거절된 id:', ', '.join(result['rejected'][:20]))


if __name__ == '__main__':
    main()
