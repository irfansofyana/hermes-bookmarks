"""Schema nine: portable content without executable import ownership."""


def upgrade_content(connection):
    """Keep source order/fields and old receipts; caller owns migration commit."""
    connection.execute('ALTER TABLE items ADD COLUMN processing_history TEXT')
    connection.execute('''CREATE TABLE content_sources(
        item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
        source_id TEXT NOT NULL, source TEXT NOT NULL, locator TEXT NOT NULL,
        imported_summary TEXT NOT NULL, source_text TEXT NOT NULL)''')
    connection.execute('CREATE INDEX content_sources_item ON content_sources(item_id)')
    connection.execute('''INSERT INTO content_sources(rowid,item_id,source_id,source,locator,imported_summary,source_text)
        SELECT rowid,item_id,source_id,source,locator,imported_summary,source_text
        FROM import_provenance ORDER BY rowid''')
