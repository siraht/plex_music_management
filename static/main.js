document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.querySelector('#myGrid');

    // Base Column Definitions
    const baseColumnDefs = [
        { 
            field: 'filepath',
            headerName: 'File Path'
        },
        { 
            field: 'artist', 
            headerName: 'Artist', 
            filter: true, 
            resizable: true, 
            sortable: true 
        },
        {
            field: 'album',
            headerName: 'Album',
            filter: true,
            resizable: true,
            sortable: true
        },
        {
            field: 'title',
            headerName: 'Title',
            filter: true,
            resizable: true,
            sortable: true
        },
        {
            field: 'formats',
            headerName: 'Available Formats',
            resizable: true,
            sortable: true,
            valueFormatter: params => params.value ? params.value.join(', ') : '',
            cellRenderer: params => {
                if (params.value) {
                    return params.value.map(format => `<span class="format-tag">${format}</span>`).join(' ');
                }
                return '';
            }
        }
    ];

    const actionColumn = {
        headerName: 'Action',
        field: 'action',
        resizable: false,
        sortable: false,
        cellRenderer: params => {
            const button = document.createElement('button');
            button.innerHTML = 'Apply Tags';
            button.classList.add('btn-apply');
            button.addEventListener('click', () => tagTrack(params));
            params.eGridCell.addEventListener('click', (event) => event.stopPropagation());
            return button;
        }
    };

    // Fetch tags and configure grid
    fetch('/api/tags')
        .then(response => response.json())
        .then(tags => {
            const tagColumnDefs = tags.map(tag => ({
                headerName: tag.name,
                field: tag.name.toLowerCase(),
                resizable: true,
                sortable: true,
                cellRenderer: params => {
                    const input = document.createElement('input');
                    input.type = tag.type || 'text';
                    if (tag.type === 'number') {
                        if (tag.min !== undefined) input.min = tag.min;
                        if (tag.max !== undefined) input.max = tag.max;
                    }
                    input.value = params.value || tag.defaultValue || '';
                    input.classList.add('tag-input-grid');
                    input.dataset.tagName = tag.name.toLowerCase();
                    input.addEventListener('change', (e) => {
                        params.data[tag.name.toLowerCase()] = e.target.value;
                    });
                    return input;
                },
                editable: false
            }));

            const columnDefs = [...baseColumnDefs, ...tagColumnDefs, actionColumn];

            const gridOptions = {
                columnDefs: columnDefs,
                rowData: [],
                rowSelection: 'multiple',
                animateRows: true,
                onGridReady: params => {
                    fetch('/api/files')
                        .then(response => response.json())
                        .then(data => {
                            params.api.setGridOption('rowData', data);
                        });
                },
                defaultColDef: {
                    flex: 1,
                    minWidth: 100,
                    sortable: true,
                    resizable: true,
                    filter: true
                }
            };

            agGrid.createGrid(gridDiv, gridOptions);
        });

    // --- Tag Management Modal --- //
    const modal = document.getElementById('tag-modal');
    const btn = document.getElementById('manage-tags-btn');
    const span = document.getElementsByClassName('close-button')[0];
    const addTagBtn = document.getElementById('add-tag-btn');
    const saveTagsBtn = document.getElementById('save-tags-btn');
    const tagListEditor = document.getElementById('tag-list-editor');

    let currentTags = [];

    // When the user clicks the button, open the modal 
    if (btn) {
        btn.onclick = function() {
            modal.style.display = "block";
            loadTagsForEditing();
        };
    }

    // When the user clicks on (x), close the modal
    if (span) {
        span.onclick = function() {
            modal.style.display = "none";
        };
    }

    // When the user clicks anywhere outside of the modal, close it
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    };

    function loadTagsForEditing() {
        fetch('/api/tags')
            .then(response => response.json())
            .then(tags => {
                currentTags = Array.isArray(tags) ? tags : [];
                renderTagEditors();
            })
            .catch(error => {
                console.error('Error loading tags:', error);
                currentTags = [];
                renderTagEditors();
            });
    }

    function renderTagEditors() {
        if (!tagListEditor) return;
        
        tagListEditor.innerHTML = '';
        currentTags.forEach((tag, index) => {
            const editor = document.createElement('div');
            editor.className = 'tag-editor-form';
            editor.innerHTML = `
                <input type="text" name="name" value="${tag.name || ''}" placeholder="Tag Name">
                <input type="text" name="prefix" value="${tag.prefix || ''}" placeholder="Prefix (e.g., 'E' for -E{value})">
                <select name="type">
                    <option value="text" ${tag.type === 'text' ? 'selected' : ''}>Text</option>
                    <option value="number" ${tag.type === 'number' ? 'selected' : ''}>Number</option>
                </select>
                <input type="text" name="defaultValue" value="${tag.defaultValue || ''}" placeholder="Default Value">
                <div class="number-options" style="display: ${tag.type === 'number' ? 'block' : 'none'}">
                    <input type="number" name="min" value="${tag.min || ''}" placeholder="Min">
                    <input type="number" name="max" value="${tag.max || ''}" placeholder="Max">
                </div>
                <button class="remove-tag-btn" data-index="${index}">Remove</button>
            `;
            tagListEditor.appendChild(editor);

            // Add event listener for type change
            const typeSelect = editor.querySelector('select[name="type"]');
            if (typeSelect) {
                typeSelect.addEventListener('change', function() {
                    const numberOptions = editor.querySelector('.number-options');
                    if (numberOptions) {
                        numberOptions.style.display = this.value === 'number' ? 'block' : 'none';
                    }
                });
            }
        });

        // Add event listeners for remove buttons
        document.querySelectorAll('.remove-tag-btn').forEach(button => {
            button.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'), 10);
                if (!isNaN(index) && index >= 0 && index < currentTags.length) {
                    currentTags.splice(index, 1);
                    renderTagEditors();
                }
            });
        });
    }

    // Add new tag
    if (addTagBtn) {
        addTagBtn.onclick = function() {
            currentTags.push({
                name: 'New Tag',
                prefix: '',
                type: 'text',
                defaultValue: ''
            });
            renderTagEditors();
        };
    }

    // Save tags
    if (saveTagsBtn) {
        saveTagsBtn.onclick = function() {
            const tagForms = document.querySelectorAll('.tag-editor-form');
            const updatedTags = [];
            
            tagForms.forEach(form => {
                const nameInput = form.querySelector('input[name="name"]');
                const prefixInput = form.querySelector('input[name="prefix"]');
                const typeSelect = form.querySelector('select[name="type"]');
                const defaultValueInput = form.querySelector('input[name="defaultValue"]');
                
                if (nameInput && typeSelect && defaultValueInput) {
                    const tag = {
                        name: nameInput.value.trim(),
                        prefix: (prefixInput?.value || '').trim(),
                        type: typeSelect.value,
                        defaultValue: defaultValueInput.value
                    };

                    if (tag.name) {  // Only add if name is not empty
                        if (tag.type === 'number') {
                            const minInput = form.querySelector('input[name="min"]');
                            const maxInput = form.querySelector('input[name="max"]');
                            if (minInput && minInput.value) tag.min = parseInt(minInput.value, 10);
                            if (maxInput && maxInput.value) tag.max = parseInt(maxInput.value, 10);
                        }
                        updatedTags.push(tag);
                    }
                }
            });

            // Send to server
            fetch('/api/tags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updatedTags),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    modal.style.display = "none";
                    location.reload(); // Reload to update the grid with new tags
                } else {
                    alert('Error saving tags: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error saving tags:', error);
                alert('Failed to save tags. Check console for details.');
            });
        };
    }
});

