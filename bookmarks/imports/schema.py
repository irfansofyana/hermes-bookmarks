"""Import tables are created in the caller's migration transaction."""

def upgrade_imports(c):
    c.execute('''CREATE TABLE import_previews(id TEXT PRIMARY KEY,digest TEXT NOT NULL,payload TEXT NOT NULL,
        options TEXT NOT NULL,report TEXT NOT NULL,created_at REAL NOT NULL,expires_at REAL NOT NULL)''')
    c.execute('''CREATE TABLE import_jobs(id TEXT PRIMARY KEY,preview_id TEXT NOT NULL REFERENCES import_previews(id),
        request_id TEXT NOT NULL UNIQUE,digest TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',
        cursor INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL,imported INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0,failed INTEGER NOT NULL DEFAULT 0,worker TEXT,token TEXT,expires REAL,
        cancel_requested INTEGER NOT NULL DEFAULT 0,error TEXT,settings TEXT,created_at REAL NOT NULL,
        CHECK(cursor=imported+skipped+failed),CHECK(cursor<=total))''')
    c.execute('CREATE INDEX import_jobs_claim ON import_jobs(state,created_at)')
    c.execute('''CREATE TABLE import_results(job_id TEXT NOT NULL REFERENCES import_jobs(id),row_index INTEGER NOT NULL,
        outcome TEXT NOT NULL,item_id TEXT,error TEXT,warnings TEXT NOT NULL,PRIMARY KEY(job_id,row_index))''')
    c.execute('''CREATE TABLE import_provenance(item_id TEXT NOT NULL REFERENCES items(id),job_id TEXT NOT NULL REFERENCES import_jobs(id),
        row_index INTEGER NOT NULL,source_id TEXT NOT NULL,source TEXT NOT NULL,locator TEXT NOT NULL,
        imported_summary TEXT NOT NULL,source_text TEXT NOT NULL,UNIQUE(job_id,row_index))''')
