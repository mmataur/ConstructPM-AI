from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.auth import TokenVerifier
from app.db import set_context


def path(org, rest=""):
    return f"/api/v1/organizations/{org}" + rest


def test_unauthenticated_and_invalid_token(client):
    assert client.get("/api/v1/organizations").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


@pytest.mark.parametrize("change", [{"aud": "wrong"}, {"iss": "wrong"}, {"email_verified": False}, {"exp": 1}])
def test_token_claims_fail_closed(client, settings, change):
    claims = jwt.decode(TokenVerifier(settings).development_token("owner@example.test"), options={"verify_signature": False})
    claims.update(change)
    token = jwt.encode(claims, settings.dev_secret, algorithm="HS256")
    assert client.get("/api/v1/me", headers={"Authorization":"Bearer "+token}).status_code == 401


def test_development_identity_disabled_in_production(settings):
    with pytest.raises(RuntimeError):
        replace(settings, environment="production").validate()
    with pytest.raises(RuntimeError):
        replace(settings, dev_auth=False, issuer="", jwks_url="").validate()


def test_registration_discovery_and_audit(client, headers, company):
    org = company()
    mine = client.get("/api/v1/organizations", headers=headers["owner"]).json()["items"]
    theirs = client.get("/api/v1/organizations", headers=headers["other"]).json()["items"]
    assert org in [o["id"] for o in mine]
    assert org not in [o["id"] for o in theirs]
    events = client.get(path(org,"/audit-events"), headers=headers["owner"]).json()["items"]
    assert [e["action"] for e in events] == ["organization.registered"]
    assert events[0]["request_id"]


def test_tenant_reads_and_mutations_hidden(client, headers, company, project, calendar):
    org, other = company(), company("other")
    p = project(org)
    for suffix in ("/projects", "/memberships", "/audit-events", f"/projects/{p['id']}", f"/projects/{p['id']}/calendars"):
        assert client.get(path(org,suffix), headers=headers["other"]).status_code == 404
    assert client.get(path(other,f"/projects/{p['id']}"), headers=headers["other"]).status_code == 404
    assert client.post(path(other,f"/projects/{p['id']}/calendars"), headers=headers["other"], json=calendar).status_code == 404
    assert client.patch(path(org,f"/projects/{p['id']}"), headers={**headers["other"],"If-Match":'"1"'}, json={"name":"Stolen"}).status_code == 404


def test_project_edit_concurrency_and_scope(client, headers, company, project):
    org=company(); p=project(org); url=path(org,f"/projects/{p['id']}")
    read=client.get(url,headers=headers["owner"])
    assert read.headers["etag"]=='"1"'
    assert client.patch(url,headers=headers["owner"],json={"name":"New name"}).status_code==428
    changed=client.patch(url,headers={**headers["owner"],"If-Match":'"1"'},json={"name":"New name"})
    assert changed.status_code==200
    assert changed.json()["row_version"]==2
    assert client.patch(url,headers={**headers["owner"],"If-Match":'"1"'},json={"name":"Lost update"}).status_code==412
    assert client.patch(url,headers={**headers["owner"],"If-Match":'"2"'},json={"organization_id":str(uuid4())}).status_code==422


def test_invitation_email_reuse_and_expiration(client, headers, company, enroll, app):
    org=company()
    invite=client.post(path(org,"/invitations"),headers=headers["owner"],json={"email":"worker@example.test"}).json()
    token=invite["token"]
    assert client.post("/api/v1/invitations/accept",headers=headers["other"],json={"token":token}).status_code==404
    assert client.post("/api/v1/invitations/accept",headers=headers["worker"],json={"token":token}).status_code==200
    assert client.post("/api/v1/invitations/accept",headers=headers["worker"],json={"token":token}).status_code==404
    invite=client.post(path(org,"/invitations"),headers=headers["owner"],json={"email":"other@example.test"}).json()
    who=client.get("/api/v1/me",headers=headers["owner"]).json()
    with app.state.factory.begin() as db:
        set_context(db,who["id"],org,who["email"])
        db.execute(text("UPDATE invitations SET expires_at=now()-interval '1 minute' WHERE id=:id"),{"id":invite["id"]})
    assert client.post("/api/v1/invitations/accept",headers=headers["other"],json={"token":invite["token"]}).status_code==404


