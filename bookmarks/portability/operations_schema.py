"""Operational receipts contain no library content or provider credentials."""
def upgrade_operations(c):
 c.execute('''CREATE TABLE portability_ops(
  id TEXT PRIMARY KEY,kind TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,args TEXT NOT NULL,
  state TEXT NOT NULL,pid INTEGER NOT NULL,size INTEGER NOT NULL DEFAULT 0,offset INTEGER NOT NULL DEFAULT 0,
  digest TEXT NOT NULL,expires_at REAL NOT NULL,metadata TEXT NOT NULL DEFAULT '{}')''')
 c.execute('''CREATE TABLE portability_previews(id TEXT PRIMARY KEY,upload_id TEXT NOT NULL UNIQUE,
  digest TEXT NOT NULL,expires_at REAL NOT NULL,report TEXT NOT NULL)''')
 c.execute('''CREATE TABLE portability_restores(id TEXT PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,
  preview_id TEXT NOT NULL,digest TEXT NOT NULL,state TEXT NOT NULL,result TEXT NOT NULL DEFAULT '{}')''')
 c.execute('''CREATE TABLE portability_asset_claims(asset_id TEXT PRIMARY KEY,restore_id TEXT NOT NULL,
  digest TEXT NOT NULL)''')
