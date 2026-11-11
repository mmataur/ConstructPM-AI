import { spawnSync } from 'node:child_process';

// Run with the same Node executable as the caller; no global npm installation
// is required when Tauri invokes its frontend build hook.
for (const args of [
  ['node_modules/typescript/bin/tsc', '--noEmit'],
  ['node_modules/vite/bin/vite.js', 'build'],
]) {
  const result = spawnSync(process.execPath, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
