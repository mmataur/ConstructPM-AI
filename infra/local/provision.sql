-- Run once as PostgreSQL administrator, before Alembic migrations.
-- Set login passwords outside this file; use SCRAM in non-ephemeral environments.
CREATE ROLE constructpm_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE constructpm_policy NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
CREATE DATABASE constructpm;

