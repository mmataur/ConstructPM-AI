"""Retain membership history while allowing per-project access revocation."""
from alembic import op

revision = "0002_project_revocation"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql("""
      ALTER TABLE project_memberships ADD COLUMN active boolean NOT NULL DEFAULT true;
      CREATE OR REPLACE FUNCTION app_private.project_access(org text, project text) RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT app_private.member(org) AND (app_private.admin(org) OR EXISTS
          (SELECT 1 FROM public.project_memberships p WHERE p.organization_id=org
            AND p.project_id=project AND p.user_id=app_private.actor() AND p.active))
      $$;
      ALTER FUNCTION app_private.project_access(text,text) OWNER TO constructpm_policy;
      REVOKE ALL ON FUNCTION app_private.project_access(text,text) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION app_private.project_access(text,text) TO constructpm_app,constructpm_policy;
      GRANT SELECT ON alembic_version TO constructpm_app;
    """)


def downgrade():
    raise RuntimeError("Restoring revoked project access is unsafe; use a reviewed forward migration")
