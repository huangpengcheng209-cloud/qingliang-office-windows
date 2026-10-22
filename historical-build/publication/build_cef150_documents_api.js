const fs=require('fs'),path=require('path'),crypto=require('crypto'),child=require('child_process');
const stage='D:/CodexCache/office-windows',task='D:/CodexWorkspaces/2026-10-13/office-windows';
const source=path.join(stage,'upstream/DesktopEditors/web-apps/apps/api/documents/api.js');
const output=path.join(stage,'build/web-apps/api/documents/api.js');
const candidate=path.join(stage,'candidate/app/editors/web-apps/apps/api/documents/api.js');
// Upstream deploy-api copies this source and substitutes the release version.
let text=fs.readFileSync(source,'utf8').replaceAll('{{PRODUCT_VERSION}}','9.4.0.129').replaceAll('{{APP_CUSTOMER_NAME}}','ONLYOFFICE');
// The desktop package deliberately leaves HASH_POSTFIX unset: upstream uses
// that guard to disable server deployment route insertion for local resources.
const unresolved=[...new Set(text.match(/\{\{[A-Z_]+\}\}/g)||[])];
if(unresolved.some(v=>v!=='{{HASH_POSTFIX}}'))throw new Error('Unexpected release placeholder');
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,text);child.execFileSync(process.execPath,['--check',output]);fs.copyFileSync(output,candidate);
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const report={source,source_sha256:sha(source),output,output_sha256:sha(output),candidate,candidate_sha256:sha(candidate),syntax_checked:true,upstream_server_prefix_guard:unresolved,runtime_acceptance:false,verified_win3_release_replaced:false};
fs.writeFileSync(path.join(task,'evidence/cef150-documents-api-build.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
