// Run the fixed upstream desktop tasks and record the AMD source files actually read.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
module.exports = function(grunt) {
    const work = path.resolve(process.env.QINGLIANG_WORK_DIR || '');
    const editor = process.env.QINGLIANG_EDITOR || '';
    if (!/^(common|documenteditor|spreadsheeteditor|presentationeditor|pdfeditor|visioeditor)$/.test(editor)) {
        throw new Error('Select one fixed desktop editor profile');
    }
    const source = path.join(work, 'sources/web-apps');
    if (!fs.existsSync(path.join(work, '.qingliang-dependency-build'))) {
        throw new Error('The marked stable build directory is required');
    }
    const reads = {};
    const original = grunt.initConfig;
    grunt.initConfig = function(config) {
        if (config.requirejs) {
            for (const [name, target] of Object.entries(config.requirejs)) {
                if (!target || !target.options || name === 'options') continue;
                const previous = target.options.onBuildRead;
                target.options.onBuildRead = function(module, file, content) {
                    const absolute = path.resolve(file);
                    if (!absolute.startsWith(path.resolve(source) + path.sep)) {
                        throw new Error('Unexpected AMD input outside the fixed source tree');
                    }
                    const relative = path.relative(source, absolute).split(path.sep).join('/');
                    if (fs.existsSync(absolute)) {
                        reads[relative] = crypto.createHash('sha256').update(fs.readFileSync(absolute)).digest('hex');
                    }
                    return previous ? previous(module, file, content) : content;
                };
            }
        }
        return original.call(grunt, config);
    };
    require(path.join(source, 'build/Gruntfile.js'))(grunt);
    process.on('exit', code => fs.writeFileSync(path.join(work, 'editor-web-amd-' + editor + '.json'),
        JSON.stringify({exit: code, inputs: reads}, null, 2)));
};
