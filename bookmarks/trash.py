"""Revision-checked recoverable deletion. No asset files are removed."""
import time
from .collections import revision
from .items import load, project


def transition(storage, item_id, expected_revision, *, deleted):
    revision(expected_revision)
    with storage._transaction(write=True) as connection:
        row=load(connection,item_id,expected_revision)
        if (row['deleted_at'] is not None)==deleted:
            return project(connection,item_id)
        now=time.time()
        connection.execute("""UPDATE jobs SET state='cancelled',token=NULL,worker=NULL,expires=NULL
            WHERE item_id=? AND state IN ('pending','running')""",(item_id,))
        connection.execute('''UPDATE items SET deleted_at=?,revision=revision+1,updated_at=?,
            enrichment_generation=enrichment_generation+1,
            enrichment_status=CASE WHEN enrichment_status IN ('pending','running') THEN 'cancelled' ELSE enrichment_status END
            WHERE id=?''',(now if deleted else None,now,item_id))
        return project(connection,item_id)
