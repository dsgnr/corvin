# Database Migrations

Schema changes are managed with Alembic. Fresh databases are initialised by `Base.metadata.create_all()`. Migrations handle changes to existing schemas.

## Usage

```bash
# Generate migration after changing models
alembic revision --autogenerate -m "Add column to table"

# Apply pending migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# View current revision
alembic current

# View migration history
alembic history
```

## Adding Schema Changes

1. Modify your model in `app/models/`
2. Run `alembic revision --autogenerate -m "Description"`
3. Review the generated file in `migrations/versions/`
4. Apply with `alembic upgrade head`
5. Commit the migration file

## Example: Adding a New Column

```python
# 1. Update your model (e.g., app/models/video.py)
class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    # Add new column
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

```bash
# 2. Generate the migration
alembic revision --autogenerate -m "Add view_count to videos"

# 3. Review migrations/versions/<timestamp>_add_view_count_to_videos.py
# The file will contain something like:
#   def upgrade():
#       op.add_column('videos', sa.Column('view_count', sa.Integer(), nullable=True))
#
#   def downgrade():
#       op.drop_column('videos', 'view_count')

# 4. Apply the migration
alembic upgrade head
```

## Running in Docker

```bash
# Generate migration
docker compose exec backend alembic revision --autogenerate -m "Description"

# Apply migrations
docker compose exec backend alembic upgrade head
```

## Configuration

The database URL is configured in `alembic.ini` and can be overridden via the `DATABASE_URL` environment variable in `migrations/env.py`.
