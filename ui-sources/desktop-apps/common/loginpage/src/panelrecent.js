/*
 * (c) Copyright Ascensio System SIA 2010-2019
 *
 * This program is a free software product. You can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public License (AGPL)
 * version 3 as published by the Free Software Foundation. In accordance with
 * Section 7(a) of the GNU AGPL its Section 15 shall be amended to the effect
 * that Ascensio System SIA expressly excludes the warranty of non-infringement
 * of any third-party rights.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the implied
 * warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR  PURPOSE. For
 * details, see the GNU AGPL at: http://www.gnu.org/licenses/agpl-3.0.html
 *
 * You can contact Ascensio System SIA at 20A-12 Ernesta Birznieka-Upisha
 * street, Riga, Latvia, EU, LV-1050.
 *
 * The  interactive user interfaces in modified source and object code versions
 * of the Program must display Appropriate Legal Notices, as required under
 * Section 5 of the GNU AGPL version 3.
 *
 * Pursuant to Section 7(b) of the License you must retain the original Product
 * logo when distributing the program. Pursuant to Section 7(e) we decline to
 * grant you any rights under trademark law for use of our trademarks.
 *
 * All the Product's GUI elements, including illustrations and icon sets, as
 * well as technical writing content are licensed under the terms of the
 * Creative Commons Attribution-ShareAlike 4.0 International. See the License
 * terms at http://creativecommons.org/licenses/by-sa/4.0/legalcode
 *
*/


/*
*   new inherited controller declaration
*   panel 'recent'
*/

