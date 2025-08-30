document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.querySelector('#myGrid');

    // Column Definitions
    const columnDefs = [
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
        },
        {
            headerName: 'Energy Level',
            field: 'energy',
            resizable: true,
            sortable: true,
            cellRenderer: params => {
                const input = document.createElement('input');
                input.type = 'number';
                input.min = 1;
                input.max = 10;
                input.value = params.value || 7;
                input.classList.add('energy-input-grid');
                input.addEventListener('change', (e) => {
                    params.data.energy = e.target.value;
                });
                return input;
            },
            editable: false
        },
        {
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
        }
    ];

    // Grid Options
    const gridOptions = {
        columnDefs: columnDefs,
        rowData: [],
        rowSelection: 'multiple', // Enable multiple row selection
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

    // Create Grid
    agGrid.createGrid(gridDiv, gridOptions);
});

function tagTrack(params) {
    const node = params.node;
    const groupKey = node.data.group_key;
    const energyLevel = node.data.energy;
    const button = params.eGridCell.querySelector('button');
    const originalText = button.textContent;

    if (!energyLevel || energyLevel < 1 || energyLevel > 10) {
        alert('Please enter a valid energy level between 1 and 10');
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
            energy: energyLevel
        })
    })
    .then(response => response.ok ? response.json() : Promise.reject('Network response was not ok'))
    .then(data => {
        if (data.status === 'success') {
            button.textContent = '✓ Done';
            button.classList.remove('btn-apply');
            button.classList.add('btn-success');
            // Optionally disable the input in the grid cell
            const energyInput = params.eGridCell.parentElement.querySelector('.energy-input-grid');
            if(energyInput) energyInput.disabled = true;
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
}
