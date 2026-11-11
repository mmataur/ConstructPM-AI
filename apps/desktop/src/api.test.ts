import { describe, expect, it, vi, afterEach } from 'vitest';
import { request, setToken, ApiError } from './api';
afterEach(()=>{vi.unstubAllGlobals();setToken('');});
describe('API boundary',()=>{
  it('sends access credentials and concurrency version only in headers',async()=>{
    const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({id:'project'})});vi.stubGlobal('fetch',fetch);setToken('private-token');
    await request('/organizations/company/projects/project','PATCH',{name:'Changed'},7);
    expect(fetch.mock.calls[0][0]).not.toContain('private-token');
    expect(fetch.mock.calls[0][1].headers).toMatchObject({Authorization:'Bearer private-token','If-Match':'"7"'});
  });
  it('preserves failures for user review rather than treating failed writes as saved',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:412,json:async()=>({message:'Refresh before editing'})}));
    await expect(request('/projects','PATCH',{name:'x'},1)).rejects.toMatchObject({status:412,message:'Refresh before editing'});
  });
});
