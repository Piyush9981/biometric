// Real-Time AJAX Polling for Dashboard Components
document.addEventListener('DOMContentLoaded', () => {
    // Determine active dashboard by looking for specific elements in the DOM
    const isWardenOrAdminDashboard = document.getElementById('stat-total-students') !== null;
    const isGatekeeperDashboard = document.getElementById('stat-total-expected') !== null;
    const isBiometricDiagnostics = document.getElementById('machines-container') !== null;

    if (isWardenOrAdminDashboard) {
        // Poll every 3 seconds for Warden / Super Admin Dashboard
        updateWardenDashboard();
        setInterval(updateWardenDashboard, 2000);
    } else if (isGatekeeperDashboard) {
        // Poll every 3 seconds for Gatekeeper Dashboard
        updateGatekeeperDashboard();
        setInterval(updateGatekeeperDashboard, 2000);
    } else if (isBiometricDiagnostics) {
        // Poll every 3 seconds for Biometric Diagnostics
        updateBiometricDiagnostics();
        setInterval(updateBiometricDiagnostics, 3000);
    }

    // Set up delegated event listeners for dynamically updated table rows
    setupEventDelegation();
});

// Helper function to apply saved column visibility settings to newly created table rows
function applyColumnVisibility() {
    const colToggles = document.querySelectorAll('.col-toggle');
    const table = document.getElementById('requests-table');
    if (table && colToggles.length > 0) {
        colToggles.forEach(toggle => {
            const colIdx = parseInt(toggle.getAttribute('data-col'));
            const displayStyle = toggle.checked ? '' : 'none';
            
            // Apply visibility to table header
            const ths = table.querySelectorAll(`thead tr th:nth-child(${colIdx + 1})`);
            ths.forEach(th => th.style.display = displayStyle);
            
            // Apply visibility to cells
            const trs = table.querySelectorAll('tbody tr');
            trs.forEach(tr => {
                const td = tr.querySelector(`td:nth-child(${colIdx + 1})`);
                if (td) td.style.display = displayStyle;
            });
        });
    }
}

