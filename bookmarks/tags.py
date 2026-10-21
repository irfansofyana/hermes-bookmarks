"""Transactional tag provenance. Suppressions win; manual labels have priority."""
import json
from uuid import uuid4
from .errors import ValidationError
from .labels import normalize_label


def normalize_tags(labels):
    if not isinstance(labels, (list, tuple)) or len(labels) > 20:
        raise ValidationError()
    values = [normalize_label(label, 80) for label in labels]
    return list({key: (display,key) for display,key in values}.values())


def tag_id(connection, display, identity):
    connection.execute('INSERT INTO tags(id,label,identity) VALUES(?,?,?) ON CONFLICT(identity) DO NOTHING',
                       (uuid4().hex, display, identity))
    return connection.execute('SELECT id FROM tags WHERE identity=?', (identity,)).fetchone()[0]


def effective_tags(connection, item_id):
    rows = connection.execute('''SELECT coalesce(it.label,t.label) AS name,
        CASE WHEN it.manual=1 THEN 'manual' ELSE 'generated' END AS source
        FROM item_tags it JOIN tags t ON t.id=it.tag_id
        WHERE it.item_id=? AND (it.manual=1 OR it.generated=1) AND it.suppressed=0
        ORDER BY it.manual DESC,it.rowid LIMIT 20''', (item_id,)).fetchall()
    return [dict(row) for row in rows]


def refresh_cache(connection, item_id):
    details = effective_tags(connection, item_id)
    connection.execute('UPDATE items SET tags=? WHERE id=?',
                       (json.dumps([tag['name'] for tag in details], ensure_ascii=False), item_id))


def merge_generated(connection, item_id, labels):
    values = normalize_tags(labels)
    connection.execute('UPDATE item_tags SET generated=0 WHERE item_id=?', (item_id,))
    manual = connection.execute('SELECT count(*) FROM item_tags WHERE item_id=? AND manual=1 AND suppressed=0', (item_id,)).fetchone()[0]
    remaining = max(0, 20-manual)
    for display, identity in values:
        key = tag_id(connection, display, identity)
        row = connection.execute('SELECT manual,suppressed FROM item_tags WHERE item_id=? AND tag_id=?', (item_id,key)).fetchone()
        if row is not None and row['suppressed']:
            continue
        if row is None or not row['manual']:
            if remaining == 0:
                continue
            remaining -= 1
        connection.execute('''INSERT INTO item_tags(item_id,tag_id,generated,label) VALUES(?,?,1,?)
            ON CONFLICT(item_id,tag_id) DO UPDATE SET generated=1,
            label=CASE WHEN item_tags.manual=1 THEN item_tags.label ELSE excluded.label END''', (item_id,key,display))
    refresh_cache(connection, item_id)


def apply_manual(connection, item_id, additions, removals):
    for display, identity in removals:
        key = tag_id(connection, display, identity)
        connection.execute('''INSERT INTO item_tags(item_id,tag_id,suppressed) VALUES(?,?,1)
            ON CONFLICT(item_id,tag_id) DO UPDATE SET manual=0,suppressed=1''', (item_id,key))
    for display, identity in additions:
        key = tag_id(connection, display, identity)
        connection.execute('''INSERT INTO item_tags(item_id,tag_id,manual,label) VALUES(?,?,1,?)
            ON CONFLICT(item_id,tag_id) DO UPDATE SET manual=1,suppressed=0,label=excluded.label''', (item_id,key,display))
    count = connection.execute('SELECT count(*) FROM item_tags WHERE item_id=? AND manual=1 AND suppressed=0', (item_id,)).fetchone()[0]
    if count > 20:
        raise ValidationError()
    # Drop only overflow generated membership so counts/search match projection.
    overflow = connection.execute('''SELECT tag_id FROM item_tags WHERE item_id=?
        AND manual=0 AND generated=1 AND suppressed=0 ORDER BY rowid LIMIT -1 OFFSET ?''', (item_id,20-count)).fetchall()
    for row in overflow:
        connection.execute('UPDATE item_tags SET generated=0 WHERE item_id=? AND tag_id=?', (item_id,row['tag_id']))
    refresh_cache(connection, item_id)
