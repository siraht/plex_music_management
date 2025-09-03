document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.querySelector('#myGrid');
    let gridApi = null;

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
                    
                    // Use the current tag value from cache or default
                    const currentValue = params.value || tag.defaultValue || '';
                    input.value = currentValue;
                    
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
                    gridApi = params.api;
                    loadFilesIntoGrid();
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

    function loadFilesIntoGrid(forceRefresh = false) {
        const url = forceRefresh ? '/api/files/refresh' : '/api/files';
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (gridApi) {
                    gridApi.setGridOption('rowData', data);
                    showNotification(`Loaded ${data.length} tracks${forceRefresh ? ' (force refreshed)' : ''}`, 'success');
                }
            })
            .catch(error => {
                console.error('Error loading files:', error);
                showNotification('Error loading files', 'error');
            });
    }

    // --- Settings Modal --- //
    const settingsModal = document.getElementById('settings-modal');
    const settingsBtn = document.getElementById('settings-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const cancelSettingsBtn = document.getElementById('cancel-settings-btn');

    // When the user clicks the settings button, open the modal
    if (settingsBtn) {
        settingsBtn.onclick = function() {
            settingsModal.style.display = "block";
            loadSettingsForEditing();
        };
    }

    // Close settings modal
    if (cancelSettingsBtn) {
        cancelSettingsBtn.onclick = function() {
            settingsModal.style.display = "none";
        };
    }

    // Save settings
    if (saveSettingsBtn) {
        saveSettingsBtn.onclick = function() {
            const tagPlacementRadios = document.querySelectorAll('input[name="tag_placement"]');
            let selectedPlacement = 'filename';
            
            tagPlacementRadios.forEach(radio => {
                if (radio.checked) {
                    selectedPlacement = radio.value;
                }
            });

            const settingsData = {
                tag_placement: selectedPlacement,
                version: "1.0"
            };

            // Send to server
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settingsData),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    settingsModal.style.display = "none";
                    showNotification('Settings saved successfully!', 'success');
                    // Refresh the grid to reflect new tag placement settings
                    loadFilesIntoGrid(true);
                } else {
                    alert('Error saving settings: ' + (data.message || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error saving settings:', error);
                alert('Failed to save settings. Check console for details.');
            });
        };
    }

    function loadSettingsForEditing() {
        fetch('/api/settings')
            .then(response => response.json())
            .then(settings => {
                const tagPlacementValue = settings.tag_placement || 'filename';
                const radio = document.querySelector(`input[name="tag_placement"][value="${tagPlacementValue}"]`);
                if (radio) {
                    radio.checked = true;
                }
            })
            .catch(error => {
                console.error('Error loading settings:', error);
                // Default to filename if there's an error
                const defaultRadio = document.querySelector('input[name="tag_placement"][value="filename"]');
                if (defaultRadio) {
                    defaultRadio.checked = true;
                }
            });
    }

    // --- Tag Management Modal --- //
    const modal = document.getElementById('tag-modal');
    const btn = document.getElementById('manage-tags-btn');
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

    // Universal close button handler
    document.addEventListener('click', function(event) {
        if (event.target.classList.contains('close-button')) {
            const modalType = event.target.getAttribute('data-modal');
            if (modalType === 'settings') {
                settingsModal.style.display = "none";
            } else if (modalType === 'tag') {
                modal.style.display = "none";
            }
        }
    });

    // When the user clicks anywhere outside of the modal, close it
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
        if (event.target == settingsModal) {
            settingsModal.style.display = "none";
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
                    showNotification('Tags saved successfully!', 'success');
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

    // Cache management functions
    function refreshFiles() {
        showNotification('Refreshing all files...', 'info');
        loadFilesIntoGrid(true);
    }

    function clearCache() {
        if (confirm('Are you sure you want to clear the cache? This will force a full rescan on the next load.')) {
            fetch('/api/cache/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showNotification('Cache cleared successfully', 'success');
                } else {
                    showNotification('Error clearing cache: ' + (data.message || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error clearing cache:', error);
                showNotification('Failed to clear cache', 'error');
            });
        }
    }

    function showCacheStats() {
        fetch('/api/cache/stats')
            .then(response => response.json())
            .then(data => {
                if (data.total_cached_files !== undefined) {
                    const lastUpdated = data.last_updated ? new Date(data.last_updated * 1000).toLocaleString() : 'Never';
                    const message = `Cache Stats:\n• Total cached files: ${data.total_cached_files}\n• Last updated: ${lastUpdated}\n• Database: ${data.cache_db_path}`;
                    alert(message);
                } else {
                    showNotification('Error getting cache stats: ' + (data.message || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error getting cache stats:', error);
                showNotification('Failed to get cache stats', 'error');
            });
    }

    // Cache management functions (moved outside DOMContentLoaded)
    window.refreshFiles = function() {
        showNotification('Refreshing all files...', 'info');
        loadFilesIntoGrid(true);
    };

    window.clearCache = function() {
        if (confirm('Are you sure you want to clear the cache? This will force a full rescan on the next load.')) {
            fetch('/api/cache/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showNotification('Cache cleared successfully', 'success');
                } else {
                    showNotification('Error clearing cache: ' + (data.message || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error clearing cache:', error);
                showNotification('Failed to clear cache', 'error');
            });
        }
    };

    window.showCacheStats = function() {
        fetch('/api/cache/stats')
            .then(response => response.json())
            .then(data => {
                if (data.total_cached_files !== undefined) {
                    const lastUpdated = data.last_updated ? new Date(data.last_updated * 1000).toLocaleString() : 'Never';
                    const message = `Cache Stats:\n• Total cached files: ${data.total_cached_files}\n• Last updated: ${lastUpdated}\n• Database: ${data.cache_db_path}`;
                    alert(message);
                } else {
                    showNotification('Error getting cache stats: ' + (data.message || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error getting cache stats:', error);
                showNotification('Failed to get cache stats', 'error');
            });
    };

    // Notification function for user feedback
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        const bgColors = {
            success: '#4caf50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196f3'
        };
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: ${bgColors[type] || bgColors.info};
            color: white;
            padding: 15px 20px;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1001;
            opacity: 0;
            transform: translateY(-20px);
            transition: all 0.3s ease;
            max-width: 400px;
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        }, 10);
        
        // Remove after 4 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 4000);
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
            }
        }
    });
});

function tagTrack(params) {
    const node = params.node;
    const groupKey = node.data.group_key;
    const button = params.eGridCell.querySelector('button');
    const originalText = button.textContent;

    // Collect all tag values from the row data
    const tagsToApply = {};
    
    // Get tag definitions to know what tags to collect
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
                    
                    // Update the row data with the applied tags
                    Object.assign(node.data, tagsToApply);
                    
                    // Optionally disable all inputs in the row
                    const tagInputs = params.eGridCell.parentElement.querySelectorAll('.tag-input-grid');
                    tagInputs.forEach(input => input.disabled = true);
                    
                    showNotification(`Successfully tagged ${node.data.filename}`, 'success');
                } else {
                    throw new Error(data.message || 'Unknown error occurred');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error: ' + (error.message || 'Failed to apply tags'), 'error');
                button.disabled = false;
                button.textContent = originalText;
                button.classList.remove('processing');
            });
        })
        .catch(error => {
            console.error('Error loading tag definitions:', error);
            showNotification('Error loading tag definitions', 'error');
            button.disabled = false;
            button.textContent = originalText;
            button.classList.remove('processing');
        });
}