def test_last_admin_protected_and_revocation_effective(client, headers, company, enroll):
    org=company(); who,_=enroll(org)
    members=client.get(path(org,"/memberships"),headers=headers["owner"]).json()["items"]
    owner=next(m for m in members if m["role"]=="administrator")
    worker=next(m for m in members if m["user_id"]==who["id"])
    assert client.patch(path(org,"/memberships/"+owner["id"]),headers={**headers["owner"],"If-Match":'"1"'},json={"role":"member","active":True}).status_code==409
    assert client.patch(path(org,"/memberships/"+worker["id"]),headers={**headers["owner"],"If-Match":'"1"'},json={"role":"member","active":False}).status_code==200
    assert client.get(path(org,"/projects"),headers=headers["worker"]).status_code==404
    assert org not in [x["id"] for x in client.get("/api/v1/organizations",headers=headers["worker"]).json()["items"]]


@pytest.mark.parametrize("role,calendar_status,edit_status", [
    ("project_manager",201,200),("planner",201,403),("site_engineer",403,403),("supervisor",403,403),
    ("quantity_surveyor",403,403),("executive",403,403),("subcontractor",403,403),("guest",403,403)])
def test_role_matrix(client, headers, company, project, enroll, calendar, role, calendar_status, edit_status):
    org=company();p=project(org);who,_=enroll(org)
    assert client.get(path(org,f"/projects/{p['id']}"),headers=headers["worker"]).status_code==404
    assigned=client.post(path(org,f"/projects/{p['id']}/memberships"),headers=headers["owner"],json={"user_id":who["id"],"role":role})
    assert assigned.status_code==201, assigned.text
    assert client.get(path(org,f"/projects/{p['id']}"),headers=headers["worker"]).status_code==200
    assert len(client.get(path(org,"/projects"),headers=headers["worker"]).json()["items"])==1
    assert client.post(path(org,f"/projects/{p['id']}/calendars"),headers=headers["worker"],json=calendar).status_code==calendar_status
    assert client.patch(path(org,f"/projects/{p['id']}"),headers={**headers["worker"],"If-Match":'"1"'},json={"name":"Reviewed project"}).status_code==edit_status
    assert client.post(path(org,"/invitations"),headers=headers["worker"],json={"email":"x@example.test","role":"administrator"}).status_code==403
    assert client.get(path(org,"/audit-events"),headers=headers["worker"]).status_code==403


def test_calendar_versions_and_immutable_evidence(client,headers,company,project,calendar,app):
    org=company();p=project(org);url=path(org,f"/projects/{p['id']}/calendars")
    first=client.post(url,headers=headers["owner"],json=calendar).json()
    calendar["exceptions"]["2027-01-04"]=[]
    second=client.post(url+f"/{first['calendar_id']}/versions",headers=headers["owner"],json=calendar)
    assert second.status_code==201, second.text
    assert second.json()["version"]==2
    assert first["content_hash"] != second.json()["content_hash"]
    rows=client.get(url,headers=headers["owner"]).json()["items"]
    assert len(rows)==2
    assert next(c for c in rows if c["id"]==first["id"])["exceptions"]=={"2027-01-01":[]}
    who=client.get("/api/v1/me",headers=headers["owner"]).json()
    for sql in ("UPDATE calendar_versions SET name='tamper' WHERE id=:id", "DELETE FROM audit_events WHERE organization_id=:org"):
        with pytest.raises(DBAPIError):
            with app.state.factory.begin() as db:
                set_context(db,who["id"],org,who["email"])
                db.execute(text(sql),{"id":first["id"],"org":org})


@pytest.mark.parametrize("bad", ["overlap","timezone","missing_weekday","negative_day","date"])
def test_invalid_calendars_rejected(client,headers,company,project,calendar,bad):
    org=company();p=project(org)
    if bad=="overlap":calendar["week"]["1"]=[["08:00","13:00"],["12:00","17:00"]]
    if bad=="timezone":calendar["timezone"]="Not/AZone"
    if bad=="missing_weekday":del calendar["week"]["7"]
    if bad=="negative_day":calendar["nominal_minutes_per_day"]=-1
    if bad=="date":calendar["exceptions"]={"2027-02-30":[]}
    assert client.post(path(org,f"/projects/{p['id']}/calendars"),headers=headers["owner"],json=calendar).status_code==422