function tagTrack(params) {
    const node = params.node;
    const groupKey = node.data.group_key;
    const button = params.eGridCell.querySelector('button');
    const originalText = button.textContent;

    // Collect all tag values from the row data
    const tagsToApply = {};
    const tagInputs = params.eGridCell.parentElement.querySelectorAll('.tag-input-grid');
    
    // This is a bit of a workaround to get the tag definitions. A better way would be to have them globally accessible.
    fetch('/api/tags')
        .then(response => response.json())
        .then(tagDefinitions => {
            tagDefinitions.forEach(tagDef => {
                const tagName = tagDef.name.toLowerCase();
                if (node.data[tagName] !== undefined) {
                    tagsToApply[tagName] = node.data[tagName];
                }
            });

            // Basic validation
            let isValid = true;
            for (const [key, value] of Object.entries(tagsToApply)) {
                if (value === null || value === '') {
                    // Allow empty tags for now, can be tightened later
                }
            }

            if (!isValid) {
                alert('Please ensure all tag fields are filled correctly.');
                return;
            }

            button.disabled = true;
            button.textContent = 'Processing...';
            button.classList.add('processing');

            fetch('/api/tag', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    group_key: groupKey,
                    tags: tagsToApply
                })
            })
            .then(response => response.ok ? response.json() : Promise.reject('Network response was not ok'))
            .then(data => {
                if (data.status === 'success') {
                    button.textContent = '✓ Done';
                    button.classList.remove('btn-apply');
                    button.classList.add('btn-success');
                    // Optionally disable all inputs in the row
                    tagInputs.forEach(input => input.disabled = true);
                } else {
                    throw new Error(data.message || 'Unknown error occurred');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error: ' + (error.message || 'Failed to apply tags'));
                button.disabled = false;
                button.textContent = originalText;
                button.classList.remove('processing');
            });
        });
}
