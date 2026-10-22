from pathlib import Path
path=Path(r'D:\CodexCache\office-windows\upstream\DesktopEditors\web-apps\apps\common\main\lib\controller\Desktop.js')
raw=path.read_bytes();newline=b'\r\n' if b'\r\n' in raw else b'\n';text=raw.decode('utf-8').replace('\r\n','\n')
start=text.index('        const _checkHelpAvailable = function () {');end=text.index('        const _onAppReady = function (opts) {',start)
replacement='''        const _checkHelpAvailable = function () {
            const me = this;
            const languages = [Common.Locale.getCurrentLanguage(), Common.Locale.getDefaultLanguage(), 'en']
                .filter(function (lang, index, list) { return lang && list.indexOf(lang) === index; });
            const findHelp = function (base, index) {
                if (index >= languages.length)
                    return Promise.reject(new Error('Help language unavailable'));
                const url = base.replace(/\\/?$/, '/') + languages[index] + '/';
                return fetch(url + 'Contents.json')
                    .then(function (response) {
                        if (!response.ok)
                            throw new Error('Help contents unavailable');
                        return response.json();
                    })
                    .then(function (contents) {
                        if (!Array.isArray(contents))
                            throw new Error('Invalid help contents');
                        helpUrl = url;
                    })
                    .catch(function () { return findHelp(base, index + 1); });
            };
            return findHelp('resources/help/', 0)
                .catch(function () {
                    if (me.helpUrl())
                        return findHelp(me.helpUrl(), 0);
                })
                .catch(function () {});
        }

'''
assert 'build_url' in text[start:end],'Already changed; do not apply twice'
path.write_bytes((text[:start]+replacement+text[end:]).replace('\n',newline.decode()).encode('utf-8'))
print('Prepared local-help language fallback; source line endings preserved.')
