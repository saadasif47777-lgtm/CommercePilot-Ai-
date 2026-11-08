"""Copy explicitly assigned legacy projects into a verified client's workspace.

Run behind the deployment access gate with writes paused and a database backup.
Defaults to dry-run; original projects are never removed. No credentials,
assistant conversations or merchant knowledge are implicitly reassigned.
"""
import argparse
import re

from commercepilot import config
from commercepilot.auth import workspace
from commercepilot.database import Database
from commercepilot.storage import ProjectStore


def migrate(target, owner, project_ids, apply=False):
    if not re.fullmatch('[a-f0-9]{64}', owner):
        raise ValueError('Use the workspace_id from the intended signed-in account session.')
    if not project_ids or len(set(project_ids)) != len(project_ids):
        raise ValueError('Choose explicit, distinct legacy project IDs.')
    identity = workspace.set(owner)
    try:
        ProjectStore(target)  # initialize the isolated destination schema
    finally:
        workspace.reset(identity)
    db = Database(target, namespace='')
    table = 'w_' + owner[:24] + '_projects'
    with db:
        db.lock_project('legacy-migration:' + owner)
        rows = []
        for project_id in project_ids:
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                raise ValueError('A selected legacy project does not exist.')
            if db.execute(f'SELECT id FROM {table} WHERE id=?', (project_id,)).fetchone():
                raise ValueError('A destination project already exists; nothing was overwritten.')
            rows.append(row)
        if apply:
            for row in rows:
                db.execute(f'INSERT INTO {table}(id,name,data,created_at,updated_at) VALUES (?,?,?,?,?)',
                           tuple(row[key] for key in ('id', 'name', 'data', 'created_at', 'updated_at')))
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-id', required=True)
    parser.add_argument('--project-id', action='append', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    count = migrate(config.DATABASE_URL or config.DB_PATH, args.workspace_id, args.project_id, args.apply)
    print(f'{"Copied" if args.apply else "Dry-run validated"} {count} projects. Originals retained; credentials and conversations unchanged.')


if __name__ == '__main__':
    main()