// Warden & Super Admin Dashboard Updater
async function updateWardenDashboard() {
    try {
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/dashboard/warden/updates/?_=${timestamp}`, { cache: 'no-store' });
        const data = await response.json();
        if (!data.success) return;

        // 1. Update stats counters
        const stats = data.stats;
        const idMap = {
            'total_students': 'stat-total-students',
            'initial_requests': 'stat-initial-requests',
            'warden_approved_requests': 'stat-warden-approved',
            'registrar_approved_requests': 'stat-registrar-approved',
            'accepted_requests': 'stat-accepted-requests',
            'declined_requests': 'stat-declined-requests',
            'rejected_requests': 'stat-rejected-requests',
            'today_requests': 'stat-today-requests'
        };
        for (const [key, val] of Object.entries(stats)) {
            const el = document.getElementById(idMap[key]);
            if (el) {
                el.textContent = val;
                el.setAttribute('data-target', val);
            }
        }

        // 2. Update table tbody
        const tbody = document.querySelector('#requests-table tbody');
        if (!tbody) return;

        const scrollY = window.scrollY;
        let html = '';

        if (data.requests.length === 0) {
            html = '<tr><td colspan="13" class="text-center">No requests found.</td></tr>';
        } else {
            data.requests.forEach(req => {
                const displayExit = convertUTCToIST(req.requested_exit_datetime);
                const displayEntry = convertUTCToIST(req.requested_entry_datetime);
                const displayActualExit = convertUTCToIST(req.actual_exit_datetime);
                const displayActualEntry = convertUTCToIST(req.actual_entry_datetime);
                const statusClass = req.request_status.toLowerCase().replace(/\s+/g, '-');
                
                let actionsHtml = '';
                if (req.request_status === 'Initiate') {
                    if (data.can_approve) {
                        actionsHtml = `
                            <div style="display: flex; gap: 8px;">
                                <button class="btn-action approve-btn" data-id="${req.request_id}" title="Approve (Default Time)" style="background:#10b981; color:white; border:none; border-radius:6px; padding:4px 8px; cursor:pointer; font-size:12px;"><i class="fas fa-check"></i> Approve</button>
                                <button class="btn-action configure-btn" data-id="${req.request_id}" title="Configure Time" style="background:#3b82f6; color:white; border:none; border-radius:6px; padding:4px 8px; cursor:pointer; font-size:12px;"><i class="fas fa-clock"></i> Configure</button>
                                <button class="btn-action reject-btn" data-id="${req.request_id}" title="Decline" style="background:#ef4444; color:white; border:none; border-radius:6px; padding:4px 8px; cursor:pointer; font-size:12px;"><i class="fas fa-ban"></i> Decline</button>
                            </div>
                        `;
                    } else {
                        actionsHtml = `<span class="action-done" style="color:var(--text-muted);"><i class="fas fa-lock"></i> No Permission</span>`;
                    }
                } else {
                    actionsHtml = `<span class="action-done"><i class="fas fa-check-double"></i></span>`;
                }

                html += `
                    <tr data-status="${req.request_status}">
                        <td class="col-req-id">${req.request_id}</td>
                        <td class="col-scholar-id">${req.student_id}</td>
                        <td class="col-profile">
                            ${req.profile_image 
                                ? `<img src="${req.profile_image}" alt="Profile" style="width: 45px; height: 45px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border-color); box-shadow: var(--shadow-sm); display: block; margin: 0 auto;">` 
                                : `<div style="width: 45px; height: 45px; border-radius: 50%; background-color: #e2e8f0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border-color); margin: 0 auto; color: #475569;">
                                    <i class="fas fa-user" style="font-size: 1.2rem;"></i>
                                   </div>`
                            }
                        </td>
                        <td class="col-student-name">${req.student_name}</td>
                        <td class="col-purpose">${req.outing_reason}</td>
                        <td class="col-destination">${req.destination}</td>
                        <td class="col-exit-time">${displayExit}</td>
                        <td class="col-entry-time">${displayEntry}</td>
                        <td class="col-actual-exit">${displayActualExit}</td>
                        <td class="col-actual-entry">${displayActualEntry}</td>
                        <td class="col-detail">
                            <button type="button" class="btn btn-secondary btn-sm view-req-detail-btn"
                                data-scholar-id="${req.student_id}"
                                data-student-name="${req.student_name}"
                                data-student-mobile="${req.student_mobile}"
                                data-course="${req.course}"
                                data-semester="${req.semester}"
                                data-hostel="${req.hostel_name}"
                                data-purpose="${req.outing_reason}"
                                data-destination="${req.destination}"
                                data-reason="${req.note || 'N/A'}"
                                data-leave-reason="${req.leave_reason || ''}"
                                data-parent-confirmed="${req.parent_confirmed}"
                                data-exit="${req.requested_exit_datetime}"
                                data-entry="${req.requested_entry_datetime}"
                                data-warden="${req.approved_by || 'Pending'}"
                                data-warden-contact="${req.warden_contact}"
                                data-requested-by="${req.requested_by || 'N/A'}"
                                data-profile="${req.profile_image || ''}">
                                <i class="fas fa-eye"></i> View
                            </button>
                        </td>
                        <td class="col-status"><span class="status-badge ${statusClass}">${req.request_status}</span></td>
                        <td class="col-actions">${actionsHtml}</td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = html;
        window.scrollTo(window.scrollX, scrollY);

        // Apply filters & column toggles
        if (window.filterTable) window.filterTable();
        applyColumnVisibility();
    } catch (err) {
        console.error('Warden Polling Error:', err);
    }
}

