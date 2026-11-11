import { test, expect, Page } from '@playwright/test';

async function login(page:Page,email:string){
  await page.goto('/');
  await page.getByRole('button',{name:email}).click();
  await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
}

test('company, project, calendar, invitation, assignment and supervisor access',async({page,browser,request})=>{
  const config=await request.get('http://127.0.0.1:8000/api/v1/auth/config');
  expect((await config.json()).mode,'E2E is restricted to local demonstration identity').toBe('development');
  const company=`Foundation Demo ${Date.now()}`;
  await login(page,'planner@example.test');
  await page.getByLabel('Company workspace').selectOption('');
  await page.getByLabel('Company name',{exact:true}).fill(company);
  await page.getByRole('button',{name:'Create company workspace'}).click();
  await expect(page.getByRole('heading',{name:company,exact:true})).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Projects',exact:true}).click();
  const create=page.locator('section').filter({has:page.getByRole('heading',{name:'Create a project',exact:true})});
  await create.getByLabel('Project code').fill('DEMO-01');
  await create.getByLabel('Project name').fill('Community Health Centre');
  await create.getByLabel('Planned start').fill('2027-01-04');
  await create.getByRole('button',{name:'Create project',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Project created.'})).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Calendars'}).click();
  await page.getByLabel('Nonworking date exceptions').fill('2027-01-01');
  await page.getByRole('button',{name:'Save calendar version'}).click();
  await expect(page.getByText('Version 1',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Create next version'}).click();
  await page.getByLabel('Calendar name').fill('Standard working week revised');
  await page.getByLabel('Nonworking date exceptions').fill('2027-01-01\n2027-04-02');
  await page.getByRole('button',{name:'Save calendar version'}).click();
  await expect(page.getByText('Version 2',{exact:true})).toBeVisible();
  await expect(page.getByText('Version 1',{exact:true})).toBeVisible();

  await page.getByRole('navigation').getByRole('button',{name:'People',exact:true}).click();
  await page.getByLabel('Verified email address').fill('supervisor@example.test');
  await page.getByRole('button',{name:'Create invitation'}).click();
  const tokenField=page.getByLabel('One-time invitation token');
  await expect(tokenField).not.toHaveValue('');
  const token=await tokenField.inputValue();
  const workerContext=await browser.newContext();
  const worker=await workerContext.newPage();
  await login(worker,'supervisor@example.test');
  await worker.getByLabel('Company workspace').selectOption('');
  await worker.getByLabel('Invitation token',{exact:true}).fill(token);
  await worker.getByRole('button',{name:'Accept invitation'}).click();
  await expect(worker.getByRole('heading',{name:company,exact:true})).toBeVisible();
  await expect(worker.getByRole('navigation').getByRole('button',{name:'People',exact:true})).toHaveCount(0);
  await expect(worker.getByText('Your first project starts here')).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Overview',exact:true}).click();
  await page.getByRole('navigation').getByRole('button',{name:'People',exact:true}).click();
  await page.getByRole('combobox',{name:'Company member',exact:true}).selectOption({label:'supervisor@example.test'});
  await page.getByRole('combobox',{name:'Project role',exact:true}).selectOption('supervisor');
  await page.getByRole('button',{name:'Assign',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Project access assigned to supervisor@example.test'})).toBeVisible();
  await worker.getByRole('button',{name:'Sign out',exact:true}).click();
  await login(worker,'supervisor@example.test');
  await worker.getByLabel('Company workspace').selectOption({label:company});
  await expect(worker.getByRole('button',{name:/DEMO-01 Community Health Centre/})).toBeVisible();
  await worker.getByRole('navigation').getByRole('button',{name:'Calendars'}).click();
  await expect(worker.getByText('Version 2',{exact:true})).toBeVisible();
  await expect(worker.getByRole('button',{name:'Save calendar version'})).toHaveCount(0);
  await page.getByRole('navigation').getByRole('button',{name:'Audit history'}).click();
  await expect(page.getByRole('cell',{name:'project.created',exact:true})).toBeVisible();
  await page.getByRole('navigation').getByRole('button',{name:'Overview',exact:true}).click();
  await page.screenshot({path:'test-results/foundation-overview.png',fullPage:true});
  await workerContext.close();
});