// Qingliang community, 2026-10-23: searchable, keyboard accessible workbench.
+function () {
    'use strict'
    var ControllerRecent = function (args = {}) {
        args.caption = 'Recent files';
        args.action =
            this.action = "recents";
        this.view = new ViewRecent(args);
    };

    ControllerRecent.prototype = Object.create(baseController.prototype);
    ControllerRecent.prototype.constructor = ControllerRecent;
    const isSvgIcons = window.devicePixelRatio >= 2 || window.devicePixelRatio === 1;
    var ViewRecent = function (args) {
        var _lang = utils.Lang;

        // args.id&&(args.id=`"id=${args.id}"`)||(args.id='');

        // localStorage.removeItem('welcome');


        //language=HTML
        args.tplPage = `
            <div class="action-panel ${args.action}">
                <div class="recent-panel-container">
                    <header class="ql-workbench-header">
                        <div><p class="ql-eyebrow" l10n="qlHomeEyebrow">${_lang.qlHomeEyebrow}</p>
                        <h1 l10n="qlHomeTitle">${_lang.qlHomeTitle}</h1>
                        <p class="ql-workbench-description" l10n="qlHomeDescription">${_lang.qlHomeDescription}</p></div>
                        <button type="button" class="ql-open-existing"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h6l2 2h10l-2 11H3zM3 7V4h6l2 3h8v2"/></svg><span l10n="qlOpenFile">${_lang.qlOpenFile}</span></button>
                    </header>
                    <section id="area-document-creation-grid" aria-label="${_lang.qlCreateTitle}"></section>
                    <section id="area-dnd-file" aria-hidden="true"></section>

                    <div id="box-container">
                        <div id="box-recovery">
                            <div class="file-list-title">
                                <h3 l10n>${_lang.listRecoveryTitle}</h3>
                            </div>
                            <div class="file-list-head text-normal">
                                <div class="col-name" l10n>${_lang.colFileName}</div>
                                <div class="col-location" l10n>${_lang.colLocation}</div>
                                <div class="col-date" l10n>${_lang.colLastOpened}</div>
                            </div>
                            <div class="file-list-body scrollable"></div>
                        </div>

                        <div id="box-recent" class="empty" aria-labelledby="ql-recent-title">
                            <div class="file-list-title">
                                <div class="ql-recent-heading"><h2 id="ql-recent-title" l10n>${_lang.qlRecentTitle}</h2><span class="ql-recent-count" role="status" aria-live="polite" aria-atomic="true"></span></div>
                                <button type="button" class="ql-more-recent"><span class="ql-more-label" l10n>${_lang.qlMoreRecent}</span><span aria-hidden="true">›</span></button>
                            </div>
                            <div class="ql-recent-controls">
                                <div class="ql-filter-types" role="group" aria-label="${_lang.qlFilterLabel}">
                                    ${[['all',_lang.qlFilterAll],['word',_lang.newDoc],['cell',_lang.qlTable],['slide',_lang.newPptx],['pdf','PDF'],['pinned',_lang.qlFilterPinned]].map(([key,label]) => `<button type="button" data-filter="${key}" aria-pressed="${key === 'all'}">${label}</button>`).join('')}
                                </div>
                                <div class="ql-recent-search">
                                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>
                                    <input id="idx-recent-filter" type="search" autocomplete="off" spellcheck="false" aria-label="${_lang.qlSearchFiles}" placeholder="${_lang.qlSearchFiles}" aria-controls="ql-recent-files" />
                                    <button type="button" class="ql-clear-search" aria-label="${_lang.qlClearSearch}" hidden>×</button>
                                </div>
                            </div>
                            <div class="file-list-head text-normal">
                                <div class="col-name" l10n>${_lang.colFileName}</div>
                                <div class="col-location" l10n>${_lang.colLocation}</div>
                                <div class="col-date" l10n>${_lang.colLastOpened}</div>
                            </div>
                            <div id="ql-recent-files" class="file-list-body scrollable"></div>
                            <div class="ql-no-results" hidden>
                                <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>
                                <strong l10n="qlNoResults">${_lang.qlNoResults}</strong>
                                <p l10n="qlNoResultsHint">${_lang.qlNoResultsHint}</p>
                                <button type="button" class="ql-reset-filter" l10n="qlResetFilter">${_lang.qlResetFilter}</button>
                            </div>
                            <div class="ql-recent-empty">
                                <strong l10n>${_lang.qlRecentEmpty}</strong>
                                <p l10n>${_lang.qlRecentEmptyHint}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        args.menu = '.main-column.tool-menu';
        args.field = '.main-column.col-center';
        args.itemindex = 0;
        // args.itemtext = _lang.actRecentFiles;
        args.tplItem = 'nomenuitem';

        baseView.prototype.constructor.call(this, args);
    };

    ViewRecent.prototype = Object.create(baseView.prototype);
    ViewRecent.prototype.constructor = ViewRecent;
    utils.fn.extend(ViewRecent.prototype, {
        render: function () {
            baseView.prototype.render.apply(this, arguments);

            if (!localStorage.getItem('welcome')) {
                localStorage.setItem('welcome', '0');
            }

            this.$boxRecovery = this.$panel.find('#box-recovery');
            this.$boxRecent = this.$panel.find('#box-recent');
            this.$panelContainer = this.$panel.find('.recent-panel-container');
        },
        listitemtemplate: function (info) {
            const escapeText = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[ch]);
            let id = !!info.uid ? (` id="${info.uid}"`) : '';
            info.crypted === undefined && (info.crypted = false);
            const dotIndex = info.name.lastIndexOf('.');
            const fullName = info.name;
            const extension = dotIndex !== -1 ? info.name.substring(dotIndex) : '';
            const displayName = dotIndex !== -1 ? info.name.substring(0, dotIndex) : info.name;
            const safeName = escapeText(displayName);
            const safeExt = escapeText(extension);
            const safeFullName = escapeText(fullName);
            const safeDescription = escapeText(info.descr);
            const safeDate = escapeText(info.date);

            // todo: crypted icon

            //language=HTML
            let _tpl = `
                <div ${id} class="row text-normal">
                    <div class="col-name" role="button" tabindex="0" aria-label="${safeFullName}" title="${safeFullName}">
                        <div class="icon">
                            <svg class="icon" data-iconname="${info.type === 'folder' ? 'folder' : `${info.format}`}"
                                 data-precls="tool-icon">
                                <use xlink:href="#${info.type === 'folder' ? 'folder-small' : info.format}"></use>
                            </svg>
                            ${info.crypted ? `<svg class="icon shield" data-iconname="shield" data-precls="tool-icon">
                                                <use xlink:href="#shield"></use>
                                              </svg>` : ''}
                            ${!isSvgIcons ? `<i class="icon ${info.type === 'folder' ? 'img-el folder' : `img-format ${info.format}`}"></i>` : ''}
                            ${info.crypted && !isSvgIcons ? `<i class="icon img-el shield"></i>` : ''}
                        </div>
                        <p class="name">
                            ${safeName}<span class="ext">${safeExt}</span>
                        </p>
                    </div>
                    <div class="col-location" title="${safeDescription}">
                        <!--              todo: icon here          -->
                        ${safeDescription}
                    </div>
            `;

            //language=HTML
            _tpl += `
                <div class="col-pin">
                    <button type="button" id="${info.uid}-pin-btn" class="btn-quick" aria-pressed="${!!info.pinned}" aria-label="${escapeText(info.pinned ? utils.Lang.menuFileUnpin : utils.Lang.menuFilePin)}">
                        <svg class="icon">
                            <use xlink:href="#pin"/>
                        </svg>
                        ${!isSvgIcons ? '<i class="icon tool-icon pin"></i>' : ''}
                    </button>
                </div>`;

            if (info.type !== 'folder') {
                //language=HTML
                _tpl += `
                    <div class="col-date"><p>${safeDate}</p></div>`;

                //language=HTML
                _tpl += `
                    <div class="col-more">
                        <button type="button" id="${info.uid}-more-btn" class="btn-quick more" aria-label="${escapeText(utils.Lang.qlFileActions)}" aria-haspopup="menu">
                            <svg class="icon">
                                <use xlink:href="#more"/>
                            </svg>
                            ${!isSvgIcons ? '<i class="icon tool-icon more"></i>' : ''}
                        </button>
                    </div>`;
            }

            return _tpl + '</div>';
        },
        onscale: function (pasteSvg) {
            let elm, icoName, parent,
                emptylist = $('[class*="text-emptylist"]', '#box-recent');
            emptylist.toggleClass('text-emptylist text-emptylist-svg');

            if (pasteSvg && !emptylist.find('svg').length)
                emptylist.prepend($('<svg class = "icon"><use xlink:href="#folder-big"></use></svg>'));

            // todo: rewrite cicon rescale

            $('#box-recent .row.text-normal').each(function () {
                let elm = $(this);
                let iconContainer = elm.find('.col-name .icon').first();
                let svgElem = iconContainer.find('svg.icon').first();

                if (pasteSvg || !svgElem.length || iconContainer.find('i.icon').length) return;

                let icoName = svgElem.attr('data-iconname');
                iconContainer.append(`<i class="icon img-format ${icoName}"></i>`);

                if (iconContainer.find('.icon.shield').length) {
                    iconContainer.append(`<i class="icon img-el shield"></i>`);
                }
            });

            $('.open-panel-container .row.text-normal').each(function () {
                let elm = $(this);
                let iconContainer = elm.find('.col-name .icon').first();
                let svgElem = iconContainer.find('svg.icon').first();

                if (pasteSvg || !svgElem.length || iconContainer.find('i.icon').length) return;

                iconContainer.append(`<i class="icon img-el folder"></i>`);

                if (iconContainer.find('.icon.shield').length) {
                    iconContainer.append(`<i class="icon img-el shield"></i>`);
                }
            });

            $('.col-more .btn-quick.more').each(function () {
                let btn = $(this);
                let svgElem = btn.find('svg.icon').first();

                if (pasteSvg || !svgElem.length || btn.find('i.icon').length) return;

                btn.append(`<i class="icon tool-icon more"></i>`);
            });
        },
        updateListSize: function () {
            const windowBottom = $(window).height();

            // Recovery
            const $headRecovery = this.$boxRecovery.find('.file-list-head');
            const $bodyRecovery = this.$boxRecovery.find('.file-list-body');

            if ($headRecovery.length && $bodyRecovery.length) {
                const headBottomRecovery = $headRecovery.offset().top + $headRecovery.outerHeight(true);
                const availableRecovery = windowBottom - headBottomRecovery - 20;

                $bodyRecovery.css({ 'max-height': availableRecovery > 0 ? availableRecovery + 'px' : '0px' });
            }

            // Recent
            const $headRecent = this.$boxRecent.find('.file-list-head');
            const $bodyRecent = this.$boxRecent.find('.file-list-body');

            if ($headRecent.length && $bodyRecent.length) {
                const headBottomRecent = $headRecent.offset().top + $headRecent.outerHeight(true);
                const availableRecent = windowBottom - headBottomRecent - 20;

                $bodyRecent.css({ 'max-height': availableRecent > 0 ? availableRecent + 'px' : '0px' });
            }
        },
    });

    window.ControllerRecent = ControllerRecent;

    String.prototype.hashCode = function () {
        var hash = 0, i, chr;
        if (this.length === 0) return hash;

        for (i = this.length; !(--i < 0);) {
            chr = this.charCodeAt(i);
            hash = ((hash << 5) - hash) + chr;
            hash = hash & hash; // Convert to 32bit integer
        }

        return hash;
    };

    utils.fn.extend(ControllerRecent.prototype, (function () {
        let collectionRecents, collectionRecovers;
        let ppmenu;
        const ITEMS_LOAD_RANGE = 40;

        const _add_recent_block = function (generation) {
            if (generation !== this.recentGeneration) return;
            if (!this.rawRecents || !Object.keys(this.rawRecents).length) return;

            const _raw_block = this.rawRecents.slice(this.recentIndex, this.recentIndex + ITEMS_LOAD_RANGE);
            const _files = utils.fn.parseRecent(_raw_block);

            let _check_block = {};

            for (let item of _files) {
                var model = new FileModel(item);
                model.set('hash', item.path.hashCode());

                if (!!this.rawRecents) {
                    collectionRecents.add(model);
                    _check_block[model.get('hash')] = item.path;
                } else return;
            }

            const _new_items_count = Object.keys(_check_block).length;
            if (_new_items_count) {
                if (this.appready) {
                    sdk.execCommand('files:check', JSON.stringify(_check_block));
                }

                Object.assign(this.check_list, _check_block);
            }

            this.recentIndex += _raw_block.length;
            if (this.recentIndex < this.rawRecents.length) {
                setTimeout(e => {
                    _add_recent_block.call(this, generation);
                }, 10);
            } else {
                this.rawRecents = undefined;
            }

            // this.view.$boxRecent.css('display', collectionRecents.size() > 0 ? 'flex' : 'none');

            if (collectionRecents.size() > 0 || collectionRecovers.size() > 0) {
                this.dndZone.hide();
                this.view.$panel.find('#area-welcome').hide();
            }
        };

        var _on_recents = function (params) {
            this.rawRecents = undefined;
            const generation = this.recentGeneration = (this.recentGeneration || 0) + 1;

            setTimeout(e => {
                if (generation !== this.recentGeneration) return;
                this.rawRecents = Array.isArray(params) ? params : [];
                this.recentIndex = 0;

                collectionRecents.empty();
                _add_recent_block.call(this, generation);
            }, 10)
        };

        var _on_recovers = function(params) {
            if ( false )
                window.sdk.command("recovery:update", JSON.stringify(params));
            else {
                collectionRecovers.empty();

                var files = utils.fn.parseRecent(params);
                for (let item of files) {
                    collectionRecovers.add( new FileModel(item) );
                }

                this.view.$boxRecovery.css('display', collectionRecovers.size() > 0 ? 'flex' : 'none');
                // requestAnimationFrame(() => this.view.updateListSize());

                if (collectionRecents.size() > 0 || collectionRecovers.size() > 0) {
                    this.dndZone.hide();
                }
            }
        };

        function addContextMenuEventListener(collection, model, view, actionList) {
            $(`#${model.uid}-pin-btn`, view).click((e) => {
                e.stopPropagation();
                const pinned = !model.pinned;
                model.setMany({ pinned: pinned, pinid: pinned ? -model.fileid : model.fileid });
            })

            $(`#${model.uid}-more-btn`, view).click((e) => {
                e.stopPropagation();

                if (ppmenu.contextdata) {
                    const m = ppmenu.contextdata;
                    if (m.uid != model.uid)
                        Menu.closeAll();
                }
                ppmenu.actionlist = actionList;
                if (actionList === 'recovery') {
                    ppmenu.hideItem('files:explore', true);
                    ppmenu.hideItem('files:pin', true);
                    ppmenu.hideItem('files:unpin', true);
                } else {
                    ppmenu.hideItem('files:explore', (!model.islocal && !model.dir) || !model.exist);
                    ppmenu.hideItem(model.pinned ? 'files:pin' : 'files:unpin', true);
                    ppmenu.hideItem(model.pinned ? 'files:unpin' : 'files:pin', false);
                }

                if (!Menu.opened) {
                    ppmenu.showUnderElem(e.currentTarget, model, $('body').hasClass('rtl') ? 'left' : 'right');
                } else {
                    Menu.closeAll();
                }
            })
        }

        function handlePin(collection, model) {
            let $el = $('#' + model.uid, collection.list);
            if (!$el.length) return;

            $el.detach();

            if (model.pinid <= 0) {
                // Pinning: insert after last pinned, or prepend
                const $lastPinned = collection.list.children('.row.pinned').last();
                $lastPinned.length ? $el.insertAfter($lastPinned) : $el.prependTo(collection.list);
                return;
            }

            // Unpinning: restore position among unpinned items
            const modelIndex = collection.items.indexOf(model);
            const items = collection.items;

            // Find nearest unpinned neighbor in DOM to position relative to
            for (let i = modelIndex + 1; i < items.length; i++) {
                if (!items[i].pinned) {
                    let $target = $('#' + items[i].uid, collection.list);
                    if ($target.length) { $el.insertBefore($target); return; }
                }
            }

            for (let i = modelIndex - 1; i >= 0; i--) {
                if (!items[i].pinned) {
                    let $target = $('#' + items[i].uid, collection.list);
                    if ($target.length) { $el.insertAfter($target); return; }
                }
            }

            // No unpinned neighbors found — place after pinned block or at start
            const $lastPinned = collection.list.children('.row.pinned').last();
            $lastPinned.length ? $el.insertAfter($lastPinned) : $el.prependTo(collection.list);
        }

        function _init_collections() {
            let _cl_rcbox = this.view.$boxRecent,
                _cl_rvbox = this.view.$boxRecovery;

            collectionRecents = new Collection({
                view: _cl_rcbox,
                list: _cl_rcbox.find('.file-list-body')
            });

            collectionRecents.events.erased.attach(collection => {
                collection.list.parent().addClass('empty');
                _schedule_recent_filter.call(this);
                this.view.$boxRecent.removeClass('ql-has-more ql-expanded');
                this.view.$boxRecent.find('.ql-more-label').text(utils.Lang.qlMoreRecent);
            });

            collectionRecents.events.inserted.attach((collection, model) => {
                let $item = $(this.view.listitemtemplate(model));

                if (model.pinned) {
                    const $pinned = collection.list.children('.row.pinned');
                    if ($pinned.length) {
                        $item.insertAfter($pinned.last());
                    } else {
                        $item.prependTo(collection.list);
                    }
                } else {
                    collection.list.append($item);
                }

                $item[model.pinned ? 'addClass' : 'removeClass']('pinned');

                addContextMenuEventListener(collection, model, this.view.$panel, 'recent');

                collection.list.parent().removeClass('empty');
                _schedule_recent_filter.call(this);
            });

            collectionRecents.events.click.attach((collection, model) => {
                // var _portal = model.descr;
                // if ( !model.islocal && !app.controller.portals.isConnected(_portal) ) {
                // app.controller.portals.authorizeOn(_portal, {type: 'fileid', id: model.fileid});
                // } else {
                openFile(OPEN_FILE_RECENT, model);
                // }
            });

            collectionRecents.events.contextmenu.attach(function (collection, model, e) {
                ppmenu.actionlist = 'recent';
                ppmenu.hideItem('files:explore', (!model.islocal && !model.dir) || !model.exist);
                ppmenu.hideItem(model.pinned ? 'files:pin' : 'files:unpin', true);
                ppmenu.hideItem(model.pinned ? 'files:unpin' : 'files:pin', false);
                ppmenu.show({left: e.clientX, top: e.clientY}, model);
            });

            collectionRecents.events.changed.attach((collection, model, property) => {
                let $el = collection.list.find('#' + model.uid);
                if ($el) {
                    $el[model.exist ? 'removeClass' : 'addClass']('unavail');
                    if (property['pinned'] !== undefined) {
                        sdk.setRecentFilePinned(model.get('fileid'), property['pinned']);
                        $el[model.pinned ? 'addClass' : 'removeClass']('pinned');
                        $el.find('.col-pin button').attr('aria-pressed', String(!!model.pinned)).attr('aria-label', model.pinned ? utils.Lang.menuFileUnpin : utils.Lang.menuFilePin);
                    }

                    if (property.pinid != undefined) {
                        handlePin(collection, model);
                    }
                }
                _schedule_recent_filter.call(this);
            });

            collectionRecents.empty();

            /**/

            collectionRecovers = new Collection({
                view: _cl_rvbox,
                list: _cl_rvbox.find('.file-list-body')
            });
            collectionRecovers.events.inserted.attach((collection, model) => {
                collection.list.append(this.view.listitemtemplate(model));
                addContextMenuEventListener(collection, model, this.view.$panel, 'recovery');
            });
            collectionRecovers.events.click.attach((collection, model) => {
                openFile(OPEN_FILE_RECOVERY, model);
            });
            collectionRecovers.events.contextmenu.attach((collection, model, e) => {
                ppmenu.actionlist = 'recovery';
                ppmenu.hideItem('files:explore', true);
                ppmenu.hideItem('files:pin', true);
                ppmenu.hideItem('files:unpin', true);
                ppmenu.show({left: e.clientX, top: e.clientY}, model);
            });
        };

        function _init_ppmenu() {
            if (ppmenu) {
                Menu.closeAll();
                $('#pp-menu-files').remove();
                ppmenu = null;
            }

            ppmenu = new Menu({
                id: 'pp-menu-files',
                className: 'with-icons',
                bottomlimitoffset: 10,
                items: [
                    {caption: utils.Lang.menuFileOpen, action: 'files:open', icon: '#folder'},
                    {caption: utils.Lang.menuFilePin, action: 'files:pin', icon: '#pin20'},
                    {caption: utils.Lang.menuFileUnpin, action: 'files:unpin', icon: '#unpin20'},
                    {caption: utils.Lang.menuFileExplore, action: 'files:explore', icon: '#gofolder'},
                    {caption: utils.Lang.menuRemoveModel, action: 'files:forget', icon: '#remove'},
                    {caption: '--'},
                    {caption: utils.Lang.menuClear, action: 'files:clear', variant: 'negative'}
                ]
            });

            ppmenu.init('#placeholder');
            ppmenu.events.itemclick.attach(_on_context_menu.bind(this));
        };

        function _on_context_menu(menu, action, data) {
            if (/\:open/.test(action)) {
                menu.actionlist == 'recent' ?
                    openFile(OPEN_FILE_RECENT, data) :
                    openFile(OPEN_FILE_RECOVERY, data);
            } else if (/\:pin/.test(action)) {
                const targetModel = collectionRecents.find('uid', data.uid);
                if (targetModel) {
                    targetModel.setMany({ pinned: true, pinid: -targetModel.fileid });
                }
            } else if (/\:unpin/.test(action)) {
                const targetModel = collectionRecents.find('uid', data.uid);
                if (targetModel) {
                    targetModel.setMany({ pinned: false, pinid: targetModel.fileid });
                }
            } else if (/\:clear/.test(action)) {
                if (menu.actionlist === 'recent') {
                    window.sdk.LocalFileRemoveAllRecents();
                    if (collectionRecovers.size() === 0) {
                        this.dndZone.show();
                    }
                } else {
                    window.sdk.LocalFileRemoveAllRecovers();
                    if (collectionRecents.size() === 0) {
                        this.dndZone.show();
                    }
                }
            } else if (/\:forget/.test(action)) {
                $('#' + data.uid, this.view.$panel).addClass('lost');

                const count = collectionRecovers.size() + collectionRecents.size();
                if (menu.actionlist === 'recent') {
                    window.sdk.LocalFileRemoveRecent(parseInt(data.fileid));
                } else {
                    window.sdk.LocalFileRemoveRecover(parseInt(data.fileid));
                }

                if ( !(count > 1) ) {
                    this.dndZone.show();
                }
            } else if (/\:explore/.test(action)) {
                if (menu.actionlist == 'recent') {
                    sdk.execCommand('files:explore', JSON.stringify({
                        path: data.path,
                        id: data.fileid,
                        hash: data.hash
                    }));
                }
            }
        };

        function _apply_recent_filter() {
            const $box = this.view.$boxRecent;
            const query = String($box.find('#idx-recent-filter').val() || '').normalize('NFKC').toLowerCase().trim();
            const type = this.recentFilter || 'all';
            const filtering = !!query || type !== 'all';
            const expanded = $box.hasClass('ql-expanded');
            let matches = 0;
            const models = new Map(collectionRecents.items.map(model => [model.uid, model]));
            collectionRecents.list.children('.row').each(function () {
                const model = models.get(this.id);
                if (!model) return;
                const family = (Number(model.type) & 0xffc0);
                const isPdf = model.format === 'pdf' || model.format === 'pdfa' || model.type === 0x57;
                const typeMatch = type === 'all' || (type === 'pinned' && !!model.pinned) ||
                    (type === 'word' && family === 0x40 && !isPdf) || (type === 'cell' && family === 0x100) ||
                    (type === 'slide' && family === 0x80) || (type === 'pdf' && isPdf);
                const text = String(model.path || '').normalize('NFKC').toLowerCase();
                const match = typeMatch && (!query || text.includes(query));
                if (match) matches++;
                const row = document.getElementById(model.uid);
                if (row) row.hidden = !match || (!filtering && !expanded && matches > 4);
            });
            $box.toggleClass('ql-has-more', !filtering && collectionRecents.size() > 4);
            $box.find('.ql-more-recent').attr('aria-expanded', String(expanded));
            $box.find('.ql-more-label').text(expanded ? utils.Lang.qlLessRecent : utils.Lang.qlMoreRecent);
            $box.find('.ql-recent-count').text(utils.Lang.qlResultCount.replace('{count}', matches));
            $box.find('.ql-no-results').prop('hidden', !(filtering && matches === 0));
            $box.find('.ql-recent-empty').prop('hidden', filtering);
            $box.find('.file-list-body').toggleClass('ql-zero-matches', filtering && matches === 0);
            $box.find('.ql-clear-search').prop('hidden', !query);
        }

        function _schedule_recent_filter() {
            if (this.recentFilterFrame) return;
            this.recentFilterFrame = requestAnimationFrame(() => {
                this.recentFilterFrame = 0;
                _apply_recent_filter.call(this);
            });
        }

        function _on_filter_recents() {
            _apply_recent_filter.call(this);
        }


        return {
            init: function () {
                baseController.prototype.init.apply(this, arguments);

                this.view.render();
                this.check_list = {};

                _init_collections.call(this);
                _init_ppmenu.call(this);

                window.sdk.on('onupdaterecents', _on_recents.bind(this));
                window.sdk.on('onupdaterecovers', _on_recovers.bind(this));
                window.sdk.on('on_native_message', (cmd, param) => {
                    if (/files:checked/.test(cmd)) {
                        let fobjs = JSON.parse(param);
                        if (fobjs) {
                            for (let obj in fobjs) {
                                let value = JSON.parse(fobjs[obj]);
                                let model = collectionRecents.find('hash', parseInt(obj));
                                if (model) {
                                    model.get('exist') != value && model.set('exist', value);
                                }
                            }
                        }
                    } else if (/file\:skip/.test(cmd)) {
                        sdk.LocalFileRemoveRecent(parseInt(param));
                    } else if (/app\:ready/.test(cmd)) {
                        if (Object.keys(this.check_list).length) {
                            setTimeout(() => {
                                sdk.execCommand('files:check', JSON.stringify(this.check_list));
                            }, 100);
                        }

                        this.appready = true;
                    }
                });

                CommonEvents.on("icons:svg", this.view.onscale);
                CommonEvents.on('portal:authorized', (data) => {
                    if (data.type == 'fileid') {
                        let fileid = data.id;
                        // openFile(OPEN_FILE_RECENT, fileid);
                    }

                    console.log('portal authorized');
                });


                this.dndZone = new DnDFileZone();
                this.dndZone.render(this.view.$panel.find("#area-dnd-file"));
                this.view.$boxRecent.find('.ql-more-recent').on('click', () => {
                    this.view.$boxRecent.toggleClass('ql-expanded');
                    _apply_recent_filter.call(this);
                });

                const docGrid = new DocumentCreationGrid({
                    documentTypes: [
                        {
                            id: 'word',
                            title: utils.Lang.newDoc,
                            langKey: 'newDoc',
                            description: 'DOCX',
                            formatLabel: {
                                value: 'DOCX',
                                gradientColorStart: '#4298C5',
                                gradientColorEnd: '#2D84B2',
                                bgColorWinXP: '#287ca9',
                            },
                            icon: '#docx-big',
                        },
                        {
                            id: 'cell',
                            title: utils.Lang.qlTable,
                            langKey: 'qlTable',
                            description: 'XLSX',
                            formatLabel: {
                                value: 'XLSX',
                                gradientColorStart: '#5BB514',
                                gradientColorEnd: '#318C2B',
                                bgColorWinXP: '#3aa133',
                            },
                            icon: '#xlsx-big',
                        },
                        {
                            id: 'slide',
                            title: utils.Lang.newPptx,
                            langKey: 'newPptx',
                            description: 'PPTX',
                            formatLabel: {
                                value: 'PPTX',
                                gradientColorStart: '#F4893A',
                                gradientColorEnd: '#DE7341',
                                bgColorWinXP: '#f36700',
                            },
                            icon: '#pptx-big',
                        },
                        {
                            id: 'form',
                            title: utils.Lang.qlPdfForm,
                            langKey: 'qlPdfForm',
                            description: 'PDF',
                            formatLabel: {
                                value: 'PDF',
                                gradientColorStart: '#F36653',
                                gradientColorEnd: '#D2402D',
                                bgColorWinXP: '#e54d39',
                            },
                            icon: '#pdf-big',
                        }
                    ],
                    onDocumentSelect: (docType) => {
                        window.sdk.command("create:new", docType);
                    }
                });

                CommonEvents.on('lang:changed', _init_ppmenu.bind(this));

                docGrid.render(this.view.$panel.find("#area-document-creation-grid"));

                $('#idx-recent-filter', this.view.$panel).on('input', _on_filter_recents.bind(this));
                const $search = this.view.$boxRecent.find('#idx-recent-filter');
                const selectFilter = key => {
                    this.recentFilter = key;
                    this.view.$boxRecent.find('[data-filter]').each(function () {
                        this.setAttribute('aria-pressed', String(this.getAttribute('data-filter') === key));
                    });
                    _apply_recent_filter.call(this);
                };
                this.view.$boxRecent.on('click', '[data-filter]', e => selectFilter(e.currentTarget.getAttribute('data-filter')));
                this.view.$boxRecent.on('click', '.ql-clear-search', () => { $search.val('').trigger('input').focus(); });
                this.view.$boxRecent.on('click', '.ql-reset-filter', () => { $search.val(''); selectFilter('all'); $search.focus(); });
                $search.on('keydown', e => {
                    if (e.key === 'Escape') { e.preventDefault(); $search.val('').trigger('input'); }
                    if (e.key === 'ArrowDown') {
                        const target = this.view.$boxRecent.find('.row:not([hidden]) .col-name').first();
                        if (target.length) { e.preventDefault(); target.focus(); }
                    }
                });
                this.view.$panel.on('keydown', '.col-name[role="button"]', e => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $(e.currentTarget).closest('.row').trigger('click'); }
                });
                $(document).on('keydown.qlRecentSearch', e => {
                    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'f' && this.view.$panel.is(':visible')) {
                        e.preventDefault(); $search.focus().select();
                    }
                });
                this.view.$panel.find('.ql-open-existing').on('click', () => openFile(OPEN_FILE_FOLDER, ''));
                _apply_recent_filter.call(this);
                CommonEvents.on('lang:changed', () => {
                    $search.attr('placeholder', utils.Lang.qlSearchFiles).attr('aria-label', utils.Lang.qlSearchFiles);
                    this.view.$boxRecent.find('.ql-clear-search').attr('aria-label', utils.Lang.qlClearSearch);
                    this.view.$boxRecent.find('.ql-filter-types').attr('aria-label', utils.Lang.qlFilterLabel);
                    const labels = {all: utils.Lang.qlFilterAll, word: utils.Lang.newDoc, cell: utils.Lang.qlTable,
                        slide: utils.Lang.newPptx, pdf: 'PDF', pinned: utils.Lang.qlFilterPinned};
                    this.view.$boxRecent.find('[data-filter]').each(function () { $(this).text(labels[this.getAttribute('data-filter')]); });
                    this.view.$panel.find('.col-more button').attr('aria-label', utils.Lang.qlFileActions);
                    this.view.$panel.find('.col-pin button').each(function () {
                        $(this).attr('aria-label', this.getAttribute('aria-pressed') === 'true' ? utils.Lang.menuFileUnpin : utils.Lang.menuFilePin);
                    });
                    _apply_recent_filter.call(this);
                });

                return this;
            },
            getRecents: function () {
                return collectionRecents;
            },
            getRecovers: function () {
                return collectionRecovers;
            }
        };
    })());
}();

/*
*   controller definition
*/

// window.CommonEvents.on('main:ready', function(){
//     var p = new ControllerRecent({});
//     p.init();
// });