// Gatekeeper Dashboard Updater
async function updateGatekeeperDashboard() {
    try {
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/dashboard/gatekeeper/updates/?_=${timestamp}`, { cache: 'no-store' });
        const data = await response.json();
        if (!data.success) return;

        // 1. Update stats counters
        const stats = data.stats;
        const idMap = {
            'total_expected': 'stat-total-expected',
            'currently_out': 'stat-currently-out',
            'returned_today': 'stat-returned-today',
            'declined': 'stat-declined'
        };
        for (const [key, val] of Object.entries(stats)) {
            const el = document.getElementById(idMap[key]);
            if (el) {
                el.textContent = val;
                el.setAttribute('data-target', val);
            }
        }

        // 2. Update table tbody
        const tbody = document.querySelector('#requests-table tbody');
        if (!tbody) return;

        const scrollY = window.scrollY;
        let html = '';

        if (data.requests.length === 0) {
            html = '<tr><td colspan="11" class="text-center">No requests found.</td></tr>';
        } else {
            data.requests.forEach(req => {
                const displayExit = convertUTCToIST(req.requested_exit_datetime);
                const displayEntry = convertUTCToIST(req.requested_entry_datetime);
                const displayActualExit = convertUTCToIST(req.actual_exit_datetime);
                const displayActualIn = convertUTCToIST(req.actual_entry_datetime);
                const statusClass = req.request_status.toLowerCase().replace(/\s+/g, '-');
                
                let graceHtml = '';
                if (req.early_grace || req.late_grace) {
                    graceHtml = `
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                            <i class="far fa-clock"></i> Grace: -${req.early_grace}m to +${req.late_grace}m
                        </div>
                    `;
                }

                let actionsHtml = '';
                if (!req.actual_exit_datetime && (req.verification_status === 'READY_FOR_OUT' || req.request_status === 'Accept' || req.request_status === 'ACCEPTED')) {
                    if (data.can_mark_out) {
                        actionsHtml = `
                            <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
                                <button class="btn-action gatekeeper-mark-out-btn" data-id="${req.request_id}" title="Mark OUT" style="background:#1f2937; color:white; border:none; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:4px;">
                                    <i class="fas fa-sign-out-alt"></i> OUT
                                </button>
                                <button class="btn-action gatekeeper-reject-btn" data-id="${req.request_id}" data-type="out" title="Reject Scan" style="background:#dc2626; color:white; border:none; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:4px;">
                                    <i class="fas fa-times-circle"></i> REJECT
                                </button>
                            </div>
                        `;
                    } else {
                        actionsHtml = `<span class="action-done" style="color:var(--text-muted);"><i class="fas fa-lock"></i> No Permission</span>`;
                    }
                } else if (req.actual_exit_datetime && !req.actual_entry_datetime) {
                    if (req.verification_status === 'READY_FOR_IN') {
                        if (data.can_mark_in) {
                            actionsHtml = `
                                <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
                                    <button class="btn-action gatekeeper-mark-in-btn" data-id="${req.request_id}" title="Mark IN" style="background:#1f2937; color:white; border:none; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:4px;">
                                        <i class="fas fa-sign-in-alt"></i> IN
                                    </button>
                                    <button class="btn-action gatekeeper-reject-btn" data-id="${req.request_id}" data-type="in" title="Reject Scan" style="background:#dc2626; color:white; border:none; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:14px; font-weight:bold; display:inline-flex; align-items:center; gap:4px;">
                                        <i class="fas fa-times-circle"></i> REJECT
                                    </button>
                                </div>
                            `;
                        } else {
                            actionsHtml = `<span class="action-done" style="color:var(--text-muted);"><i class="fas fa-lock"></i> No Permission</span>`;
                        }
                    } else {
                        actionsHtml = `
                            <span style="color: #ea580c; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                                <i class="fas fa-fingerprint"></i> Waiting for Biometric Scan
                            </span>
                        `;
                    }
                } else {
                    actionsHtml = `<span style="color: var(--text-muted);font-size:12px;">${req.request_status}</span>`;
                }

                const viewBtnHtml = `
                    <button type="button" class="btn btn-secondary btn-sm view-req-detail-btn"
                        data-request-id="${req.request_id}"
                        data-scholar-id="${req.student_id}"
                        data-student-name="${req.student_name}"
                        data-student-mobile="${req.student_mobile}"
                        data-course="${req.course}"
                        data-semester="${req.semester}"
                        data-hostel="${req.hostel_name}"
                        data-purpose="${req.outing_reason}"
                        data-destination="${req.destination}"
                        data-reason="${req.note || 'N/A'}"
                        data-leave-reason="${req.leave_reason || ''}"
                        data-parent-confirmed="${req.parent_confirmed}"
                        data-exit="${req.requested_exit_datetime}"
                        data-entry="${req.requested_entry_datetime}"
                        data-warden="${req.approved_by || 'Pending'}"
                        data-warden-contact="${req.warden_contact}"
                        data-requested-by="${req.requested_by || 'N/A'}"
                        data-profile="${req.profile_image || ''}">
                        <i class="fas fa-eye"></i> View
                    </button>
                `;

                let profileHtml = '';
                if (req.profile_image) {
                    profileHtml = `<img src="${req.profile_image}" alt="Profile" style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 1px solid var(--border-color); box-shadow: var(--shadow-sm);">`;
                } else {
                    profileHtml = `
                        <div style="width: 48px; height: 48px; border-radius: 50%; background-color: #e2e8f0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--border-color); color: #475569; margin: 0 auto;">
                            <i class="fas fa-user" style="font-size: 1.2rem;"></i>
                        </div>
                    `;
                }

                html += `
                    <tr data-status="${req.request_status}">
                        <td class="col-req-id">${req.request_id}</td>
                        <td class="col-scholar-id">${req.student_id}</td>
                        <td class="col-student-name">
                            <div class="student-profile-container col-profile" style="display: none;">
                                ${profileHtml}
                            </div>
                            ${req.student_name}
                        </td>
                        <td class="col-purpose">${req.outing_reason}</td>
                        <td class="col-destination">${req.destination}</td>
                        <td class="col-exit-time">
                            ${displayExit}
                            ${graceHtml}
                        </td>
                        <td class="col-entry-time">${displayEntry}</td>
                        <td class="col-actual-exit">${displayActualExit}</td>
                        <td class="col-actual-entry">${displayActualIn}</td>
                        <!-- FUTURE DEVELOPER: Uncomment this line to enable the View Detail cell in dynamic updates -->
                        <!-- <td class="col-detail">${viewBtnHtml}</td> -->
                        <td class="col-status"><span class="status-badge ${statusClass}">${req.request_status}</span></td>
                        <td class="col-actions">
                            <div class="actions-wrapper" style="display: flex; gap: 8px; align-items: center;">
                                ${actionsHtml}
                            </div>
                        </td>
                    </tr>
                `;
            });
        }

        tbody.innerHTML = html;
        window.scrollTo(window.scrollX, scrollY);

        // Apply filters & column toggles
        if (window.filterTable) window.filterTable();
        applyColumnVisibility();

        // Check if there is a pending request ID to open
        const params = new URLSearchParams(window.location.search);
        const openReqId = params.get('open_request_id') || window.pendingOpenRequestId;
        if (openReqId) {
            const btn = document.querySelector(`.view-req-detail-btn[data-request-id="${openReqId}"]`);
            if (btn) {
                btn.click();
                window.pendingOpenRequestId = null;
                if (params.has('open_request_id')) {
                    const newUrl = window.location.pathname;
                    window.history.replaceState({}, document.title, newUrl);
                }
            }
        }
    } catch (err) {
        console.error('Gatekeeper Polling Error:', err);
    }
}

