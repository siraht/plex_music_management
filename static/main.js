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
            field: 'filename_length',
            headerName: 'Filename Length',
            resizable: true,
            sortable: true,
            width: 150,
            cellRenderer: params => {
                const length = params.value || 0;
                const hasWarning = params.data.has_filename_warning;
                
                let className = 'filename-length';
                let icon = '';
                
                if (hasWarning) {
                    className += ' filename-warning';
                    icon = '⚠️ ';
                    if (length > 265) {
                        className += ' filename-critical';
                        icon = '🔴 ';
                    }
                } else if (length > 240) {
                    className += ' filename-caution';
                    icon = '⚡ ';
                }
                
                return `<span class="${className}" title="${hasWarning ? 'Filename too long for CDJ compatibility' : 'Filename length OK'}">${icon}${length}</span>`;
            }
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
            
            // Add warning class if filename is problematic
            if (params.data.has_filename_warning) {
                button.classList.add('btn-caution');
                button.title = 'Warning: This file has a long filename that may not be compatible with CDJs';
            }
            
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
                        // Validate filename length as user types
                        validateFilenameLength(params);
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

    function validateFilenameLength(params) {
        // Get all tag values for this row
        const tags = {};
        const tagInputs = params.eGridCell.parentElement.querySelectorAll('.tag-input-grid');
        tagInputs.forEach(input => {
            tags[input.dataset.tagName] = input.value;
        });

        // Get the first file from the group to validate
        const groupKey = params.data.group_key;
        
        // Make a validation request
        fetch('/api/validate-filename', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_path: groupKey + '.flac', // Use group key as base
                tags: tags
            })
        })
        .then(response => response.json())
        .then(data => {
            const button = params.eGridCell.parentElement.querySelector('.btn-apply');
            if (button) {
                if (!data.is_valid) {
                    button.classList.add('btn-caution');
                    button.title = data.message + (data.suggested_filename ? `\nSuggested: ${data.suggested_filename}` : '');
                } else {
                    button.classList.remove('btn-caution');
                    button.title = 'Apply tags to this track';
                }
            }
        })
        .catch(error => {
            console.warn('Error validating filename:', error);
        });
    }

    function loadFilesIntoGrid(forceRefresh = false) {
        const url = forceRefresh ? '/api/files/refresh' : '/api/files';
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (gridApi) {
                    gridApi.setGridOption('rowData', data);
                    
                    // Count filename warnings
                    const warningCount = data.filter(item => item.has_filename_warning).length;
                    const totalFiles = data.length;
                    
                    let message = `Loaded ${totalFiles} tracks${forceRefresh ? ' (force refreshed)' : ''}`;
                    if (warningCount > 0) {
                        message += ` - ${warningCount} files have long filenames ⚠️`;
                        showNotification(message, 'warning');
                    } else {
                        showNotification(message, 'success');
                    }
                }
            })
            .catch(error => {
                console.error('Error loading files:', error);
                showNotification('Error loading files', 'error');
            });
    }

    function showFilenameWarnings() {
        fetch('/api/files/filename-warnings')
            .then(response => response.json())
            .then(data => {
                const warnings = data.warnings || [];
                const stats = data.stats || {};
                
                if (warnings.length === 0) {
                    alert('No filename length warnings found. All files are CDJ-compatible!');
                    return;
                }
                
                // Create detailed warning message
                let message = `CDJ Filename Compatibility Report:\n\n`;
                message += `📊 Summary:\n`;
                message += `• Total files: ${stats.total_files || 0}\n`;
                message += `• Valid filenames: ${stats.valid_files || 0}\n`;
                message += `• Warning files: ${stats.warning_files || 0}\n`;
                message += `• Critical files: ${stats.critical_files || 0}\n\n`;
                
                if (warnings.length > 0) {
                    message += `🔴 First ${Math.min(5, warnings.length)} problematic files:\n`;
                    warnings.slice(0, 5).forEach(warning => {
                        message += `• ${warning.filename.substring(0, 60)}${warning.filename.length > 60 ? '...' : ''}\n`;
                        message += `  Length: ${warning.length} chars (${warning.excess_chars} over limit)\n\n`;
                    });
                    
                    if (warnings.length > 5) {
                        message += `... and ${warnings.length - 5} more files\n\n`;
                    }
                    
                    message += `💡 Tip: Consider shortening artist/album names or using abbreviations to ensure CDJ compatibility.`;
                }
                
                alert(message);
            })
            .catch(error => {
                console.error('Error getting filename warnings:', error);
                showNotification('Failed to get filename warnings', 'error');
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
                    const fileStats = data.filename_stats || {};
                    
                    let message = `Cache Stats:\n• Total cached files: ${data.total_cached_files}\n• Last updated: ${lastUpdated}\n• Database: ${data.cache_db_path}`;
                    
                    if (fileStats.total_files) {
                        message += `\n\nFilename Compatibility:\n• Valid filenames: ${fileStats.valid_files || 0}\n• Warning files: ${fileStats.warning_files || 0}\n• Critical files: ${fileStats.critical_files || 0}`;
                    }
                    
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

    window.showFilenameWarnings = showFilenameWarnings;

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
                case 'r':
                    e.preventDefault();
                    refreshFiles();
                    break;
                case 'w':
                    e.preventDefault();
                    showFilenameWarnings();
                    break;
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
            .then(response => response.json())
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
                } else if (data.status === 'error' && data.validation_errors) {
                    // Handle filename validation errors
                    let errorMessage = data.message + ':\n\n';
                    data.validation_errors.forEach(error => {
                        errorMessage += `• ${error.file}: ${error.message}\n`;
                        if (error.suggested) {
                            errorMessage += `  Suggested: ${error.suggested}\n`;
                        }
                    });
                    errorMessage += '\n💡 Consider shortening the filename or using metadata-only tag placement.';
                    alert(errorMessage);
                } else {
                    throw new Error(data.message || 'Unknown error occurred');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error: ' + (error.message || 'Failed to apply tags'), 'error');
            })
            .finally(() => {
                button.disabled = false;
                if (button.textContent === 'Processing...') {
                    button.textContent = originalText;
                }
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
