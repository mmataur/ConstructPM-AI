export const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
let token = '';
export function setToken(value: string) { token = value; }
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function request<T>(path: string, method = 'GET', body?: unknown, version?: number, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, {method, signal, headers: {
    ...(token ? {Authorization: `Bearer ${token}`} : {}), ...(body ? {'Content-Type':'application/json'} : {}), ...(version ? {'If-Match': `"${version}"`} : {})
  }, body: body ? JSON.stringify(body) : undefined});
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.fields?.map((f: {message: string}) => f.message).join('; ') || data.message || 'Request failed', response.status);
  return data;
}
export type Organization = {id:string; name:string; timezone:string; role:string};
export type Project = {id:string; code:string; name:string; timezone:string; start_date:string; discipline:string; archived:boolean; row_version:number; effective_role?:string};
export type Member = {id:string; user_id:string; email:string; role:string; active:boolean; row_version:number};
export type ProjectMember = {id:string; user_id:string; role:string; active:boolean; row_version:number};
export type Calendar = {id:string; calendar_id:string; version:number; name:string; timezone:string; nominal_minutes_per_day:number; week:Record<string,string[][]>; exceptions:Record<string,string[][]>; content_hash:string};
export type Audit = {id:string; action:string; actor_id:string; entity_id:string; created_at:string; details:unknown};
export const projectRoles = ['project_manager','planner','site_engineer','supervisor','quantity_surveyor','executive','subcontractor','guest'];
export const label = (text:string) => text.replaceAll('_',' ').replace(/^\w/, c => c.toUpperCase());