// Biometric Diagnostics Updater
async function updateBiometricDiagnostics() {
    try {
        const timestamp = new Date().getTime();
        // 1. Fetch & update registered devices
        const machRes = await fetch(`/api/dashboard/biometric/machines/updates/?_=${timestamp}`, { cache: 'no-store' });
        const machData = await machRes.json();
        if (machData.success) {
            const container = document.getElementById('machines-container');
            if (container) {
                let html = '';
                machData.machines.forEach(m => {
                    const statusClass = m.status === 'ONLINE' ? 'in' : (m.status === 'OFFLINE' ? 'time-out' : 'decline');
                    html += `
                        <div style="background: white; border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s, box-shadow 0.2s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 16px rgba(0,0,0,0.05)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 6px rgba(0,0,0,0.02)';">
                            <div>
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                                    <div>
                                        <h3 style="font-size: 1.1rem; font-weight: 600; color: var(--text-dark); margin: 0;">${m.machine_name}</h3>
                                        <code style="font-size: 0.85rem; color: var(--text-muted); background: #f1f5f9; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px;">${m.ip_address}:${m.port}</code>
                                    </div>
                                    <span class="status-badge ${statusClass}" style="text-transform: uppercase;">
                                        ${m.status || 'UNKNOWN'}
                                    </span>
                                </div>
                                
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; font-size: 0.85rem; border-top: 1px dashed var(--border-color); padding-top: 16px;">
                                    <div>
                                        <span style="color: var(--text-muted); display: block;">Last Connected</span>
                                        <span style="font-weight: 600; color: var(--text-dark);">${convertUTCToIST(m.last_connected)}</span>
                                    </div>
                                    <div>
                                        <span style="color: var(--text-muted); display: block;">Last Synced</span>
                                        <span style="font-weight: 600; color: var(--text-dark);">${convertUTCToIST(m.last_successful_sync)}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div style="margin-top: 20px; display: flex; gap: 8px;">
                                <a href="?test_connection=${m.id}" class="btn btn-secondary" style="flex: 1; font-size: 0.85rem; padding: 8px; font-weight: bold; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; gap: 6px;">
                                    <i class="fas fa-plug-circle-bolt"></i> Test Connection
                                </a>
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;
            }
        }

        // 2. Fetch & update verification queue logs
        const queueRes = await fetch(`/api/dashboard/biometric/queue/updates/?_=${timestamp}`, { cache: 'no-store' });
        const queueData = await queueRes.json();
        if (queueData.success) {
            const tbody = document.querySelector('#requests-table tbody');
            if (tbody) {
                let html = '';
                if (queueData.queue.length === 0) {
                    html = '<tr><td colspan="7" class="text-center">No transactions in the biometric queue log.</td></tr>';
                } else {
                    queueData.queue.forEach(item => {
                        const statusClass = item.verification_status === 'ACCEPTED' ? 'in' : (item.verification_status === 'PENDING' ? 'initiate' : (item.verification_status === 'EXPIRED' ? 'time-out' : 'decline'));
                        
                        html += `
                            <tr>
                                <td>${convertUTCToIST(item.approved_at)}</td>
                                <td>
                                    <strong>${item.student_name}</strong><br>
                                    <span style="font-size: 11px; color: var(--text-muted);">ID: ${item.student_id}</span>
                                </td>
                                <td>
                                    <span style="font-family: monospace; font-size: 0.9rem;">#${item.request_id}</span>
                                </td>
                                <td>
                                    <span class="status-badge ${statusClass}">
                                        ${item.verification_status}
                                    </span>
                                </td>
                                <td>${item.sync_attempts || 0}</td>
                                <td>${convertUTCToIST(item.last_attempted_at)}</td>
                                <td style="max-width: 250px; white-space: normal; word-break: break-all; font-size: 0.85rem;">
                                    ${item.remarks || 'No errors logged.'}
                                </td>
                            </tr>
                        `;
                    });
                }
                tbody.innerHTML = html;
            }
        }
    } catch (err) {
        console.error('Biometric Diagnostics Polling Error:', err);
    }
}

// Event Delegation setup to ensure dynamic HTML elements capture button clicks correctly
function setupEventDelegation() {
    document.addEventListener('click', async (e) => {
        // 1. View request detail button click
        const viewBtn = e.target.closest('.view-req-detail-btn');
        if (viewBtn) {
            const reqDetailModal = document.getElementById('request-detail-modal');
            if (reqDetailModal) {
                document.getElementById('request-detail-modal').setAttribute('data-current-scholar-id', viewBtn.getAttribute('data-scholar-id'));
                
                const profileUrl = viewBtn.getAttribute('data-profile');
                const profileImg = document.getElementById('req-modal-profile-img');
                const profilePlaceholder = document.getElementById('req-modal-profile-placeholder');
                if (profileUrl) {
                    if (profileImg) {
                        profileImg.src = profileUrl;
                        profileImg.style.display = 'block';
                    }
                    if (profilePlaceholder) {
                        profilePlaceholder.style.display = 'none';
                    }
                } else {
                    if (profileImg) {
                        profileImg.style.display = 'none';
                        profileImg.src = '';
                    }
                    if (profilePlaceholder) {
                        profilePlaceholder.style.display = 'flex';
                    }
                }
                
                const studentName = viewBtn.getAttribute('data-student-name') || 'N/A';
                const reqModalTitleStudentName = document.getElementById('req-modal-title-student-name');
                if (reqModalTitleStudentName) reqModalTitleStudentName.textContent = (studentName !== 'N/A' ? studentName + "'s" : '');
                
                document.getElementById('req-modal-name').textContent = studentName;
                document.getElementById('req-modal-mobile').textContent = viewBtn.getAttribute('data-student-mobile') || 'N/A';
                document.getElementById('req-modal-course').textContent = viewBtn.getAttribute('data-course') || 'N/A';
                document.getElementById('req-modal-semester').textContent = viewBtn.getAttribute('data-semester') || 'N/A';
                document.getElementById('req-modal-hostel').textContent = viewBtn.getAttribute('data-hostel') || 'N/A';
                
                document.getElementById('req-modal-purpose').textContent = viewBtn.getAttribute('data-purpose') || 'N/A';
                document.getElementById('req-modal-destination').textContent = viewBtn.getAttribute('data-destination') || 'N/A';
                const leaveReason = viewBtn.getAttribute('data-leave-reason');
                const parentConfirmed = viewBtn.getAttribute('data-parent-confirmed');
                const declineReason = viewBtn.getAttribute('data-reason');
                const status = viewBtn.closest('tr').getAttribute('data-status');

                document.getElementById('req-modal-leave-reason').textContent = leaveReason || '-';
                document.getElementById('req-modal-parent-confirmed').textContent = (parentConfirmed === 'true' || parentConfirmed === 'True') ? '✔ Yes' : '✖ No';
                
                const declineSection = document.getElementById('req-modal-decline-section');
                if (status === 'Decline' || status === 'Reject') {
                    const declinedBy = status === 'Decline' ? 'Warden' : 'Registrar / Super Admin';
                    document.getElementById('req-modal-declined-by').textContent = declinedBy;
                    document.getElementById('req-modal-decline-reason').textContent = declineReason || '-';
                    if (declineSection) declineSection.style.display = 'block';
                } else {
                    if (declineSection) declineSection.style.display = 'none';
                }
                document.getElementById('req-modal-exit').textContent = convertUTCToIST(viewBtn.getAttribute('data-exit')) || 'N/A';
                document.getElementById('req-modal-entry').textContent = convertUTCToIST(viewBtn.getAttribute('data-entry')) || 'N/A';
                
                document.getElementById('req-modal-warden').textContent = viewBtn.getAttribute('data-warden') || 'Pending';
                document.getElementById('req-modal-warden-contact').textContent = viewBtn.getAttribute('data-warden-contact') || 'N/A';
                document.getElementById('req-modal-requested-by').textContent = viewBtn.getAttribute('data-requested-by') || 'N/A';
                
                // Copy/inject action buttons into modal footer
                const tr = viewBtn.closest('tr');
                if (tr) {
                    const actionCell = tr.querySelector('td:last-child');
                    const modalFooter = document.querySelector('#request-detail-modal .modal-footer');
                    if (actionCell && modalFooter) {
                        let modalActions = modalFooter.querySelector('.modal-actions-container');
                        if (!modalActions) {
                            modalActions = document.createElement('div');
                            modalActions.className = 'modal-actions-container';
                            modalFooter.insertBefore(modalActions, modalFooter.firstChild);
                        }
                        
                        let tempDiv = document.createElement('div');
                        tempDiv.innerHTML = actionCell.innerHTML;
                        const innerViewBtn = tempDiv.querySelector('.view-req-detail-btn');
                        if (innerViewBtn) {
                            innerViewBtn.remove();
                        }
                        modalActions.innerHTML = tempDiv.innerHTML;
                        modalActions.style.display = 'flex';
                        modalActions.style.gap = '8px';
                        modalActions.style.marginRight = 'auto';
                        
                        modalActions.querySelectorAll('.btn-action, button').forEach(b => {
                            b.removeAttribute('style');
                            b.style.display = 'inline-flex';
                            b.style.alignItems = 'center';
                            b.style.gap = '6px';
                            b.style.padding = '8px 16px';
                            b.style.fontSize = '14px';
                            b.style.fontWeight = '600';
                            b.style.borderRadius = '8px';
                            b.style.border = 'none';
                            b.style.cursor = 'pointer';
                            b.style.minHeight = '40px';
                            b.style.color = '#fff';
                            if (b.classList.contains('approve-btn') || b.classList.contains('gatekeeper-mark-in-btn')) {
                                b.style.backgroundColor = '#10b981';
                            } else if (b.classList.contains('reject-btn') || b.classList.contains('decline-btn')) {
                                b.style.backgroundColor = '#ef4444';
                            } else if (b.classList.contains('configure-btn')) {
                                b.style.backgroundColor = '#3b82f6';
                            } else if (b.classList.contains('gatekeeper-mark-out-btn')) {
                                b.style.backgroundColor = '#1f2937';
                            } else {
                                b.style.backgroundColor = '#6b7280';
                            }
                        });
                    }
                }
                
                reqDetailModal.classList.remove('hidden');
            }
            return;
        }

        // 2. Warden Approve click
        const approveBtn = e.target.closest('.approve-btn');
        if (approveBtn) {
            const id = approveBtn.getAttribute('data-id');
            if (confirm('Approve this request with default grace periods (15 min early)?')) {
                try {
                    const res = await fetch('/api/request/warden-approve/', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN},
                        body: JSON.stringify({request_id: id, reason: 'Approved', early_grace: 0, late_grace: 0})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) {
                        updateWardenDashboard();
                    }
                } catch(err) { alert('Network error.'); }
            }
            return;
        }

        // 3. Warden Configure click
        const configureBtn = e.target.closest('.configure-btn');
        if (configureBtn) {
            const id = configureBtn.getAttribute('data-id');
            const configureModal = document.getElementById('configure-time-modal');
            const configureRequestId = document.getElementById('configure-request-id');
            const configureFormMessage = document.getElementById('configure-form-message');
            if (configureModal && configureRequestId) {
                configureRequestId.value = id;
                configureFormMessage.textContent = '';
                configureFormMessage.className = '';
                configureModal.classList.remove('hidden');
            }
            return;
        }

        // 4. Warden Reject click
        const rejectBtn = e.target.closest('.reject-btn');
        if (rejectBtn) {
            const id = rejectBtn.getAttribute('data-id');
            const actionReasonModal = document.getElementById('action-reason-modal');
            const actionRequestIdInput = document.getElementById('action-request-id');
            const actionStatusInput = document.getElementById('action-status');
            const actionModalTitle = document.getElementById('action-modal-title');
            const actionReasonText = document.getElementById('action-reason-text');
            const actionFormMessage = document.getElementById('action-form-message');

            if (actionReasonModal) {
                actionRequestIdInput.value = id;
                actionStatusInput.value = 'Rejected';
                actionModalTitle.textContent = 'Reason for Rejection';
                actionReasonText.value = '';
                actionFormMessage.textContent = '';
                actionFormMessage.className = '';
                actionReasonModal.classList.remove('hidden');
            }
            return;
        }

        // 5. Gatekeeper Mark OUT click
        const markOutBtn = e.target.closest('.gatekeeper-mark-out-btn');
        if (markOutBtn) {
            const id = markOutBtn.getAttribute('data-id');
            if (confirm('Mark this student as OUT?')) {
                try {
                    const res = await fetch('/api/outpass/gatekeeper-mark-out/', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN},
                        body: JSON.stringify({request_id: id})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) {
                        updateGatekeeperDashboard();
                    }
                } catch(err) { alert('Network error.'); }
            }
            return;
        }

        // 6. Gatekeeper Mark IN click
        const markInBtn = e.target.closest('.gatekeeper-mark-in-btn');
        if (markInBtn) {
            const id = markInBtn.getAttribute('data-id');
            if (confirm('Mark this student as IN?')) {
                try {
                    const res = await fetch('/api/outpass/gatekeeper-mark-in/', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN},
                        body: JSON.stringify({request_id: id})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) {
                        updateGatekeeperDashboard();
                    }
                } catch(err) { alert('Network error.'); }
            }
            return;
        }

        // 7. Gatekeeper Reject click
        const gatekeeperRejectBtn = e.target.closest('.gatekeeper-reject-btn');
        if (gatekeeperRejectBtn) {
            const id = gatekeeperRejectBtn.getAttribute('data-id');
            const type = gatekeeperRejectBtn.getAttribute('data-type');
            const typeLabel = type === 'out' ? 'exit' : 'entry';
            if (confirm(`Reject this student's biometric ${typeLabel} scan?`)) {
                try {
                    const res = await fetch('/api/outpass/gatekeeper-reject/', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN},
                        body: JSON.stringify({request_id: id})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) {
                        updateGatekeeperDashboard();
                    }
                } catch(err) { alert('Network error.'); }
            }
            return;
        }
    });
}

window.openRequestDetails = function(requestId) {
    const isGatekeeperDashboard = document.getElementById('stat-total-expected') !== null;
    if (isGatekeeperDashboard) {
        const btn = document.querySelector(`.view-req-detail-btn[data-request-id="${requestId}"]`);
        if (btn) {
            btn.click();
        } else {
            window.pendingOpenRequestId = requestId;
        }
    } else {
        window.location.href = `/gatekeeper/?open_request_id=${requestId}`;
    }
};
