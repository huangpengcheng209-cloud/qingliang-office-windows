/*
 * Copyright (c) 2026. This modification is distributed under AGPL-3.0.
 * The original editor toolbar and its legal notices remain available in full mode.
 */
define([], function () {
    'use strict';

    // Qingliang community, 2026-10-23: native sorting, theme-aware controls and reduced motion.

    const paths = {
        file: '<path d="M4 5h16M4 12h16M4 19h16"/>',
        search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
        open: '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v2"/><path d="M3 9h18l-2 11H5L3 9Z"/>',
        save: '<path d="M4 3h14l3 3v15H3V3h1Z"/><path d="M7 3v7h10V3M7 21v-8h10v8"/>',
        undo: '<path d="m9 5-6 6 6 6"/><path d="M3 11h11a6 6 0 0 1 0 12"/>',
        redo: '<path d="m15 5 6 6-6 6"/><path d="M21 11H10a6 6 0 0 0 0 12"/>',
        paste: '<rect x="5" y="5" width="14" height="17" rx="2"/><path d="M9 5V3h6v2M8 10h8M8 14h8"/>',
        alignleft: '<path d="M3 5h18M3 9h12M3 13h18M3 17h12"/>',
        aligncenter: '<path d="M3 5h18M6 9h12M3 13h18M6 17h12"/>',
        alignright: '<path d="M3 5h18M9 9h12M3 13h18M9 17h12"/>',
        image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m4 18 6-6 4 4 2-2 5 5"/>',
        table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16M15 4v16"/>',
        play: '<path d="m9 5 11 7-11 7V5Z"/>',
        slide: '<rect x="3" y="4" width="18" height="15" rx="2"/><path d="M8 23h8M12 19v4M12 8v7M8.5 11.5h7"/>',
        sort: '<path d="M5 4v16m-3-3 3 3 3-3M12 7h9M12 12h6M12 17h3"/>',
        text: '<path d="M4 5h16M12 5v15M8 20h8"/>',
        highlight: '<path d="m5 15 9-9 4 4-9 9H5v-4ZM15 5l2-2 4 4-2 2M3 22h18"/>',
        more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
        chevron: '<path d="m8 5 7 7-7 7"/>'
    };
    const style = `
        #toolbar.ql-simple, .ql-command-shade {
            --ql-surface:var(--background-normal,#fff);
            --ql-ink:var(--text-normal,#182235);
            --ql-muted:var(--text-secondary,#64748b);
            --ql-divider:var(--border-divider,#e3e9f1);
            --ql-control:var(--border-regular-control,#d9e2ee);
            --ql-hover:var(--highlight-button-hover,#edf4ff);
            --ql-selected:var(--highlight-button-pressed,#e6f0ff);
            --ql-link:var(--text-link,#0875f9);
            --ql-focus:var(--border-control-focus,#3487ee);
            --ql-footer:var(--background-toolbar-additional,#f8fafc);
        }
        body.ql-simple-mode #app-title { display:none !important; }
        #toolbar.ql-simple { position:relative; background:var(--ql-surface); border-bottom:1px solid var(--ql-divider); }
        #toolbar.ql-simple:not(.ql-full) > .toolbar { visibility:hidden; pointer-events:none; }
        #toolbar.ql-simple .ql-quickbar { position:absolute; inset:0 10px; z-index:7; display:flex; align-items:center; gap:2px; background:var(--ql-surface); font-family:"Microsoft YaHei UI","Segoe UI",sans-serif; }
        #toolbar.ql-simple .ql-scrollbar { display:flex; align-items:center; flex:1; min-width:0; overflow-x:auto; overflow-y:hidden; scrollbar-width:thin; }
        #toolbar.ql-simple .ql-tools { display:flex; align-items:center; flex:none; padding-left:5px; border-left:1px solid var(--ql-divider); background:var(--ql-surface); }
        #toolbar.ql-simple.ql-full .ql-quickbar { display:none; }
        #toolbar.ql-simple .ql-group { display:flex; align-items:center; gap:2px; padding:0 6px; border-right:1px solid var(--ql-divider); flex:none; }
        #toolbar.ql-simple .ql-group:last-child { border-right:0; }
        #toolbar.ql-simple .ql-action { box-sizing:border-box; min-width:52px; height:64px; padding:7px 5px 5px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; border:0; border-radius:10px; background:transparent; color:var(--ql-ink); font:13px/1.1 "Microsoft YaHei UI","Segoe UI",sans-serif; white-space:nowrap; cursor:pointer; }
        #toolbar.ql-simple .ql-action:hover:not(:disabled), #toolbar.ql-simple .ql-action:focus-visible { background:var(--ql-hover); outline:none; }
        #toolbar.ql-simple .ql-action[aria-pressed="true"] { background:var(--ql-selected); color:var(--text-normal-pressed,var(--ql-ink)); }
        #toolbar.ql-simple .ql-action:disabled { opacity:.36; cursor:default; }
        #toolbar.ql-simple .ql-action svg { width:22px; height:22px; display:block; flex:none; }
        #toolbar.ql-simple .ql-action .ql-letter { height:22px; font:bold 22px/22px Georgia,serif; }
        #toolbar.ql-simple .ql-action .ql-letter.ql-italic { font-style:italic; }
        #toolbar.ql-simple .ql-action .ql-letter.ql-under { text-decoration:underline; text-underline-offset:4px; }
        #toolbar.ql-simple .ql-action.ql-wide { min-width:68px; }
        #toolbar.ql-simple .ql-action.ql-more { min-width:60px; }
        #toolbar.ql-simple .ql-combo { display:flex; flex-direction:column; gap:5px; justify-content:center; height:64px; padding:0 3px; color:var(--ql-muted); font:11px/1 "Microsoft YaHei UI","Segoe UI",sans-serif; }
        #toolbar.ql-simple .ql-combo select { box-sizing:border-box; height:32px; width:132px; padding:0 22px 0 9px; border:1px solid var(--ql-control); border-radius:8px; background:var(--ql-surface); color:var(--ql-ink); font:13px "Microsoft YaHei UI","Segoe UI",sans-serif; cursor:pointer; }
        #toolbar.ql-simple .ql-combo.ql-size select { width:69px; }
        #toolbar.ql-simple .ql-combo select:focus-visible { outline:2px solid var(--ql-focus); outline-offset:1px; }
        #toolbar.ql-simple .ql-combo select:disabled { opacity:.45; cursor:default; }
        #toolbar.ql-simple .ql-back { position:absolute; z-index:1002; top:1px; right:82px; height:25px; border:1px solid var(--ql-control); border-radius:6px; background:var(--ql-hover); color:var(--ql-link); font:12px "Microsoft YaHei UI","Segoe UI",sans-serif; cursor:pointer; display:none; }
        #toolbar.ql-simple.ql-full .ql-back { display:block; }
        .ql-command-shade { position:fixed; inset:0; z-index:2000; background:var(--background-scrim,rgba(23,35,55,.16)); display:flex; align-items:flex-start; justify-content:center; padding:54px 16px 20px; box-sizing:border-box; }
        .ql-command-panel { width:580px; max-width:100%; max-height:calc(100vh - 74px); display:flex; flex-direction:column; background:var(--ql-surface); border:1px solid var(--ql-control); border-radius:16px; box-shadow:0 16px 50px rgba(23,35,55,.2); color:var(--ql-ink); font:14px/1.5 "Microsoft YaHei UI","Segoe UI",sans-serif; overflow:hidden; }
        .ql-command-head { display:flex; align-items:center; padding:16px 20px 10px; gap:12px; }
        .ql-command-head h2 { margin:0; font-size:18px; font-weight:600; flex:1; }
        .ql-command-close { border:0; border-radius:6px; background:var(--ql-hover); padding:3px 10px; font:20px/1.3 sans-serif; cursor:pointer; color:var(--ql-muted); }
        .ql-command-search { box-sizing:border-box; width:calc(100% - 40px); margin:0 20px 10px; padding:11px 13px; border:1px solid var(--ql-control); border-radius:9px; font:14px "Microsoft YaHei UI","Segoe UI",sans-serif; color:var(--ql-ink); background:var(--ql-surface); }
        .ql-command-search:focus { outline:2px solid var(--ql-focus); border-color:var(--ql-focus); }
        .ql-command-list { overflow-y:auto; padding:0 10px 10px; }
        .ql-command-item { display:flex; align-items:center; width:100%; padding:10px; gap:12px; text-align:left; border:0; border-radius:9px; color:var(--ql-ink); background:var(--ql-surface); cursor:pointer; font:14px/1.5 "Microsoft YaHei UI","Segoe UI",sans-serif; }
        .ql-command-item:hover:not(:disabled), .ql-command-item:focus-visible { background:var(--ql-hover); outline:2px solid var(--ql-focus); outline-offset:-2px; }
        .ql-command-item:disabled { opacity:.45; cursor:default; }
        .ql-command-item span { flex:1; }
        .ql-command-item strong { display:block; font-weight:500; }
        .ql-command-item small { display:block; font-size:12px; color:var(--ql-muted); }
        .ql-command-item kbd { font:12px "Segoe UI",sans-serif; color:var(--ql-muted); white-space:nowrap; }
        .ql-command-empty, .ql-command-foot { margin:0; padding:10px 20px; color:var(--ql-muted); font-size:12px; }
        .ql-command-foot { border-top:1px solid var(--ql-divider); background:var(--ql-footer); }
        #toolbar.ql-simple .ql-action, #toolbar.ql-simple .ql-combo select,
        #toolbar.ql-simple .ql-back, .ql-command-close, .ql-command-item {
            transition:box-shadow .14s ease, border-color .14s ease, transform .1s ease;
        }
        #toolbar.ql-simple .ql-action:hover:not(:disabled) { box-shadow:0 1px 5px rgba(0,0,0,.08); }
        #toolbar.ql-simple .ql-action:focus-visible, #toolbar.ql-simple .ql-back:focus-visible,
        .ql-command-close:focus-visible { outline:2px solid var(--ql-focus); outline-offset:2px; }
        #toolbar.ql-simple .ql-action:active:not(:disabled), .ql-command-close:active,
        .ql-command-item:active:not(:disabled) { transform:translateY(1px); }
        .ql-command-shade { animation:ql-backdrop-in .12s ease both; }
        .ql-command-panel { animation:ql-command-in .16s cubic-bezier(.2,.8,.2,1) both; }
        @keyframes ql-backdrop-in { from { opacity:0; } to { opacity:1; } }
        @keyframes ql-command-in { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
        @media (prefers-reduced-motion:reduce) {
            #toolbar.ql-simple .ql-action, #toolbar.ql-simple .ql-combo select,
            #toolbar.ql-simple .ql-back, .ql-command-shade, .ql-command-panel,
            .ql-command-close, .ql-command-item { transition:none; animation:none; transform:none !important; }
        }
    `;
    function icon(name) {
        if (name === 'bold') return '<span class="ql-letter">B</span>';
        if (name === 'italic') return '<span class="ql-letter ql-italic">I</span>';
        if (name === 'underline') return '<span class="ql-letter ql-under">U</span>';
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (paths[name] || paths.more) + '</svg>';
    }
    function install(webapp, native) {
        const root = document.getElementById('toolbar');
        if (!root || root.classList.contains('ql-simple')) return;
        const kind = window.DE ? 'document' : window.SSE ? 'sheet' : window.PE ? 'presentation' : window.PDFE ? 'pdf' : null;
        if (!kind) return;
        const controller = webapp.getController('Toolbar');
        const toolbar = controller && (controller.toolbar || controller.getView('Toolbar') || controller.getView());
        if (!toolbar) return;

        if (!document.getElementById('ql-simple-style')) {
            const css = document.createElement('style');
            css.id = 'ql-simple-style';
            css.textContent = style;
            document.head.appendChild(css);
        }
        const bar = document.createElement('nav');
        bar.className = 'ql-quickbar';
        bar.setAttribute('aria-label', '氢量办公常用操作');
        const scroll = document.createElement('div');
        scroll.className = 'ql-scrollbar';
        const tools = document.createElement('div');
        tools.className = 'ql-tools';
        bar.appendChild(scroll);
        bar.appendChild(tools);
        const back = document.createElement('button');
        back.type = 'button';
        back.className = 'ql-back';
        back.setAttribute('oo_editor_input', 'true');
        back.textContent = '返回简洁';
        const viewportController = webapp.getController('Viewport');
        const layout = viewportController && viewportController.viewport && viewportController.viewport.vlayout;
        const toolbarPanel = layout && layout.getItem('toolbar');
        const fullHeight = toolbarPanel && toolbarPanel.height;
        function setFull(full) {
            root.classList.toggle('ql-full', full);
            document.body.classList.toggle('ql-simple-mode', !full);
            if (toolbarPanel) toolbarPanel.height = full ? fullHeight : 88;
            if (viewportController && viewportController.onLayoutChanged) {
                viewportController.onLayoutChanged('header');
            }
        }
        back.addEventListener('click', function () { setFull(false); });
        const groups = [
            [['file', '文件', null, 'file']],
            [
                ['open', '打开', null, 'open'],
                ['save', '保存', 'btnSave', 'save'],
                ['undo', '撤销', 'btnUndo', 'undo'],
                ['redo', '恢复', 'btnRedo', 'redo'],
                ['paste', '粘贴', 'btnPaste', 'paste']
            ]
        ];
        if (kind === 'document' || kind === 'sheet' || kind === 'presentation') {
            groups.push([
                ['font', '字体', null, 'text', 'home'],
                ['size', '字号', null, 'text', 'home'],
                ['bold', '加粗', 'btnBold', 'bold'],
                ['italic', '斜体', 'btnItalic', 'italic'],
                ['underline', '下划线', 'btnUnderline', 'underline']
            ]);
        }
        if (kind === 'document' || kind === 'sheet') {
            groups.push([
                ['left', '左对齐', 'btnAlignLeft', 'alignleft'],
                ['center', '居中', 'btnAlignCenter', 'aligncenter'],
                ['right', '右对齐', 'btnAlignRight', 'alignright']
            ]);
        }
        if (kind === 'presentation') groups.push([['slide', '新建幻灯片', 'btnAddSlide', 'slide']]);
        if (kind === 'sheet') groups.push([['sort', '升序排列', 'btnSortDown', 'sort']]);
        if (kind === 'pdf') groups.push([
            ['text', '添加文字', 'btnTextComment', 'text'],
            ['highlight', '高亮', 'btnHighlight', 'highlight'],
            ['underline', '下划线', 'btnUnderline', 'underline']
        ]);
        if (kind === 'document' || kind === 'sheet' || kind === 'presentation') groups.push([
            ['image', '图片', null, 'image', 'ins'],
            ['table', '表格', null, 'table', 'ins']
        ]);
        if (kind === 'presentation') groups.push([['slideshow', '开始放映', 'btnPreview', 'play']]);
        groups.push([['commands', '找功能', null, 'search'], ['more', '全部功能', null, 'more', 'full']]);

        function tabNode(tab) {
            return root.querySelector('.box-tabs [data-tab="' + tab + '"]') || root.querySelector('.box-tabs [data-type="' + tab + '"]') || document.getElementById(tab);
        }

        function showFull(tab) {
            setFull(true);
            if (tab && tab !== 'full') {
                const entry = tabNode(tab);
                if (entry) entry.click();
            }
        }
        const main = webapp.getController('Main');
        const left = webapp.getController('LeftMenu');
        let shade = null;
        let commandOpener = null;
        function closeCommands(restoreFocus) {
            if (!shade) return;
            shade.remove();
            shade = null;
            main.api && main.api.asc_enableKeyEvents(true);
            if (restoreFocus && commandOpener) commandOpener.focus();
        }
        function commandItems(filesOnly) {
            const options = main.appOptions || {};
            const canDownload = !!main.api && options.canDownload !== false;
            const menu = left && left.leftMenu && left.leftMenu.menuFile;
            const entries = [
                {id:'open', title:'打开文件', detail:'选择电脑里的文档、表格、演示文稿或 PDF', keys:'Ctrl+O', run:function () { native.execCommand('editor:event', JSON.stringify({action:'file:open'})); }},
                {id:'save', title:'保存', detail:'保存当前文件的修改', keys:'Ctrl+S', enabled:toolbar.btnSave && !toolbar.btnSave.disabled, run:function () { toolbar.btnSave.click(); }},
                {id:'saveas', title:'另存为', detail:'选择新的文件名、位置或格式', keys:'Ctrl+Shift+S', enabled:canDownload, run:function () { main.api.asc_DownloadAs(); }},
                {id:'exportpdf', title:kind === 'pdf' ? '另存 PDF 副本' : '导出 PDF', detail:kind === 'sheet' ? '选择工作表与输出范围，再保存为 PDF' : '选择保存位置，生成便于分享的 PDF 文件', aliases:'转换 格式 pdf', enabled:canDownload && !!menu, run:function () { if (!menu.rendered) menu.render(); left.clickSaveAsFormat(menu, Asc.c_oAscFileType.PDF); }},
                {id:'print', title:'打印与预览', detail:'检查纸张、页面和打印范围', keys:'Ctrl+P', enabled:options.canPrint !== false, run:function () { main.onPrint(); }},
                {id:'find', title:'查找内容', detail:'在当前文件中搜索文字', keys:'Ctrl+F', enabled:!!left, run:function () { left.onShowHideSearch(true); }}
            ];
            if (filesOnly) return entries;
            const catalogs = {
                document: [
                    ['home','文字与段落','字体 字号 加粗 斜体 行距 列表 对齐'],
                    ['ins','插入内容','图片 表格 图表 页码 页眉 页脚 公式 符号'],
                    ['layout','页面排版','纸张 方向 页边距 分栏 分页 分节'],
                    ['links','目录与引用','目录 脚注 尾注 书签 超链接 题注'],
                    ['review','审阅文档','批注 修订 比较 拼写'],
                    ['forms','制作表单','填写 文本框 下拉框 复选框'],
                    ['view','阅读与视图','缩放 标尺 窗口 导航']
                ],
                sheet: [
                    ['home','单元格与样式','字体 数字格式 合并单元格 条件格式 对齐'],
                    ['ins','插入图表与表格','图表 图片 数据透视表 透视 表格'],
                    ['formula','公式与函数','求和 平均值 计数 查找 引用 函数'],
                    ['data','整理数据','排序 筛选 数据验证 重复 分列'],
                    ['layout','打印排版','纸张 方向 页边距 打印区域 缩放'],
                    ['review','检查与批注','批注 拼写'],
                    ['view','工作表视图','冻结 窗格 缩放 网格线']
                ],
                presentation: [
                    ['home','文字与幻灯片','字体 段落 新建 布局 幻灯片'],
                    ['ins','插入对象','图片 表格 图表 视频 音频 形状'],
                    ['design','主题与背景','主题 配色 背景 幻灯片大小'],
                    ['transit','切换效果','切换 过渡 时长 换页'],
                    ['animate','对象动画','动画 顺序 进入 退出'],
                    ['review','检查与批注','批注 拼写'],
                    ['view','演示视图','备注 母版 缩放 视图']
                ],
                pdf: [
                    ['home','PDF 常用工具','选择 文字 页面 旋转'],
                    ['comment','标注与批注','高亮 下划线 批注 文字 画笔'],
                    ['ins','插入内容','图片 文字 页面'],
                    ['forms','表单工具','填写 文本框 下拉框 复选框'],
                    ['red','涂黑敏感内容','涂黑 遮盖 隐私 敏感信息'],
                    ['view','阅读视图','缩放 页面 视图']
                ]
            };
            (catalogs[kind] || []).forEach(function (entry) {
                const node = tabNode(entry[0]);
                if (!node || node.offsetParent === null || node.classList.contains('disabled') || node.getAttribute('aria-disabled') === 'true') return;
                entries.push({id:'tools-' + entry[0], title:entry[1], detail:'打开完整工具栏 · ' + entry[2].split(' ').slice(0,4).join('、'), aliases:entry[2], run:function () { showFull(entry[0]); }});
            });
            if (kind === 'presentation' && toolbar.btnPreview) {
                entries.push({id:'slideshow', title:'从当前页放映', detail:'从正在编辑的幻灯片开始播放 · Esc 结束', aliases:'播放 幻灯片 演示 放映', enabled:!toolbar.btnPreview.disabled, run:function () { toolbar.btnPreview.click(); }});
                entries.push({id:'slideshow-first', title:'从头开始放映', detail:'从第一张幻灯片开始播放 · ← → 换页 · Esc 结束', aliases:'播放 幻灯片 演示 放映 首页', enabled:!toolbar.btnPreview.disabled, run:function () { controller.onPreview(0, false, false); }});
            }
            entries.push({id:'all-tools', title:'全部功能', detail:'展开完整工具栏，按选项卡选择专业功能', run:function () { showFull('full'); }});
            return entries;
        }
        function openCommands(filesOnly, opener) {
            if (shade || (Common.Utils.ModalWindow && Common.Utils.ModalWindow.isVisible())) return;
            commandOpener = opener;
            const entries = commandItems(filesOnly);
            shade = document.createElement('div');
            shade.className = 'ql-command-shade';
            const panel = document.createElement('section');
            panel.className = 'ql-command-panel';
            panel.setAttribute('role', 'dialog');
            panel.setAttribute('aria-modal', 'true');
            panel.setAttribute('aria-label', filesOnly ? '文件与输出' : '查找功能');
            panel.innerHTML = '<div class="ql-command-head"><h2>' + (filesOnly ? '文件与输出' : '你想做什么？') + '</h2><button type="button" class="ql-command-close" data-ql-action="close-commands" aria-label="关闭">×</button></div><input class="ql-command-search" type="search" aria-label="搜索功能" placeholder="' + (filesOnly ? '搜索：另存为、PDF、打印…' : '输入功能名，例如：页码、求和、动画…') + '"><div class="ql-command-list"></div><p class="ql-command-foot">↑ ↓ 选择 · Enter 打开 · Esc 返回编辑</p>';
            shade.appendChild(panel);
            document.body.appendChild(shade);
            const input = panel.querySelector('input');
            const list = panel.querySelector('.ql-command-list');
            function render() {
                const query = input.value.trim().toLowerCase().replace(/\s+/g, '');
                list.replaceChildren();
                entries.filter(function (entry) { return (entry.title + entry.detail + (entry.aliases || '')).toLowerCase().replace(/\s+/g, '').includes(query); }).forEach(function (entry) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'ql-command-item';
                    button.dataset.qlAction = entry.id;
                    button.disabled = entry.enabled === false;
                    const text = document.createElement('span');
                    const title = document.createElement('strong');
                    title.textContent = entry.title;
                    const detail = document.createElement('small');
                    detail.textContent = entry.detail;
                    text.append(title, detail);
                    const key = document.createElement('kbd');
                    key.textContent = entry.keys || '›';
                    button.append(text, key);
                    button.addEventListener('click', function () { closeCommands(false); entry.run(); });
                    list.appendChild(button);
                });
                if (!list.children.length) {
                    const empty = document.createElement('p');
                    empty.className = 'ql-command-empty';
                    empty.textContent = '没有找到，可以换个关键词或打开“全部功能”。';
                    list.appendChild(empty);
                }
            }
            panel.querySelector('.ql-command-close').addEventListener('click', function () { closeCommands(true); });
            shade.addEventListener('click', function (event) { if (event.target === shade) closeCommands(true); });
            panel.addEventListener('keydown', function (event) {
                event.stopPropagation();
                if (event.isComposing || event.keyCode === 229) return;
                if (event.ctrlKey && !event.altKey && !event.metaKey) {
                    const key = event.key.toLowerCase();
                    const shortcut = {s:event.shiftKey ? 'saveas' : 'save', o:'open', p:'print', f:'find'}[key];
                    if (shortcut) {
                        event.preventDefault();
                        const command = entries.find(function (entry) { return entry.id === shortcut; });
                        if (command && command.enabled !== false) { closeCommands(false); command.run(); }
                        return;
                    }
                }
                if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeCommands(true); return; }
                const buttons = Array.from(list.querySelectorAll('button:not(:disabled)'));
                if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                    event.preventDefault();
                    const index = buttons.indexOf(document.activeElement);
                    const next = event.key === 'ArrowDown' ? index + 1 : (index <= 0 ? buttons.length - 1 : index - 1);
                    if (buttons.length) buttons[(next + buttons.length) % buttons.length].focus();
                } else if (event.key === 'Enter' && document.activeElement === input) {
                    event.preventDefault();
                    if (buttons.length) buttons[0].click();
                } else if (event.key === 'Tab') {
                    const focusable = Array.from(panel.querySelectorAll('button:not(:disabled), input'));
                    const first = focusable[0], last = focusable[focusable.length-1];
                    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
                }
            });
            input.addEventListener('input', render);
            main.api && main.api.asc_enableKeyEvents(false);
            render();
            input.focus();
        }
        function actionModel(key) {
            // The current spreadsheet toolbar creates sorting buttons in DataTab, after initial render.
            const models = toolbar[key] || (key === 'btnSortDown' && toolbar.btnsSortDown);
            // injectButtons returns an array-like collection, not a native Array.
            const candidates = models && typeof models.click !== 'function' && typeof models.length === 'number' ? Array.from(models) : [models];
            const valid = function (model) { return model && typeof model.click === 'function'; };
            return candidates.find(function (model) { return valid(model) && !model.disabled; }) || candidates.find(valid);
        }
        const tracked = [];
        const combos = [];
        function makeCombo(item) {
            const isFont = item[0] === 'font';
            const label = document.createElement('label');
            label.className = 'ql-combo' + (isFont ? ' ql-font' : ' ql-size');
            const caption = document.createElement('span');
            caption.textContent = item[1];
            const select = document.createElement('select');
            select.dataset.qlAction = item[0];
            select.setAttribute('aria-label', item[1]);
            select.setAttribute('oo_editor_input', 'true');
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = isFont ? '选择文字后设置' : '字号';
            placeholder.disabled = true;
            select.appendChild(placeholder);
            const entry = {modelKey: isFont ? 'cmbFontName' : 'cmbFontSize', model: null,
                select: select, records: [], isFont: isFont};
            select.addEventListener('change', function () {
                const record = entry.records[Number(select.value)];
                if (!record || !entry.model || entry.model.disabled) return;
                entry.model.setValue(isFont ? record.name : record.value);
                entry.model.trigger('selected', entry.model, record);
            });
            label.appendChild(caption);
            label.appendChild(select);
            combos.push(entry);
            return label;
        }
        function refreshCombo(entry) {
            const model = toolbar[entry.modelKey];
            if (!model || !model.store || !model.store.toJSON) return;
            const records = model.store.toJSON().filter(function (record) {
                return entry.isFont ? !!record.name : record.value !== undefined;
            });
            if (!records.length) return;
            if (entry.model === model && entry.records.length === records.length) return;
            entry.model = model;
            entry.records = records;
            entry.select.length = 1;
            records.forEach(function (record, index) {
                const option = document.createElement('option');
                option.value = String(index);
                option.textContent = entry.isFont ? record.name : (record.displayValue || String(record.value));
                entry.select.appendChild(option);
            });
        }
        groups.forEach(function (items) {
            const group = document.createElement('div');
            group.className = 'ql-group';
            items.forEach(function (item) {
                if (item[0] === 'font' || item[0] === 'size') {
                    const combo = makeCombo(item);
                    if (combo) { group.appendChild(combo); return; }
                }
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'ql-action' + (item[1].length > 4 ? ' ql-wide' : '') + (item[0] === 'more' ? ' ql-more' : '');
                // Keep keyboard focus on toolbar controls using the SDK input boundary.
                button.setAttribute('oo_editor_input', 'true');
                button.dataset.qlAction = item[0];
                button.innerHTML = icon(item[3]) + '<span>' + item[1] + '</span>';
                const hints = {file:'另存为、导出 PDF、打印与查找', open:'打开文件 · Ctrl+O', save:'保存 · Ctrl+S', undo:'撤销 · Ctrl+Z', redo:'恢复 · Ctrl+Y', slideshow:'从当前幻灯片开始放映 · ← → 换页 · Esc 结束', commands:'按中文关键词查找常用与专业功能', more:'展开完整工具栏'};
                button.title = hints[item[0]] || item[1];
                if (item[2]) tracked.push([button, item[2], button.title]);
                button.addEventListener('click', function () {
                    if (item[0] === 'file' || item[0] === 'commands') {
                        openCommands(item[0] === 'file', button);
                    } else if (item[0] === 'open') {
                        native.execCommand('editor:event', JSON.stringify({action:'file:open'}));
                    } else if (item[4]) {
                        showFull(item[4]);
                    } else {
                        const model = item[2] && actionModel(item[2]);
                        if (model && !model.disabled) model.click();
                    }
                });
                group.appendChild(button);
            });
            if (items[0][0] === 'file') bar.insertBefore(group, scroll);
            else (items[0][0] === 'commands' || items[0][0] === 'slideshow' ? tools : scroll).appendChild(group);
        });
        root.appendChild(bar);
        root.appendChild(back);
        root.classList.add('ql-simple');
        setFull(false);
        function sync() {
            tracked.forEach(function (pair) {
                const model = actionModel(pair[1]);
                pair[0].disabled = !model || !!model.disabled;
                pair[0].title = model ? pair[2] : '当前编辑器不支持此操作';
                pair[0].setAttribute('aria-pressed', !!model && !!model.pressed);
            });
            combos.forEach(function (entry) {
                refreshCombo(entry);
                entry.select.disabled = !entry.model || !!entry.model.disabled;
                if (document.activeElement === entry.select) return;
                if (!entry.model) return;
                const value = String(entry.model.getValue());
                const index = entry.records.findIndex(function (record) {
                    return String(entry.isFont ? record.name : record.value) === value;
                });
                entry.select.value = index >= 0 ? String(index) : '';
            });
        }
        const source = root.querySelector('.toolbar');
        if (source && window.MutationObserver) {
            const observer = new MutationObserver(sync);
            observer.observe(source, {attributes:true, subtree:true, attributeFilter:['class','disabled','aria-pressed']});
        }
        sync();
        window.setTimeout(sync, 300);
        window.setInterval(sync, 500);
    }
    return {install: install};
});
