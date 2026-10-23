// Test boundary only. The production HTML never contains this adapter or sample history.
window.__bridgeCommands = [];
const fixtureDark = new URLSearchParams(location.search).get('uitheme') === 'theme-dark';
window.RendererProcessVariable = {localthemes: [], theme: {id: fixtureDark ? 'theme-dark' : 'theme-white', type: fixtureDark ? 'dark' : 'light', system: 'disabled'}};
window.AscDesktopEditor = {
    execCommand: function (command, payload) { window.__bridgeCommands.push({command, payload}); },
    GetCryptoMode: function () { return 0; },
    GetSupportCryptoModes: function () { return []; },
    GetExternalClouds: function () { return []; },
    GetLocalFeatures: function () { return false; },
    LocalFileRecents: function () {},
    LocalFileRecovers: function () {},
    LocalFileTemplates: function () {},
    LocalFileRemoveAllRecents: function () { window.onupdaterecents([]); },
    LocalFileRemoveRecent: function () {},
    LocalFileRemoveAllRecovers: function () { window.onupdaterecovers([]); },
    LocalFileRemoveRecover: function () {}
};
