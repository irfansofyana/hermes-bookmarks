"""Plugin bindings only. Hermes owns transcripts, sessions and execution."""
import json
import re

from .storage import Storage


_IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,160}\Z')
_MODEL_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+~-]{0,299}\Z')


def model_identity(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'provider', 'model'}:
        raise ValueError('Invalid model identity')
    if any(not isinstance(v, str) or not _MODEL_ID.fullmatch(v) for v in value.values()):
        raise ValueError('Invalid model identity')
    return value


def thread_from_row(row):
    result = dict(row)
    result['model'] = json.loads(result['model'])
    return result


class ChatStore:
    def __init__(self, root):
        self.storage = Storage(root)

    def identity(self, profile):
        with self.storage._transaction() as connection:
            value = connection.execute("SELECT value FROM library_config WHERE key='library_id'").fetchone()[0]
        return {'library_id': value, 'profile': profile}

    def threads(self, profile, params):
        if not isinstance(params, dict) or params.keys() - {'limit', 'offset'}:
            raise ValueError('Invalid pagination')
        def integer(key, default):
            value = params.get(key, default)
            if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 18:
                value = int(value)
            if type(value) is not int or value < 0:
                raise ValueError('Invalid pagination')
            return value
        limit, offset = integer('limit', 50), integer('offset', 0)
        if not 1 <= limit <= 100:
            raise ValueError('Invalid pagination')
        with self.storage._transaction() as connection:
            total = connection.execute('SELECT count(*) FROM chat_threads WHERE profile=?', (profile,)).fetchone()[0]
            rows = connection.execute('SELECT * FROM chat_threads WHERE profile=? ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?', (profile, limit, offset)).fetchall() if offset < total else []
        return {'threads': [thread_from_row(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

    def bind(self, profile, params):
        if not isinstance(params, dict) or params.keys() - {'id', 'session_id', 'title', 'model'}:
            raise ValueError('Invalid conversation binding')
        for key in ('id', 'session_id'):
            value = params.get(key)
            if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
                raise ValueError('Invalid conversation identifier')
        title = params.get('title', 'Bookmarks')
        if not isinstance(title, str) or not title.strip() or len(title) > 160 or any(ord(c) < 32 for c in title):
            raise ValueError('Invalid title')
        model = json.dumps(model_identity(params.get('model')), sort_keys=True, separators=(',', ':'))
        with self.storage._transaction(write=True) as connection:
            connection.execute('INSERT INTO chat_threads(id,profile,session_id,title,model) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING', (params['id'], profile, params['session_id'], title, model))
            row = connection.execute('SELECT * FROM chat_threads WHERE id=? AND profile=?', (params['id'], profile)).fetchone()
            if row is None or row['session_id'] != params['session_id'] or row['model'] != model:
                raise ValueError('A conversation binding cannot be retargeted')
            return thread_from_row(row)
