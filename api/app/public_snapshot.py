"""Export/import only public career/startup tables as deterministic JSONL for Git."""
import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .startup_db import SCHEMA

ROOT = Path(__file__).resolve().parents[2]
TABLES = ('postings', 'sources', 'attachments', 'submission_requirements',
          'startup_nodes', 'startup_node_evidence', 'startup_node_edges')
CAREER_SCHEMA = '''CREATE TABLE postings (
 id VARCHAR(40) PRIMARY KEY, raw_hash VARCHAR(64) NOT NULL,
 data JSON, checked_at BIGINT NOT NULL)'''


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def dump(db, tables, path, career=False):
    counts = {}
    db.row_factory = sqlite3.Row
    with Path(path).open('w', encoding='utf-8', newline='\n') as out:
        for table in tables:
            count = 0
            for row in db.execute(f'SELECT * FROM {table} ORDER BY 1,2'):
                value = dict(row)
                if career and value['data'] is not None:
                    value['data'] = json.loads(value['data'])
                    if value['data'].get('isVirtual') or value['id'].startswith('man-'):
                        continue
                out.write(json.dumps({'table': table, 'row': value}, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
                count += 1
            counts[table] = count
    return counts


def export(career, startup, destination):
    if Path(career).resolve() == Path(startup).resolve():
        raise ValueError('Career and startup must be separate databases')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'format': 1, 'scope': 'Public posting/source tables only. No accounts, conversations, secrets, or embedding cache.', 'files': {}}
    for name, path, tables, is_career in [('career.jsonl', career, ('postings',), True),
                                          ('startup.jsonl', startup, TABLES, False)]:
        with closing(readonly(path)) as db:
            counts = dump(db, tables, destination / name, is_career)
        manifest['files'][name] = {'sha256': sha(destination / name), 'bytes': (destination / name).stat().st_size, 'tables': counts}
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return manifest


def restore(source, career, startup):
    source, career, startup = Path(source), Path(career), Path(startup)
    if career.resolve() == startup.resolve() or career.name == 'dev.db' or startup.name == 'dev.db':
        raise ValueError('Use separate public DB targets, never dev.db')
    if career.exists() or startup.exists():
        raise ValueError('Destination already exists. Use new paths; existing DBs are never overwritten.')
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or set(manifest['files']) != {'career.jsonl', 'startup.jsonl'}:
        raise ValueError('Unsupported snapshot format')
    for name, metadata in manifest['files'].items():
        if sha(source / name) != metadata['sha256']:
            raise ValueError('Snapshot checksum mismatch: ' + name)
    # Validate both datasets in temporary files before publishing either target.
    temporaries = [p.with_name(p.name + '.importing') for p in (career, startup)]
    if any(p.exists() for p in temporaries):
        raise ValueError('An importing file already exists; inspect it first')
    try:
        for name, target, schema, allowed in [('career.jsonl', temporaries[0], CAREER_SCHEMA, ('postings',)),
                                               ('startup.jsonl', temporaries[1], SCHEMA, TABLES)]:
            target.parent.mkdir(parents=True, exist_ok=True)
            counts = {t: 0 for t in allowed}
            with closing(sqlite3.connect(target)) as db:
                db.execute('PRAGMA foreign_keys=ON')
                db.executescript(schema)
                columns = {t: [r[1] for r in db.execute(f'PRAGMA table_info({t})')] for t in allowed}
                with db, (source / name).open(encoding='utf-8') as incoming:
                    for line in incoming:
                        entry = json.loads(line)
                        table, row = entry['table'], entry['row']
                        if table not in allowed or set(row) != set(columns[table]):
                            raise ValueError('Unexpected table/columns')
                        if name == 'career.jsonl' and row['data'] is not None:
                            row['data'] = json.dumps(row['data'], ensure_ascii=False)
                        keys = columns[table]
                        db.execute(f'INSERT INTO {table}({",".join(keys)}) VALUES({",".join("?" for _ in keys)})', [row[k] for k in keys])
                        counts[table] += 1
                if counts != manifest['files'][name]['tables'] or db.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('Snapshot count or reference mismatch')
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Database integrity check failed')
        # link fails if a target appeared during import, unlike replace/rename.
        created = []
        try:
            for temp, target in zip(temporaries, (career, startup)):
                target.hardlink_to(temp)
                created.append(target)
        except OSError:
            for target in created:
                target.unlink()
            raise
    finally:
        for temp in temporaries:
            temp.unlink(missing_ok=True)
    return {'career': str(career), 'startup': str(startup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    output = commands.add_parser('export')
    output.add_argument('--career', type=Path, default=ROOT / 'api/career.db')
    output.add_argument('--startup', type=Path, default=ROOT / 'api/startup.db')
    output.add_argument('--out', type=Path, default=ROOT / 'data/public')
    incoming = commands.add_parser('restore')
    incoming.add_argument('--source', type=Path, default=ROOT / 'data/public')
    incoming.add_argument('--career', type=Path, default=ROOT / 'api/career.shared.db')
    incoming.add_argument('--startup', type=Path, default=ROOT / 'api/startup.shared.db')
    args = parser.parse_args()
    try:
        result = export(args.career, args.startup, args.out) if args.command == 'export' else restore(args.source, args.career, args.startup)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
