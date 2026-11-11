import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'e2e',workers:1,timeout:60000,use:{baseURL:'http://127.0.0.1:1420',viewport:{width:1440,height:1000},headless:true,
  launchOptions:process.env.PLAYWRIGHT_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH}:{}},reporter:'list'});
