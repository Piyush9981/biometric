// History page timezone formatting and PDF generation
document.addEventListener('DOMContentLoaded', () => {
    const tbody = document.getElementById('history-tbody');
    const searchInput = document.getElementById('history-search');
    const statusFilter = document.getElementById('status-filter');
    const btnDownloadAll = document.getElementById('btn-download-all');

    let historyData = [];
    let filteredData = [];

    // Base64 string for logo will be loaded asynchronously
    let logoBase64 = null;

    // Helper to fetch image and convert to base64
    function getBase64ImageFromURL(url) {
        return new Promise((resolve, reject) => {
            var img = new Image();
            img.crossOrigin = "Anonymous";
            img.onload = () => {
                var canvas = document.createElement("canvas");
                canvas.width = img.width;
                canvas.height = img.height;
                var ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0);
                var dataURL = canvas.toDataURL("image/jpeg");
                resolve(dataURL);
            };
            img.onerror = error => reject(error);
            img.src = url;
        });
    }

    // Preload logo
    getBase64ImageFromURL('/static/images/dsvv_logo.jpg')
        .then(base64 => { logoBase64 = base64; })
        .catch(err => console.error('Failed to load logo for PDF:', err));

    // Fetch history data
    async function fetchHistory() {
        try {
            const response = await fetch('/api/history/', {
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            if (data.success) {
                historyData = data.history;
                applyFilters();
            } else {
                tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Failed to load history</td></tr>';
            }
        } catch (error) {
            console.error('Error fetching history:', error);
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-danger">Network error</td></tr>';
        }
    }

    function renderTable() {
        tbody.innerHTML = '';
        if (filteredData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="12" class="text-center">No records found</td></tr>';
            return;
        }

        filteredData.forEach(record => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${record.id}</td>
                <td>${record.scholar_id}</td>
                <td>
                    ${record.profile_image 
                        ? `<img src="${record.profile_image}" alt="Profile" style="width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border-color); box-shadow: var(--shadow-sm); display: block; margin: 0 auto;">` 
                        : `<div style="width: 45px; height: 45px; border-radius: 50%; background-color: #e2e8f0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border-color); margin: 0 auto; color: #475569;">
                            <i class="fas fa-user" style="font-size: 1.2rem;"></i>
                           </div>`
                    }
                </td>
                <td>${record.student_name}</td>
                <td>${convertUTCToIST(record.requested_exit_datetime)}</td>
                <td>${convertUTCToIST(record.requested_entry_datetime)}</td>
                <td>${record.actual_exit_datetime ? convertUTCToIST(record.actual_exit_datetime) : '---'}</td>
                <td>${record.actual_entry_datetime ? convertUTCToIST(record.actual_entry_datetime) : '---'}</td>
                <td>${record.outing_reason}</td>
                <td>${record.destination}</td>
                <td>
                    <span class="status-badge status-${record.request_status.toLowerCase().replace(/\s+/g, '-')}">${record.request_status}</span>
                    ${record.timeout_state ? `<div style="font-size: 10px; color: var(--text-muted); margin-top: 4px; font-weight: 500;">${record.timeout_state}</div>` : ''}
                </td>
                <td>
                    <button class="btn-action view-student-history-btn" data-scholar-id="${record.scholar_id}" title="View History">
                        <i class="fas fa-eye" style="color: var(--info);"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Add event listeners to single download buttons
        document.querySelectorAll('.download-single-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                const record = historyData.find(r => r.id == id);
                if (record) generatePDF([record], `Outpass_${record.scholar_id}_${record.requested_exit_datetime.split('T')[0]}`);
            });
        });

        // Add event listeners to view buttons
        document.querySelectorAll('.view-student-history-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const scholarId = e.currentTarget.getAttribute('data-scholar-id');
                openStudentHistoryModal(scholarId);
            });
        });


        // Apply column visibility
        applyHistoryColumnVisibility();
    }

    function applyFilters() {
        const searchTerm = searchInput.value.toLowerCase();
        const statusTerm = statusFilter.value;

        filteredData = historyData.filter(record => {
            const matchesSearch = 
                record.scholar_id.toLowerCase().includes(searchTerm) ||
                record.student_name.toLowerCase().includes(searchTerm) ||
                record.destination.toLowerCase().includes(searchTerm);
            
            let matchesStatus = false;
            if (statusTerm === 'All') {
                matchesStatus = true;
            } else if (statusTerm === 'Time out') {
                const s = record.request_status.toLowerCase();
                matchesStatus = s === 'time out' || s === 'time_out' || s === 'timeout_processed';
            } else {
                matchesStatus = record.request_status === statusTerm;
            }
            
            return matchesSearch && matchesStatus;
        });

        renderTable();
    }



    // Event Listeners
    searchInput.addEventListener('input', applyFilters);
    statusFilter.addEventListener('change', applyFilters);

    // Column Visibility Logic
    function applyHistoryColumnVisibility() {
        const colToggles = document.querySelectorAll('.hist-col-toggle');
        const table = document.getElementById('history-table');
        if (table && colToggles.length > 0) {
            colToggles.forEach(toggle => {
                const colIdx = parseInt(toggle.getAttribute('data-col'));
                const displayStyle = toggle.checked ? '' : 'none';
                
                // Apply to th
                const ths = table.querySelectorAll(`thead tr th:nth-child(${colIdx + 1})`);
                ths.forEach(th => th.style.display = displayStyle);
                
                // Apply to td
                const trs = table.querySelectorAll('tbody tr');
                trs.forEach(tr => {
                    const td = tr.querySelector(`td:nth-child(${colIdx + 1})`);
                    if (td) td.style.display = displayStyle;
                });
            });
        }
    }

    document.querySelectorAll('.hist-col-toggle').forEach(toggle => {
        toggle.addEventListener('change', applyHistoryColumnVisibility);
    });



    // Download Time Period Modal Logic
    const downloadTimeModal = document.getElementById('download-time-modal');
    
    btnDownloadAll.addEventListener('click', () => {
        if (historyData.length === 0) {
            alert('No records to download.');
            return;
        }
        if (downloadTimeModal) {
            downloadTimeModal.classList.remove('hidden');
        } else {
            generatePDF(filteredData, 'All_Outpass_History');
        }
    });

    if (document.getElementById('btn-close-download-modal')) {
        document.getElementById('btn-close-download-modal').addEventListener('click', () => {
            downloadTimeModal.classList.add('hidden');
        });

        document.getElementById('btn-cancel-download').addEventListener('click', () => {
            downloadTimeModal.classList.add('hidden');
        });

        document.getElementById('btn-confirm-download').addEventListener('click', () => {
            const timeValue = document.getElementById('download-time-select').value;
            let cutoffDate = new Date();
            cutoffDate.setHours(0, 0, 0, 0);

            if (timeValue !== 'all_time') {
                switch (timeValue) {
                    case 'today':
                        break;
                    case '1_week':
                        cutoffDate.setDate(cutoffDate.getDate() - 7);
                        break;
                    case '1_month':
                        cutoffDate.setMonth(cutoffDate.getMonth() - 1);
                        break;
                    case '6_months':
                        cutoffDate.setMonth(cutoffDate.getMonth() - 6);
                        break;
                    case '1_year':
                        cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
                        break;
                }
                
                const timeFilteredData = filteredData.filter(record => {
                    const recordDate = new Date(record.requested_exit_datetime);
                    return recordDate >= cutoffDate;
                });
                
                if (timeFilteredData.length === 0) {
                    alert('No records found for the selected time period.');
                } else {
                    generatePDF(timeFilteredData, `Outpass_History_${timeValue}`);
                }
            } else {
                generatePDF(filteredData, 'All_Outpass_History');
            }
            
            downloadTimeModal.classList.add('hidden');
        });
    }

    // Modal logic
    const studentHistoryModal = document.getElementById('student-history-modal');
    
    document.getElementById('btn-close-history-modal').addEventListener('click', () => {
        studentHistoryModal.classList.add('hidden');
    });
    
    document.getElementById('btn-close-history-modal-footer').addEventListener('click', () => {
        studentHistoryModal.classList.add('hidden');
    });

    async function openStudentHistoryModal(scholarId) {
        studentHistoryModal.classList.remove('hidden');
        document.getElementById('modal-student-name').textContent = 'Loading...';
        document.getElementById('modal-history-tbody').innerHTML = '<tr><td colspan="7" class="text-center">Loading...</td></tr>';
        
        try {
            const response = await fetch(`/api/student/${scholarId}/history/`);
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('modal-student-name').textContent = data.student_name;
                document.getElementById('modal-total-requests').textContent = data.stats.total;
                document.getElementById('modal-approved').textContent = data.stats.approved;
                document.getElementById('modal-pending').textContent = data.stats.pending;
                document.getElementById('modal-rejected').textContent = data.stats.rejected;
                
                const tbody = document.getElementById('modal-history-tbody');
                tbody.innerHTML = '';
                
                if (data.history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center">No history found.</td></tr>';
                } else {
                    data.history.forEach(item => {
                        const displayExit = convertUTCToIST(item.requested_exit_datetime);
                        const displayEntry = convertUTCToIST(item.requested_entry_datetime);
                        const displayActualExit = convertUTCToIST(item.actual_exit_datetime);
                        const displayActualEntry = convertUTCToIST(item.actual_entry_datetime);
                        
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><span class="td-val">${displayExit}</span></td>
                            <td><span class="td-val">${displayEntry}</span></td>
                            <td>
                                <span class="td-val text-right">
                                    OUT: ${displayActualExit}<br>
                                    IN: ${item.is_late ? `<span style="color:var(--danger); font-weight:bold;">${displayActualEntry} (Late)</span>` : displayActualEntry}
                                </span>
                            </td>
                            <td><span class="td-val text-right">${item.outing_reason}</span></td>
                            <td><span class="td-val text-right">${item.destination}</span></td>
                            <td>
                                <span class="td-val">
                                    <span class="status-badge status-${item.request_status.toLowerCase().replace(/\s+/g, '-')}">${item.request_status}</span>
                                    ${item.timeout_state ? `<div style="font-size: 10px; color: var(--text-muted); margin-top: 4px; font-weight: 500;">${item.timeout_state}</div>` : ''}
                                </span>
                            </td>
                            <td style="min-width: 280px; padding: 10px;"><span class="td-val text-right">${window.generateLeaveInformationHTML(item.leave_reason, item.parent_confirmed, item.request_status, item.warden_remarks)}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            } else {
                alert('Failed to load student history: ' + data.message);
                studentHistoryModal.classList.add('hidden');
            }
        } catch (err) {
            console.error('Error fetching student history:', err);
            alert('Network error while fetching student history.');
            studentHistoryModal.classList.add('hidden');
        }
    }

    // PDF Generation using jsPDF and jspdf-autotable
    function generatePDF(dataRecords, filename) {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF('landscape'); // Landscape for better table fit

        // Theme colors
        const primaryBlue = [30, 58, 138]; // rgb(30, 58, 138)
        const lightBlue = [239, 246, 255];

        // Add Header
        if (logoBase64) {
            doc.addImage(logoBase64, 'JPEG', 14, 10, 20, 20);
        }
        
        // System Name & College Info
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(22);
        doc.setTextColor(primaryBlue[0], primaryBlue[1], primaryBlue[2]);
        doc.text("Dev Sanskriti Vishwavidyalaya", 40, 20);
        
        doc.setFontSize(14);
        doc.setTextColor(100, 100, 100);
        doc.text("Student Outpass Management System - Outing History", 40, 28);

        // Date generated
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        const generatedDate = convertUTCToIST(new Date().toISOString());
        doc.text(`Generated on: ${generatedDate}`, 14, 38);

        // Prepare table data
        const head = [['Req ID', 'Scholar ID', 'Name', 'Course', 'Sem', 'Req Exit', 'Req Entry', 'Purpose', 'Destination', 'Status']];
        const body = dataRecords.map(r => [
            r.id,
            r.scholar_id,
            r.student_name,
            r.course,
            r.semester,
            convertUTCToIST(r.requested_exit_datetime),
            convertUTCToIST(r.requested_entry_datetime),
            r.outing_reason,
            r.destination,
            r.timeout_state ? `${r.request_status} (${r.timeout_state})` : r.request_status
        ]);

        // Draw Table
        doc.autoTable({
            startY: 45,
            head: head,
            body: body,
            theme: 'grid',
            headStyles: {
                fillColor: primaryBlue,
                textColor: 255,
                fontStyle: 'bold'
            },
            alternateRowStyles: {
                fillColor: lightBlue
            },
            styles: {
                font: 'helvetica',
                fontSize: 9,
                cellPadding: 4
            },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 25 },
                1: { cellWidth: 35 },
                8: { fontStyle: 'bold' }
            },
            didParseCell: function (data) {
                if (data.section === 'body' && (data.column.index === 8 || data.column.index === 9)) {
                    // Color code status column
                    const status = data.cell.raw;
                    if (status && status.includes('IN')) data.cell.styles.textColor = [6, 95, 70]; // success
                    if (status && (status.includes('Time out') || status.includes('TIME_OUT') || status.includes('TIME OUT'))) data.cell.styles.textColor = [100, 116, 139]; // grey
                    if (status && (status.includes('Decline') || status.includes('Reject'))) data.cell.styles.textColor = [153, 27, 27]; // danger
                }
            }
        });

        // Add Footer
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);
            doc.setFontSize(8);
            doc.setTextColor(150);
            doc.text(`Page ${i} of ${pageCount}`, doc.internal.pageSize.width - 20, doc.internal.pageSize.height - 10, { align: 'right' });
            doc.text('Authorized Signatory / Warden', 14, doc.internal.pageSize.height - 10);
        }

        doc.save(`${filename}.pdf`);
    }

    // Initial fetch
    fetchHistory();
});