def test_runtime_rls_missing_context_and_connection_reuse(client,headers,company,project,app):
    org=company();p=project(org)
    owner=client.get("/api/v1/me",headers=headers["owner"]).json();other=client.get("/api/v1/me",headers=headers["other"]).json()
    with app.state.factory.begin() as db:
        role=db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
        assert not role.rolsuper and not role.rolbypassrls
        assert db.execute(text("SELECT id FROM projects")).all()==[]
        set_context(db,owner["id"],org,owner["email"])
        assert db.execute(text("SELECT id FROM projects WHERE id=:id"),{"id":p["id"]}).scalar()==p["id"]
        set_context(db,other["id"],org,other["email"])
        assert db.execute(text("SELECT id FROM projects WHERE id=:id"),{"id":p["id"]}).scalar() is None
    with app.state.factory.begin() as db:
        assert db.execute(text("SELECT current_setting('app.tenant',true)")).scalar() in (None,"")
        assert db.execute(text("SELECT id FROM projects")).all()==[]


def test_database_rejects_cross_tenant_reference(client,headers,company,project,app):
    org=company();other=company();p=project(org);who=client.get("/api/v1/me",headers=headers["owner"]).json()
    with pytest.raises(DBAPIError):
        with app.state.factory.begin() as db:
            set_context(db,who["id"],other,who["email"])
            db.execute(text("INSERT INTO project_memberships(id,organization_id,project_id,user_id,role,row_version) VALUES(:id,:org,:p,:u,'planner',1)"),{"id":str(uuid4()),"org":other,"p":p["id"],"u":who["id"]})


def test_pagination_and_safe_error_payload(client,headers,company,project):
    org=company();project(org);project(org);project(org)
    r=client.get(path(org,"/projects?limit=2"),headers=headers["owner"]).json()
    assert len(r["items"])==2 and r["next_cursor"]
    rest=client.get(path(org,"/projects?limit=2&after="+r["next_cursor"]),headers=headers["owner"]).json()
    assert len(rest["items"])==1
    bad=client.post(path(org,"/projects"),headers=headers["owner"],json={"secret":"should-not-echo"})
    assert bad.status_code==422 and "should-not-echo" not in bad.text
    assert bad.headers["x-request-id"]


def test_project_access_revocation_preserves_company_access(client,headers,company,project,enroll):
    org=company();p=project(org);who,_=enroll(org)
    url=path(org,f"/projects/{p['id']}/memberships")
    assigned=client.post(url,headers=headers["owner"],json={"user_id":who["id"],"role":"supervisor"}).json()
    change=client.patch(url+"/"+assigned["id"],headers={**headers["owner"],"If-Match":'"1"'},json={"user_id":who["id"],"role":"supervisor","active":False})
    assert change.status_code==200,change.text
    assert not change.json()["active"]
    assert client.get(path(org,"/projects"),headers=headers["worker"]).json()["items"]==[]
    assert client.get(path(org,f"/projects/{p['id']}"),headers=headers["worker"]).status_code==404
    assert org in [o["id"] for o in client.get("/api/v1/organizations",headers=headers["worker"]).json()["items"]]


def test_concurrent_admin_demotion_keeps_an_administrator(client,headers,company,enroll):
    org=company();enroll(org,"other","administrator")
    rows=client.get(path(org,"/memberships"),headers=headers["owner"]).json()["items"]
    def demote(actor):
        email={"owner":"owner@example.test","other":"other@example.test"}[actor]
        member=next(row for row in rows if row["email"]==email)
        return client.patch(path(org,"/memberships/"+member["id"]),headers={**headers[actor],"If-Match":'"1"'},json={"role":"member","active":True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(demote,["owner","other"]))
    assert sorted(outcomes)==[200,409]


def test_audit_cursor_orders_and_validates(client,headers,company,project):
    org=company();project(org);project(org)
    first=client.get(path(org,"/audit-events?limit=2"),headers=headers["owner"]).json()
    second=client.get(path(org,"/audit-events?limit=2&after="+first["next_cursor"]),headers=headers["owner"]).json()
    assert len(first["items"])==2 and len(second["items"])==1
    assert len({e["id"] for e in first["items"]+second["items"]})==3
    assert first["items"][0]["created_at"]>=second["items"][0]["created_at"]
    assert client.get(path(org,"/audit-events?after=nonsense"),headers=headers["owner"]).status_code==422

