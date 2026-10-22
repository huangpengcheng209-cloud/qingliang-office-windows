// Rebuild the four pinned main application bundles using upstream AMD lists.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const child = require('child_process');
const stage = 'D:/CodexCache/office-windows';
const task = 'D:/CodexWorkspaces/2026-10-13/office-windows';
const web = path.join(stage, 'upstream/DesktopEditors/web-apps');
const requirejs = require(path.join(stage, 'js-tools/node_modules/requirejs'));
const terser = require(path.join(stage, 'js-tools/node_modules/terser'));
const vm = require('vm');
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const output = path.join(stage, 'build/web-apps');
fs.mkdirSync(output, {recursive: true});
process.chdir(path.join(web, 'build'));

async function main() {
  const reports = [];
  const gruntfile = fs.readFileSync(path.join(web, 'build/Gruntfile.js'), 'utf8');
  const replacementBlock = gruntfile.match(/global\.jsreplacements\s*=\s*(\[[\s\S]*?\]);/);
  if (!replacementBlock) throw new Error('Upstream branding replacement definitions were not found');
  // Use the pinned upstream defaults; publisher identity remains upstream attribution.
  const replacements = vm.runInNewContext('(' + replacementBlock[1] + ')', {
    _encode: value => value, process: {env: {DEFAULT_LANG: 'zh-CN'}}
  });
  const patched = path.join(web, 'apps/common/main/lib/controller/Desktop.js');
  for (const editor of ['documenteditor', 'spreadsheeteditor', 'presentationeditor', 'pdfeditor']) {
    const config = JSON.parse(fs.readFileSync(editor + '.json', 'utf8'));
    const options = {...config.main.js.requirejs.options, optimize: 'none'};
    const destination = path.join(output, editor, 'main/app.js');
    fs.mkdirSync(path.dirname(destination), {recursive: true});
    options.out = destination;
    const inputs = {};
    options.onBuildRead = function(module, file, contents) {
      if (fs.existsSync(file)) inputs[file] = sha(file);
      return contents;
    };
    console.log('Building ' + editor + ' AMD application');
    const response = await new Promise((resolve, reject) => requirejs.optimize(options, resolve, reject));
    fs.writeFileSync(path.join(stage, 'logs', 'build-web-' + editor + '.log'), response);
    if (!Object.keys(inputs).some(file => path.resolve(file).toLowerCase() === path.resolve(patched).toLowerCase())) {
      throw new Error('Patched Desktop controller was omitted: ' + editor);
    }
    let content = fs.readFileSync(destination, 'utf8').replaceAll('{{PRODUCT_VERSION}}', '9.4.0.129');
    for (const replacement of replacements) content = content.replace(replacement.from, replacement.to);
    const unresolved = [...new Set(content.match(/\{\{[A-Z_]+\}\}/g) || [])];
    if (unresolved.length) throw new Error('Unresolved release placeholders: ' + unresolved.join(', '));
    const minified = await terser.minify(content, {format: {comments: false}});
    if (!minified.code) throw new Error('Empty application output');
    const banner = '/*! Copyright (c) Ascensio System SIA 2026. All rights reserved.\n * https://www.onlyoffice.com/\n * Version: 9.4.0 (build:129)\n */\n';
    fs.writeFileSync(destination, banner + minified.code, 'utf8');
    child.execFileSync(process.execPath, ['--check', destination]);
    const postloadDestination = path.join(output, editor, 'main/code.js');
    const postloadInputs = {};
    const postloadOptions = {...config.main.js.postload.options, optimize: 'none', out: postloadDestination};
    postloadOptions.onBuildRead = (module, file, contents) => {
      if (fs.existsSync(file)) postloadInputs[file] = sha(file);
      return contents;
    };
    const postloadLog = await new Promise((resolve, reject) => requirejs.optimize(postloadOptions, resolve, reject));
    fs.writeFileSync(path.join(stage, 'logs', 'build-web-' + editor + '-postload.log'), postloadLog);
    let postloadContent = fs.readFileSync(postloadDestination, 'utf8').replaceAll('{{PRODUCT_VERSION}}', '9.4.0.129');
    for (const replacement of replacements) postloadContent = postloadContent.replace(replacement.from, replacement.to);
    const postloadUnresolved = [...new Set(postloadContent.match(/\{\{[A-Z_]+\}\}/g) || [])];
    if (postloadUnresolved.length) throw new Error('Unresolved postload placeholders: ' + postloadUnresolved.join(', '));
    const postloadMinified = await terser.minify(postloadContent, {format: {comments: false}});
    if (!postloadMinified.code) throw new Error('Empty postload output');
    fs.writeFileSync(postloadDestination, banner + postloadMinified.code, 'utf8');
    child.execFileSync(process.execPath, ['--check', postloadDestination]);
    reports.push({editor, inputs, output: destination, output_sha256: sha(destination), postload: {inputs: postloadInputs, output: postloadDestination, output_sha256: sha(postloadDestination), unresolved_release_placeholders: postloadUnresolved}, patched_controller_sha256: sha(patched), branding_definitions_sha256: sha(path.join(web, 'build/Gruntfile.js')), unresolved_release_placeholders: unresolved, requirejs_version: requirejs.version, syntax_checked: true, integrated: false, windows_functional_acceptance: 'not_run'});
    console.log('Built ' + editor + ' with the patched Desktop controller');
  }
  fs.writeFileSync(path.join(task, 'evidence/web-controllers-build.json'), JSON.stringify(reports, null, 2));
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
