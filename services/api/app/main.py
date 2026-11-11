import hashlib
import base64
import binascii
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text, tuple_
from sqlalchemy.exc import IntegrityError

from .auth import TokenVerifier
from .config import Settings
from .db import session_factory, set_context
from .models import AuditEvent, CalendarVersion, Invitation, Membership, Organization, Project, ProjectMembership, User
from .schemas import CalendarIn, InvitationIn, MemberPatch, OrganizationIn, ProjectIn, ProjectMemberIn, ProjectPatch


def record(row, fields):
    return {key: getattr(row, key) for key in fields.split()}


def create_app(settings=None):
    s = settings or Settings()
    s.validate()
    factory = session_factory(s.database_url)
    verifier = TokenVerifier(s)
    @asynccontextmanager
    async def lifespan(app):
        with factory.begin() as db:
            privileged = db.execute(text("SELECT rolsuper OR rolbypassrls OR pg_has_role(current_user,'constructpm_policy','MEMBER') FROM pg_roles WHERE rolname=current_user")).scalar()
            owns_tables = db.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"))
            secured = db.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('users','organizations','memberships','projects','project_memberships','invitations','calendar_versions','audit_events') AND c.relrowsecurity AND c.relforcerowsecurity"))
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            if privileged or owns_tables or secured != 8 or revision != "0002_project_revocation":
                raise RuntimeError("Unsafe database identity/schema: use the restricted app role and apply foundation migrations")
        yield
        factory.kw["bind"].dispose()

    api = FastAPI(title="ConstructPM AI — Foundation", version="0.1.0", lifespan=lifespan, docs_url="/docs" if s.environment == "development" else None)
    api.state.factory = factory
    api.add_middleware(CORSMiddleware, allow_origins=list(s.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type", "If-Match"], expose_headers=["ETag", "X-Request-ID"])
    bearer = HTTPBearer(auto_error=False)

    @api.middleware("http")
    async def request_metadata(request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @api.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"code": f"HTTP_{exc.status_code}", "message": exc.detail, "request_id": request.state.request_id}, headers=exc.headers)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo input values or tokens into error payloads.
        return JSONResponse(status_code=422, content={"code": "VALIDATION", "message": "Check the supplied fields", "fields": [{"path": list(e["loc"]), "message": e["msg"]} for e in exc.errors()], "request_id": request.state.request_id})

    @api.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=409, content={"code": "CONFLICT", "message": "A conflicting record exists or a reference is invalid", "request_id": request.state.request_id})

    def identity(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        if not credentials:
            raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
        return verifier.verify(credentials.credentials)

    def database(who=Depends(identity)):
        with factory() as db:
            with db.begin():
                set_context(db, who.id, email=who.email)
                user = db.get(User, who.id)
                if not user:
                    db.add(User(id=who.id, email=who.email, name=who.name))
                    db.flush()
                yield db

    def scope(o: UUID, db=Depends(database), who=Depends(identity)):
        oid = str(o)
        set_context(db, who.id, oid, who.email)
        member = db.scalar(select(Membership).where(Membership.organization_id == oid, Membership.user_id == who.id, Membership.active.is_(True)))
        if not member:
            raise HTTPException(404, "Organization not found")
        return db, who, member, oid

    def admin(ctx):
        if ctx[2].role != "administrator":
            raise HTTPException(403, "Organization administrator permission required")

    def project_scope(ctx, p, write=False, calendar=False):
        db, who, member, oid = ctx
        pid = str(p)
        project = db.scalar(select(Project).where(Project.id == pid, Project.organization_id == oid))
        if not project:
            raise HTTPException(404, "Project not found")
        if member.role == "administrator":
            role = "administrator"
        else:
            pm = db.scalar(select(ProjectMembership).where(ProjectMembership.organization_id == oid, ProjectMembership.project_id == pid, ProjectMembership.user_id == who.id, ProjectMembership.active.is_(True)))
            if not pm:
                raise HTTPException(404, "Project not found")
            role = pm.role
        allowed = {"administrator", "project_manager", "planner"} if calendar else {"administrator", "project_manager"}
        if write and role not in allowed:
            raise HTTPException(403, "Your project role cannot make this change")
        return project, role

    def audit(ctx, request, action, entity, details=None, project=None):
        db, who, _, oid = ctx
        db.add(AuditEvent(organization_id=oid, project_id=project, actor_id=who.id, action=action, entity_id=entity,
                          details=details or {}, request_id=request.state.request_id))

    def match(version, value):
        if value is None:
            raise HTTPException(428, "If-Match is required")
        if value != f'"{version}"':
            raise HTTPException(412, "Record changed; refresh before editing")

    def project_out(row):
        return record(row, "id organization_id code name timezone start_date discipline archived row_version created_at")

    @api.get("/health")
    def health():
        return {"status": "ok", "phase": 1}

    @api.get("/api/v1/auth/config")
    def auth_config():
        return {"mode": "development" if s.dev_auth else "oidc", "issuer": s.issuer, "audience": s.audience,
                "development_emails": list(s.dev_emails) if s.dev_auth else []}

    if s.dev_auth:
        @api.post("/api/v1/dev/token")
        def dev_token(email: str, request: Request):
            if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                raise HTTPException(403, "Local test identities require a loopback connection")
            return {"access_token": verifier.development_token(email), "token_type": "bearer", "expires_in": 1800}

    @api.get("/api/v1/me")
    def me(who=Depends(identity), db=Depends(database)):
        return {"id": who.id, "email": who.email, "name": who.name}

    @api.get("/api/v1/organizations")
    def organizations(db=Depends(database), who=Depends(identity)):
        # Discovery policy exposes only the actor's own active memberships.
        rows = db.execute(select(Organization, Membership.role).join(Membership, Membership.organization_id == Organization.id)
                          .where(Membership.user_id == who.id, Membership.active.is_(True)).order_by(Organization.name)).all()
        return {"items": [{**record(org, "id name timezone created_at"), "role": role} for org, role in rows]}

    @api.post("/api/v1/organizations", status_code=201)
    def register(body: OrganizationIn, request: Request, db=Depends(database), who=Depends(identity)):
        oid = str(uuid4())
        set_context(db, who.id, oid, who.email)
        org = Organization(id=oid, **body.model_dump(), created_by=who.id)
        db.add(org)
        db.flush()
        member = Membership(organization_id=oid, user_id=who.id, email=who.email, role="administrator")
        db.add(member)
        db.flush()
        audit((db, who, member, oid), request, "organization.registered", oid, {"name": org.name})
        return record(org, "id name timezone created_at")

    @api.get("/api/v1/organizations/{o}/memberships")
    def members(ctx=Depends(scope)):
        admin(ctx)
        return {"items": [record(m, "id user_id email role active row_version") for m in ctx[0].scalars(select(Membership).where(Membership.organization_id == ctx[3]).order_by(Membership.email))]}

    @api.patch("/api/v1/organizations/{o}/memberships/{m}")
    def update_member(m: UUID, body: MemberPatch, request: Request, if_match: str | None = Header(default=None), ctx=Depends(scope)):
        admin(ctx)
        db, who, _, oid = ctx
        # Serialize all membership changes to prevent concurrent last-admin removal.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:oid, 0))"), {"oid": oid})
        if not db.scalar(text("SELECT app_private.admin(:oid)"), {"oid": oid}):
            raise HTTPException(403, "Administrator access has changed; refresh your session")
        row = db.scalar(select(Membership).where(Membership.id == str(m), Membership.organization_id == oid).with_for_update())
        if not row:
            raise HTTPException(404, "Member not found")
        match(row.row_version, if_match)
        if row.user_id == who.id and not body.active:
            raise HTTPException(409, "Ask another administrator to deactivate your membership")
        admins = list(db.scalars(select(Membership).where(Membership.organization_id == oid, Membership.role == "administrator", Membership.active.is_(True))))
        if row.active and row.role == "administrator" and (not body.active or body.role != "administrator") and len(admins) <= 1:
            raise HTTPException(409, "At least one active administrator must remain")
        before = record(row, "role active")
        row.role, row.active = body.role, body.active
        row.row_version += 1
        audit(ctx, request, "membership.changed", row.id, {"before": before, "after": body.model_dump()})
        return record(row, "id user_id email role active row_version")

    @api.post("/api/v1/organizations/{o}/invitations", status_code=201)
    def invite(body: InvitationIn, request: Request, ctx=Depends(scope)):
        admin(ctx)
        token = secrets.token_urlsafe(32)
        row = Invitation(organization_id=ctx[3], email=body.email, role=body.role, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(days=3))
        ctx[0].add(row)
        ctx[0].flush()
        audit(ctx, request, "invitation.created", row.id, {"role": body.role})
        return {"id": row.id, "token": token, "expires_at": row.expires_at, "delivery": "Copy securely; no email has been sent"}

    @api.post("/api/v1/invitations/accept")
    def accept_invite(request: Request, body: dict, db=Depends(database), who=Depends(identity)):
        token = body.get("token", "")
        if not isinstance(token, str) or len(token) > 256:
            raise HTTPException(422, "Invalid invitation")
        digest = hashlib.sha256(token.encode()).hexdigest()
        set_context(db, who.id, email=who.email, invite=digest)
        row = db.scalar(select(Invitation).where(Invitation.token_hash == digest).with_for_update())
        if not row or row.accepted_at or row.expires_at <= datetime.now(timezone.utc) or row.email != who.email:
            raise HTTPException(404, "Invitation is invalid, expired, or already used")
        set_context(db, who.id, row.organization_id, who.email, digest)
        member = Membership(organization_id=row.organization_id, user_id=who.id, email=who.email, role=row.role)
        db.add(member)
        db.flush()
        row.accepted_at = datetime.now(timezone.utc)
        audit((db, who, member, row.organization_id), request, "invitation.accepted", row.id)
        return {"organization_id": row.organization_id}

    @api.get("/api/v1/organizations/{o}/projects")
    def projects(after: str = "", limit: int = Query(default=50, ge=1, le=200), ctx=Depends(scope)):
        db, who, member, oid = ctx
        stmt = select(Project).where(Project.organization_id == oid, Project.id > after)
        if member.role != "administrator":
            stmt = stmt.where(Project.id.in_(select(ProjectMembership.project_id).where(ProjectMembership.organization_id == oid, ProjectMembership.user_id == who.id, ProjectMembership.active.is_(True))))
        rows = list(db.scalars(stmt.order_by(Project.id).limit(limit+1)))
        return {"items": [project_out(r) for r in rows[:limit]], "next_cursor": rows[limit-1].id if len(rows) > limit else None}

    @api.post("/api/v1/organizations/{o}/projects", status_code=201)
    def add_project(body: ProjectIn, request: Request, ctx=Depends(scope)):
        admin(ctx)
        data = body.model_dump()
        data["start_date"] = body.start_date.isoformat()
        row = Project(organization_id=ctx[3], **data)
        ctx[0].add(row)
        ctx[0].flush()
        audit(ctx, request, "project.created", row.id, {"code": row.code}, row.id)
        return project_out(row)

    @api.get("/api/v1/organizations/{o}/projects/{p}")
    def get_project(p: UUID, response: Response, ctx=Depends(scope)):
        row, role = project_scope(ctx, p)
        response.headers["ETag"] = f'"{row.row_version}"'
        return {**project_out(row), "effective_role": role}

    @api.patch("/api/v1/organizations/{o}/projects/{p}")
    def edit_project(p: UUID, body: ProjectPatch, request: Request, if_match: str | None = Header(default=None), ctx=Depends(scope)):
        project_scope(ctx, p, write=True)
        row = ctx[0].scalar(select(Project).where(Project.organization_id == ctx[3], Project.id == str(p)).with_for_update())
        match(row.row_version, if_match)
        before = record(row, "name archived")
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        row.row_version += 1
        audit(ctx, request, "project.changed", row.id, {"before": before, "after": body.model_dump(exclude_unset=True)}, row.id)
        return project_out(row)

    @api.get("/api/v1/organizations/{o}/projects/{p}/memberships")
    def project_members(p: UUID, ctx=Depends(scope)):
        project_scope(ctx, p, write=True)
        rows = ctx[0].scalars(select(ProjectMembership).where(ProjectMembership.organization_id == ctx[3], ProjectMembership.project_id == str(p)))
        return {"items": [record(r, "id user_id role active row_version") for r in rows]}

    @api.post("/api/v1/organizations/{o}/projects/{p}/memberships", status_code=201)
    def assign_member(p: UUID, body: ProjectMemberIn, request: Request, ctx=Depends(scope)):
        admin(ctx)  # Project managers cannot escalate project roles in Phase 1.
        project_scope(ctx, p, write=True)
        db, _, _, oid = ctx
        member = db.scalar(select(Membership).where(Membership.organization_id == oid, Membership.user_id == body.user_id, Membership.active.is_(True)))
        if not member:
            raise HTTPException(404, "Active organization member not found")
        row = db.scalar(select(ProjectMembership).where(ProjectMembership.organization_id == oid, ProjectMembership.project_id == str(p), ProjectMembership.user_id == body.user_id).with_for_update())
        if row:
            raise HTTPException(409, "Project membership exists; use the versioned update endpoint")
        row = ProjectMembership(organization_id=oid, project_id=str(p), **body.model_dump())
        db.add(row)
        db.flush()
        audit(ctx, request, "project.membership.created", row.id, body.model_dump(), str(p))
        return record(row, "id user_id role active row_version")

    @api.patch("/api/v1/organizations/{o}/projects/{p}/memberships/{m}")
    def edit_project_member(p: UUID, m: UUID, body: ProjectMemberIn, request: Request, if_match: str | None = Header(default=None), ctx=Depends(scope)):
        admin(ctx)
        project_scope(ctx, p, write=True)
        row = ctx[0].scalar(select(ProjectMembership).where(ProjectMembership.organization_id == ctx[3], ProjectMembership.project_id == str(p), ProjectMembership.id == str(m)).with_for_update())
        if not row or row.user_id != body.user_id:
            raise HTTPException(404, "Project membership not found")
        match(row.row_version, if_match)
        before = row.role
        row.role, row.active = body.role, body.active
        row.row_version += 1
        audit(ctx, request, "project.membership.changed", row.id, {"before_role": before, "after": body.model_dump()}, str(p))
        return record(row, "id user_id role active row_version")

    def calendar_out(row):
        return record(row, "id calendar_id version name timezone nominal_minutes_per_day week exceptions content_hash created_at")

    @api.get("/api/v1/organizations/{o}/projects/{p}/calendars")
    def calendars(p: UUID, ctx=Depends(scope)):
        project_scope(ctx, p)
        rows = ctx[0].scalars(select(CalendarVersion).where(CalendarVersion.organization_id == ctx[3], CalendarVersion.project_id == str(p)).order_by(CalendarVersion.calendar_id, CalendarVersion.version.desc()))
        return {"items": [calendar_out(r) for r in rows]}

    def save_calendar(p, body, request, ctx, calendar_id=None):
        project_scope(ctx, p, write=True, calendar=True)
        db, who, _, oid = ctx
        version = 1
        if calendar_id:
            # Lock parent project to serialize version numbering for each calendar.
            db.execute(select(Project).where(Project.id == str(p), Project.organization_id == oid).with_for_update()).scalar_one()
            old = db.scalar(select(CalendarVersion).where(CalendarVersion.organization_id == oid, CalendarVersion.project_id == str(p), CalendarVersion.calendar_id == str(calendar_id)).order_by(CalendarVersion.version.desc()))
            if not old:
                raise HTTPException(404, "Calendar not found")
            version = old.version + 1
        payload = body.model_dump()
        content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        row = CalendarVersion(organization_id=oid, project_id=str(p), calendar_id=str(calendar_id or uuid4()), version=version,
                              created_by=who.id, content_hash=content_hash, **payload)
        db.add(row)
        db.flush()
        audit(ctx, request, "calendar.version.created", row.id, {"calendar_id": row.calendar_id, "version": version, "hash": content_hash}, str(p))
        return calendar_out(row)

    @api.post("/api/v1/organizations/{o}/projects/{p}/calendars", status_code=201)
    def add_calendar(p: UUID, body: CalendarIn, request: Request, ctx=Depends(scope)):
        return save_calendar(p, body, request, ctx)

    @api.post("/api/v1/organizations/{o}/projects/{p}/calendars/{c}/versions", status_code=201)
    def version_calendar(p: UUID, c: UUID, body: CalendarIn, request: Request, ctx=Depends(scope)):
        return save_calendar(p, body, request, ctx, c)

    @api.get("/api/v1/organizations/{o}/audit-events")
    def audit_events(after: str = "", limit: int = Query(default=50, ge=1, le=200), ctx=Depends(scope)):
        admin(ctx)
        stmt = select(AuditEvent).where(AuditEvent.organization_id == ctx[3])
        if after:
            try:
                if len(after) > 300:
                    raise ValueError()
                stamp, identifier = json.loads(base64.urlsafe_b64decode(after.encode()))
                stamp = datetime.fromisoformat(stamp)
                identifier = str(UUID(identifier))
                if stamp.tzinfo is None:
                    raise ValueError()
            except (ValueError, TypeError, binascii.Error):
                raise HTTPException(422, "Invalid audit cursor")
            stmt = stmt.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (stamp, identifier))
        rows = list(ctx[0].scalars(stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit+1)))
        cursor = None
        if len(rows) > limit:
            tail = rows[limit-1]
            cursor = base64.urlsafe_b64encode(json.dumps([tail.created_at.isoformat(), tail.id]).encode()).decode()
        return {"items": [record(r, "id project_id actor_id action entity_id details request_id created_at") for r in rows[:limit]], "next_cursor": cursor}

    return api

