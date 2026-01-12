# Database Migrations

Schema changes are managed with Flask-Migrate. Fresh databases are created by `db.create_all()`. Migrations handle changes to existing schemas.

## Usage

```bash
# Generate migration after changing models
flask db migrate -m "Add column to table"

# Apply pending migrations
flask db upgrade
```

## Adding Schema Changes

1. Modify your model in `app/models/`
2. Run `flask db migrate -m "Description"`
3. Review the generated file in `migrations/versions/`
4. Commit the migration file
