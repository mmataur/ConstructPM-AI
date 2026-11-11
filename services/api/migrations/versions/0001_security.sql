-- Provision constructpm_app (LOGIN, no bypass) and constructpm_policy
-- (NOLOGIN, BYPASSRLS) before migrating, using a privileged setup identity.
CREATE SCHEMA app_private;
REVOKE ALL ON SCHEMA app_private FROM PUBLIC;
GRANT USAGE ON SCHEMA public, app_private TO constructpm_app, constructpm_policy;
GRANT SELECT ON organizations, memberships, project_memberships, invitations TO constructpm_policy;

CREATE FUNCTION app_private.actor() RETURNS text LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.actor', true), '') $$;
CREATE FUNCTION app_private.tenant() RETURNS text LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.tenant', true), '') $$;

CREATE FUNCTION app_private.member(org text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM public.memberships m WHERE m.organization_id=org
    AND m.user_id=app_private.actor() AND m.active)
$$;
CREATE FUNCTION app_private.admin(org text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM public.memberships m WHERE m.organization_id=org
    AND m.user_id=app_private.actor() AND m.active AND m.role='administrator')
$$;
CREATE FUNCTION app_private.project_access(org text, project text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT app_private.member(org) AND (app_private.admin(org) OR EXISTS
    (SELECT 1 FROM public.project_memberships p WHERE p.organization_id=org
      AND p.project_id=project AND p.user_id=app_private.actor()))
$$;
CREATE FUNCTION app_private.bootstrap(org text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM public.organizations o WHERE o.id=org AND o.created_by=app_private.actor())
    AND NOT EXISTS (SELECT 1 FROM public.memberships m WHERE m.organization_id=org)
$$;
CREATE FUNCTION app_private.invited(org text, requested_role text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM public.invitations i WHERE i.organization_id=org
    AND i.token_hash=current_setting('app.invite',true)
    AND i.email=current_setting('app.email',true) AND i.role=requested_role
    AND i.accepted_at IS NULL AND i.expires_at>now())
$$;
ALTER FUNCTION app_private.member(text) OWNER TO constructpm_policy;
ALTER FUNCTION app_private.admin(text) OWNER TO constructpm_policy;
ALTER FUNCTION app_private.project_access(text,text) OWNER TO constructpm_policy;
ALTER FUNCTION app_private.bootstrap(text) OWNER TO constructpm_policy;
ALTER FUNCTION app_private.invited(text,text) OWNER TO constructpm_policy;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app_private FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app_private TO constructpm_app, constructpm_policy;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY user_self ON users USING (id=app_private.actor()) WITH CHECK(id=app_private.actor());

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organization_read ON organizations FOR SELECT USING
  (app_private.member(id) OR app_private.bootstrap(id));
CREATE POLICY organization_create ON organizations FOR INSERT WITH CHECK
  (id=app_private.tenant() AND created_by=app_private.actor());

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_read ON memberships FOR SELECT USING
  ((user_id=app_private.actor() AND active) OR (organization_id=app_private.tenant() AND app_private.admin(organization_id)));
CREATE POLICY membership_create ON memberships FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND
    (app_private.admin(organization_id) OR
      (user_id=app_private.actor() AND email=current_setting('app.email',true) AND active AND
        ((app_private.bootstrap(organization_id) AND role='administrator') OR app_private.invited(organization_id,role)))));
CREATE POLICY membership_update ON memberships FOR UPDATE USING
  (organization_id=app_private.tenant() AND app_private.admin(organization_id)) WITH CHECK
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
CREATE POLICY project_read ON projects FOR SELECT USING
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,id));
CREATE POLICY project_create ON projects FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));
CREATE POLICY project_update ON projects FOR UPDATE USING
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,id)) WITH CHECK
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,id));

ALTER TABLE project_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY project_member_read ON project_memberships FOR SELECT USING
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,project_id));
CREATE POLICY project_member_create ON project_memberships FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));
CREATE POLICY project_member_update ON project_memberships FOR UPDATE USING
  (organization_id=app_private.tenant() AND app_private.admin(organization_id)) WITH CHECK
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));

ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations FORCE ROW LEVEL SECURITY;
CREATE POLICY invitation_read ON invitations FOR SELECT USING
  ((organization_id=app_private.tenant() AND app_private.admin(organization_id)) OR
    (token_hash=current_setting('app.invite',true) AND email=current_setting('app.email',true)));
CREATE POLICY invitation_create ON invitations FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));
CREATE POLICY invitation_update ON invitations FOR UPDATE USING
  ((organization_id=app_private.tenant() AND app_private.admin(organization_id)) OR
    (token_hash=current_setting('app.invite',true) AND email=current_setting('app.email',true) AND accepted_at IS NULL AND expires_at>now()))
  WITH CHECK(organization_id=app_private.tenant());

ALTER TABLE calendar_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY calendar_read ON calendar_versions FOR SELECT USING
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,project_id));
CREATE POLICY calendar_create ON calendar_versions FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND app_private.project_access(organization_id,project_id) AND created_by=app_private.actor());

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON audit_events FOR SELECT USING
  (organization_id=app_private.tenant() AND app_private.admin(organization_id));
CREATE POLICY audit_create ON audit_events FOR INSERT WITH CHECK
  (organization_id=app_private.tenant() AND actor_id=app_private.actor() AND app_private.member(organization_id));

CREATE FUNCTION app_private.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable evidence cannot be changed or deleted'; END;
$$;
REVOKE ALL ON FUNCTION app_private.reject_mutation() FROM PUBLIC;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION app_private.reject_mutation();
CREATE TRIGGER calendar_immutable BEFORE UPDATE OR DELETE ON calendar_versions FOR EACH ROW EXECUTE FUNCTION app_private.reject_mutation();

ALTER TABLE memberships ADD CONSTRAINT org_role_valid CHECK (role IN ('administrator','member'));
ALTER TABLE invitations ADD CONSTRAINT invite_role_valid CHECK (role IN ('administrator','member'));
ALTER TABLE project_memberships ADD CONSTRAINT project_role_valid CHECK
  (role IN ('project_manager','planner','site_engineer','supervisor','quantity_surveyor','executive','subcontractor','guest'));
ALTER TABLE calendar_versions ADD CONSTRAINT calendar_version_positive CHECK(version>0 AND nominal_minutes_per_day BETWEEN 1 AND 1440);
ALTER TABLE audit_events ADD CONSTRAINT audit_project_scope FOREIGN KEY(organization_id,project_id) REFERENCES projects(organization_id,id);
CREATE INDEX audit_tenant_time ON audit_events(organization_id,created_at,id);
CREATE INDEX calendar_project_versions ON calendar_versions(organization_id,project_id,calendar_id,version);

GRANT SELECT, INSERT, UPDATE ON users, memberships, projects, project_memberships, invitations TO constructpm_app;
GRANT SELECT, INSERT ON organizations, calendar_versions, audit_events TO constructpm_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

