-- Frozen schema for revision 0001_foundation. Do not regenerate after release.
CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE organizations (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	timezone VARCHAR(100) NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE memberships (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	active BOOLEAN NOT NULL, 
	row_version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	UNIQUE (organization_id, user_id)
);

CREATE INDEX ix_memberships_organization_id ON memberships (organization_id);

CREATE INDEX ix_memberships_user_id ON memberships (user_id);

CREATE TABLE projects (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	timezone VARCHAR(100) NOT NULL, 
	start_date VARCHAR(10) NOT NULL, 
	discipline VARCHAR(60) NOT NULL, 
	archived BOOLEAN NOT NULL, 
	row_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	UNIQUE (organization_id, id), 
	UNIQUE (organization_id, code)
);

CREATE INDEX ix_projects_organization_id ON projects (organization_id);

CREATE TABLE invitations (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id), 
	UNIQUE (token_hash)
);

CREATE INDEX ix_invitations_organization_id ON invitations (organization_id);

CREATE TABLE audit_events (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	actor_id VARCHAR(36) NOT NULL, 
	action VARCHAR(80) NOT NULL, 
	entity_id VARCHAR(36) NOT NULL, 
	details JSON NOT NULL, 
	request_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE INDEX ix_audit_events_created_at ON audit_events (created_at);

CREATE INDEX ix_audit_events_organization_id ON audit_events (organization_id);

CREATE TABLE project_memberships (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	row_version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id, project_id) REFERENCES projects (organization_id, id), 
	UNIQUE (organization_id, project_id, user_id)
);

CREATE INDEX ix_project_memberships_organization_id ON project_memberships (organization_id);

CREATE INDEX ix_project_memberships_project_id ON project_memberships (project_id);

CREATE TABLE calendar_versions (
	id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	calendar_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	timezone VARCHAR(100) NOT NULL, 
	nominal_minutes_per_day INTEGER NOT NULL, 
	week JSON NOT NULL, 
	exceptions JSON NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id, project_id) REFERENCES projects (organization_id, id), 
	UNIQUE (organization_id, project_id, id), 
	UNIQUE (organization_id, project_id, calendar_id, version)
);

CREATE INDEX ix_calendar_versions_organization_id ON calendar_versions (organization_id);

CREATE INDEX ix_calendar_versions_project_id ON calendar_versions (project_id);
