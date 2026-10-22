"use strict";

/**
 * Document Creation Grid - Shows cards for creating new documents
 *
 * @param {Object} config
 * @param {Array} config.documentTypes - Document types to show
 * @param {Function} config.onDocumentSelect - Called when user selects a document
 *
 * Document Type Object:
 * - id: unique identifier
 * - title: display name
 * - formatLabel: { value, gradientColorStart, gradientColorEnd }
 * - icon: icon reference (e.g., '#docx-big')
 *
 * @example
 * const docGrid = new DocumentCreationGrid({
 *   documentTypes: [
 *     {
 *       id: 'docx',
 *       title: 'Word Document',
 *       formatLabel: {
 *         value: 'DOCX',
 *         gradientColorStart: '#4298C5',
 *         gradientColorEnd: '#2D84B2'
 *       },
 *       icon: '#docx-big'
 *     }
 *   ],
 *   onDocumentSelect: (docType) => console.log(docType)
 * });
 */
window.DocumentCreationGrid = function (config = {}) {
	const {
		documentTypes = [],
		onDocumentSelect = null
	} = config;


	let $el, $parent;
	const icons = {
		word: '<path d="M8 8h20M8 14h20M8 20h16M8 26h12"/>',
		cell: '<rect x="6" y="6" width="24" height="24" rx="2"/><path d="M6 14h24M6 22h24M14 6v24M22 6v24"/>',
		slide: '<rect x="5" y="7" width="26" height="19" rx="2"/><path d="M18 26v5M11 31h14M10 12h9M10 17h13"/>',
		form: '<path d="M10 4h13l5 5v23H10zM23 4v6h5M14 17h10M14 22h10M14 27h7"/>',
	};

	/** Select through the existing native create command. */
	function handleDocumentSelect(docType, element) {
		const selectedDoc = documentTypes.find(doc => doc.id === docType);

		if (!selectedDoc) {
			console.warn('Document type not found:', docType);
			return;
		}

		if (onDocumentSelect && typeof onDocumentSelect === 'function') {
			onDocumentSelect(docType, selectedDoc, element);
		}
	}

	return {
		/**
		 * Renders the component in the specified parent element
		 * @param {jquery} parentElement - Parent element to render the component in
		 */
		render: (parentElement) => {
			if (!parentElement) {
				throw new Error('Parent element is required for rendering');
			}

			//language=HTML
			const _template = `
                <div class="document-creation-grid">
                    ${documentTypes.map(doc => `
                    <button type="button" class="document-creation-item" data-id="${doc.id}">
                        <span class="ql-card-icon" aria-hidden="true"><svg viewBox="0 0 36 36">${icons[doc.id]}</svg></span>
                        <span class="ql-card-arrow" aria-hidden="true">›</span>
                        <span class="title" l10n="${doc.langKey}">${doc.title}</span>
                        <span class="description">${doc.formatLabel.value}</span>
                    </button>
                `).join('')}
                </div>`;

			$parent = parentElement;
			$el = $parent.append(_template).find('.document-creation-grid');
			$el.on('click', '.document-creation-item', function () {
				handleDocumentSelect(this.getAttribute('data-id'), this);
			});
		},
	};
};
