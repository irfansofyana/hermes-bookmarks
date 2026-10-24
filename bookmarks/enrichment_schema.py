"""Schema eleven: stable settings and explicit enrichment request identity."""

def upgrade_enrichment(c):
    c.execute("ALTER TABLE items ADD COLUMN summary_source TEXT NOT NULL DEFAULT 'none' CHECK(summary_source IN ('none','legacy','generated','manual'))")
    c.execute('ALTER TABLE items ADD COLUMN summary_revision INTEGER NOT NULL DEFAULT 0 CHECK(summary_revision>=0)')
    c.execute("ALTER TABLE items ADD COLUMN extracted_text TEXT NOT NULL DEFAULT ''")
    c.execute('ALTER TABLE items ADD COLUMN generated_provenance TEXT')
    c.execute("UPDATE items SET summary_source='legacy' WHERE summary!=''")
    c.execute('ALTER TABLE jobs RENAME TO jobs_previous')
    c.execute('DROP INDEX jobs_claim')
    c.execute('''CREATE TABLE jobs (
        id TEXT PRIMARY KEY, item_id TEXT NOT NULL, revision INTEGER NOT NULL,
        settings TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
        worker TEXT, token TEXT, expires REAL, attempts INTEGER NOT NULL DEFAULT 0,
        error TEXT, result TEXT, generation INTEGER NOT NULL DEFAULT 1,
        request_id TEXT, fields TEXT, settings_revision INTEGER,
        primary_asset_id TEXT, summary_revision INTEGER,
        UNIQUE(item_id,generation))''')
    c.execute('''INSERT INTO jobs(rowid,id,item_id,revision,settings,state,worker,token,expires,attempts,error,result,generation)
        SELECT rowid,id,item_id,revision,settings,state,worker,token,expires,attempts,error,result,generation
        FROM jobs_previous ORDER BY rowid''')
    c.execute('DROP TABLE jobs_previous')
    c.execute('CREATE INDEX jobs_claim ON jobs(state)')
    c.execute('CREATE TABLE enrichment_requests(request_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,receipt TEXT NOT NULL)')
    from .settings import initialize
    initialize(c)
