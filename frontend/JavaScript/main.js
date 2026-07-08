/**
 * Converts a UTC datetime string into IST (Asia/Kolkata) timezone.
 * Returns formatted string in exact format: DD/MM/YYYY HH:mm (24-hour format).
 * This is a pure function. It accepts UTC datetime values only and does not mutate its inputs or application state.
 *
 * @param {string} utcString - The UTC datetime string to convert.
 * @returns {string} The formatted IST datetime string, or "-" if invalid.
 */
function convertUTCToIST(utcString) {
    if (!utcString || typeof utcString !== 'string' || utcString.trim() === '' || utcString.trim() === '-') {
        return '-';
    }

    try {
        let dateObj;
        let parseStr = utcString.trim();

        // Check if string contains timezone info (ends with Z, or +/-XX:XX offset)
        const hasTimezone = parseStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(parseStr);
        if (!hasTimezone) {
            console.warn("Warning: convertUTCToIST received timezone-naive string:", utcString);
        }

        // Try standard Date parsing
        dateObj = new Date(parseStr);

        // Fallback for custom formats if standard Date parsing fails
        if (isNaN(dateObj.getTime())) {
            // 1. Try format: DD/MM/YYYY hh:mm AM/PM (e.g. 04/07/2026 10:15 PM)
            const ampmRegex = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})\s+(AM|PM)$/i;
            const ampmMatch = parseStr.match(ampmRegex);
            if (ampmMatch) {
                let day = parseInt(ampmMatch[1], 10);
                let month = parseInt(ampmMatch[2], 10) - 1;
                let year = parseInt(ampmMatch[3], 10);
                let hour = parseInt(ampmMatch[4], 10);
                let minute = parseInt(ampmMatch[5], 10);
                const ampm = ampmMatch[6].toUpperCase();
                if (ampm === 'PM' && hour < 12) hour += 12;
                if (ampm === 'AM' && hour === 12) hour = 0;
                
                const utcTimestamp = Date.UTC(year, month, day, hour, minute);
                dateObj = new Date(utcTimestamp);
            }

            // 2. Try format: DD/MM/YYYY HH:mm
            if (isNaN(dateObj.getTime())) {
                const dmyRegex = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/;
                const dmyMatch = parseStr.match(dmyRegex);
                if (dmyMatch) {
                    let day = parseInt(dmyMatch[1], 10);
                    let month = parseInt(dmyMatch[2], 10) - 1;
                    let year = parseInt(dmyMatch[3], 10);
                    let hour = parseInt(dmyMatch[4], 10);
                    let minute = parseInt(dmyMatch[5], 10);
                    
                    const utcTimestamp = Date.UTC(year, month, day, hour, minute);
                    dateObj = new Date(utcTimestamp);
                }
            }
        }

        if (isNaN(dateObj.getTime())) {
            return '-';
        }

        // Format to Asia/Kolkata timezone using Intl.DateTimeFormat (12-hour clock)
        const options = {
            timeZone: 'Asia/Kolkata',
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        };
        const formatter = new Intl.DateTimeFormat('en-US', options);
        const parts = formatter.formatToParts(dateObj);

        let dayPart = '', monthPart = '', yearPart = '', hourPart = '', minutePart = '', dayPeriod = '';
        for (const part of parts) {
            if (part.type === 'day') dayPart = part.value;
            else if (part.type === 'month') monthPart = part.value;
            else if (part.type === 'year') yearPart = part.value;
            else if (part.type === 'hour') hourPart = part.value;
            else if (part.type === 'minute') minutePart = part.value;
            else if (part.type === 'dayPeriod') dayPeriod = part.value.toUpperCase();
        }

        return `${dayPart}/${monthPart}/${yearPart} ${hourPart}:${minutePart} ${dayPeriod}`;

    } catch (e) {
        console.error("Error converting UTC to IST:", e);
        return '-';
    }
}

// Bind to window to guarantee global availability
window.convertUTCToIST = convertUTCToIST;

/**
 * Generates the standardized Leave Information HTML block to avoid duplicate implementations.
 */
function generateLeaveInformationHTML(leaveReason, parentConfirmed, status, declineReason) {
    let html = `
        <div style="text-align: left;">
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 8px; margin-bottom: 15px;">
                <strong style="color: var(--text-muted);">Leave Reason:</strong>
                <div style="font-weight: 500; word-break: break-word; line-height: 1.5; color: #334155;">${leaveReason || '-'}</div>
            </div>
            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 8px; margin-bottom: 15px;">
                <strong style="color: var(--text-muted);">Parents Confirmed:</strong>
                <span style="font-weight: 500;">${(parentConfirmed === true || parentConfirmed === 'true' || parentConfirmed === 'True') ? '✔ Yes' : '✖ No'}</span>
            </div>
    `;

    if (status === 'Decline' || status === 'Reject') {
        const declinedBy = status === 'Decline' ? 'Warden' : 'Registrar / Super Admin';
        html += `
            <div style="border-top: 1px dashed var(--border-color); padding-top: 15px; margin-top: 5px;">
                <div style="display: grid; grid-template-columns: 150px 1fr; gap: 8px; margin-bottom: 15px;">
                    <strong style="color: var(--danger);">Declined by:</strong>
                    <span style="font-weight: 500; color: var(--danger);">${declinedBy}</span>
                </div>
                <div style="display: grid; grid-template-columns: 150px 1fr; gap: 8px;">
                    <strong style="color: var(--danger);">Reason:</strong>
                    <div style="font-weight: 500; word-break: break-word; line-height: 1.5; color: var(--danger);">${declineReason || '-'}</div>
                </div>
            </div>
        `;
    }
    
    html += `</div>`;
    return html;
}
window.generateLeaveInformationHTML = generateLeaveInformationHTML;

document.addEventListener('DOMContentLoaded', () => {
    // Globally reset all forms on page refresh to clear cached/autofilled values
    document.querySelectorAll('form').forEach(form => {
        if (form.id !== 'login-form') {
            form.reset();
        }
    });

    // Current Datetime auto-fill
    const startDatetimeInput = document.getElementById('requested-exit-datetime');
    const endDatetimeInput = document.getElementById('requested-entry-datetime');

    if (startDatetimeInput && endDatetimeInput) {
        // Format to YYYY-MM-DDTHH:MM for datetime-local
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        const formatted = now.toISOString().slice(0, 16);

        startDatetimeInput.value = formatted;
        endDatetimeInput.value = formatted;
    }

    // Modal Logic
    const modal = document.getElementById('student-modal');
    const btnView = document.getElementById('btn-view');
    const btnCloseModals = document.querySelectorAll('.btn-close-modal');

    function openModal() {
        modal.classList.remove('hidden');
    }

    function closeModal() {
        modal.classList.add('hidden');
    }

    btnCloseModals.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            closeModal();
        });
    });

    // Close modal when clicking outside
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    // Fetch Student logic
    const scholarInput = document.getElementById('scholar-id');
    const nameDisplay = document.getElementById('student-name-display');
    let currentStudent = null;

    if (scholarInput) {
        scholarInput.addEventListener('input', async (e) => {
            const id = e.target.value.trim();
            if (id.length > 5) { // Assuming length is enough to start searching
                try {
                    const response = await fetch(`/api/student/${id}/`);
                    const data = await response.json();
                    if (data.success) {
                        nameDisplay.textContent = data.student_name;
                        currentStudent = data;

                        // Populate modal silently
                        const modalProfileImg = document.getElementById('modal-profile-img');
                        const modalProfilePlaceholder = document.getElementById('modal-profile-placeholder');
                        if (data.image_url && data.image_url !== '/static/images/default_avatar.png') {
                            if (modalProfileImg) {
                                modalProfileImg.src = data.image_url;
                                modalProfileImg.style.display = 'block';
                            }
                            if (modalProfilePlaceholder) {
                                modalProfilePlaceholder.style.display = 'none';
                            }
                        } else {
                            if (modalProfileImg) {
                                modalProfileImg.style.display = 'none';
                                modalProfileImg.src = '';
                            }
                            if (modalProfilePlaceholder) {
                                modalProfilePlaceholder.style.display = 'flex';
                            }
                        }
                        const modalTitleStudentName = document.getElementById('modal-title-student-name');
                        if (modalTitleStudentName) modalTitleStudentName.textContent = data.student_name + "'s";
                        document.getElementById('modal-name').textContent = data.student_name;
                        document.getElementById('modal-mobile').textContent = data.mobile_number;
                        document.getElementById('modal-course').textContent = data.course;
                        document.getElementById('modal-semester').textContent = data.semester;
                        const modHostel = document.getElementById('modal-hostel');
                        if (modHostel) modHostel.textContent = data.hostel_name;

                        const modParentName = document.getElementById('modal-parent-name');
                        if (modParentName) modParentName.textContent = data.guardian_name || 'N/A';
                        const modParentRel = document.getElementById('modal-parent-relation');
                        if (modParentRel) modParentRel.textContent = data.guardian_relation || 'N/A';
                        const modParentContact = document.getElementById('modal-parent-contact');
                        if (modParentContact) modParentContact.textContent = data.guardian_contact || 'N/A';

                        const purposeInput = document.getElementById('purpose');
                        const destInput = document.getElementById('destination');
                        if (purposeInput && data.purpose) purposeInput.value = data.purpose;
                        if (destInput && data.destination) destInput.value = data.destination;
                    } else {
                        nameDisplay.textContent = 'Student not found';
                        currentStudent = null;
                    }
                } catch (err) {
                    nameDisplay.textContent = 'Error fetching details';
                    currentStudent = null;
                }
            } else {
                nameDisplay.textContent = 'Enter ID to fetch';
                currentStudent = null;
            }
        });
    }

    if (btnView) {
        btnView.addEventListener('click', () => {
            if (currentStudent) {
                openModal();
            } else {
                alert('Please enter a valid Scholar ID first.');
            }
        });
    }

    // Form Submission (Intercepted for Send Request Popup)
    const outpassForm = document.getElementById('outpass-form');
    if (outpassForm) {
        outpassForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const msgDiv = document.getElementById('form-message');

            if (!currentStudent) {
                msgDiv.className = 'message error';
                msgDiv.textContent = 'Please enter a valid Scholar ID before submitting.';
                return;
            }

            // Evaluate conditions to determine if Parent Confirmation is mandatory
            const purpose = document.getElementById('purpose').value;
            const exitStr = document.getElementById('requested-exit-datetime').value;
            const entryStr = document.getElementById('requested-entry-datetime').value;
            
            let requireParentConfirm = true;
            
            if (purpose === 'Emergency' || purpose === 'Sunday Outing') {
                requireParentConfirm = false;
            } else if (exitStr && entryStr) {
                const exitTime = new Date(exitStr);
                const entryTime = new Date(entryStr);
                const diffHours = (entryTime - exitTime) / (1000 * 60 * 60);
                if (diffHours <= 2) {
                    requireParentConfirm = false;
                }
            }

            // Show the popup instead of submitting directly
            const sendModal = document.getElementById('send-request-modal');
            if (sendModal) {
                document.getElementById('popup-leave-reason').value = '';
                
                const cb = document.getElementById('popup-parent-confirmed');
                cb.checked = false;
                cb.required = requireParentConfirm;
                
                const label = document.querySelector('label[for="popup-parent-confirmed"]');
                if (label) {
                    const asterisk = label.querySelector('span');
                    if (asterisk) asterisk.style.display = requireParentConfirm ? 'inline' : 'none';
                }

                document.getElementById('send-form-message').textContent = '';
                sendModal.classList.remove('hidden');
            }
        });
    }

    // Popup Form Submission (Actual API Call)
    const sendRequestForm = document.getElementById('send-request-form');
    if (sendRequestForm) {
        document.getElementById('btn-cancel-send-modal').addEventListener('click', () => {
            document.getElementById('send-request-modal').classList.add('hidden');
        });
        document.getElementById('btn-close-send-modal').addEventListener('click', () => {
            document.getElementById('send-request-modal').classList.add('hidden');
        });

        sendRequestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btnConfirm = document.getElementById('btn-confirm-send');
            const formMsg = document.getElementById('form-message');
            const popupMsg = document.getElementById('send-form-message');

            const payload = {
                scholar_id: document.getElementById('scholar-id').value,
                purpose: document.getElementById('purpose').value,
                destination: document.getElementById('destination').value,
                requested_exit_datetime: document.getElementById('requested-exit-datetime').value,
                requested_entry_datetime: document.getElementById('requested-entry-datetime').value,
                leave_reason: document.getElementById('popup-leave-reason').value,
                parent_confirmed: document.getElementById('popup-parent-confirmed').checked
            };

            // Loading state
            btnConfirm.disabled = true;
            btnConfirm.textContent = 'Sending...';

            try {
                const response = await fetch('/api/request/create/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.CSRF_TOKEN
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                if (data.success) {
                    document.getElementById('send-request-modal').classList.add('hidden');
                    formMsg.className = 'message success';
                    formMsg.textContent = 'Request submitted successfully!';
                    
                    if (outpassForm) outpassForm.reset();
                    const nameDisplay = document.getElementById('name-display');
                    if (nameDisplay) nameDisplay.textContent = 'Enter ID to fetch';
                    currentStudent = null;

                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    popupMsg.style.color = 'var(--danger)';
                    popupMsg.textContent = data.message || 'Failed to submit request.';
                }
            } catch (err) {
                console.error(err);
                popupMsg.style.color = 'var(--danger)';
                popupMsg.textContent = 'Network error.';
            } finally {
                btnConfirm.disabled = false;
                btnConfirm.textContent = 'Confirm & Send';
            }
        });
    }

    // Table Filtering
    const searchInput = document.getElementById('table-search');
    const statusFilter = document.getElementById('status-filter');
    const tableBody = document.querySelector('#requests-table tbody');

    function filterTable() {
        if (!tableBody) return;
        const rows = tableBody.querySelectorAll('tr');
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const statusTerm = statusFilter ? statusFilter.value : 'All';

        rows.forEach(row => {
            if (row.children.length === 1) return; // Skip "No requests" row

            const rowText = row.textContent.toLowerCase();
            const status = row.getAttribute('data-status');

            const matchesSearch = !searchTerm || rowText.includes(searchTerm);
            const matchesStatus = statusTerm === 'All' || status === statusTerm ||
                (statusTerm === 'Accept' && status === 'ACCEPTED') ||
                (statusTerm === 'ACCEPTED' && status === 'Accept');

            if (matchesSearch && matchesStatus) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    if (searchInput) searchInput.addEventListener('input', filterTable);
    if (statusFilter) statusFilter.addEventListener('change', filterTable);
    window.filterTable = filterTable;

    // Approve/Reject Actions logic
    const actionReasonModal = document.getElementById('action-reason-modal');
    const actionReasonForm = document.getElementById('action-reason-form');
    const actionRequestIdInput = document.getElementById('action-request-id');
    const actionStatusInput = document.getElementById('action-status');
    const actionReasonText = document.getElementById('action-reason-text');
    const actionModalTitle = document.getElementById('action-modal-title');
    const actionFormMessage = document.getElementById('action-form-message');

    function openActionModal(id, status) {
        actionRequestIdInput.value = id;
        actionStatusInput.value = status;
        actionModalTitle.textContent = status === 'Approved' ? 'Reason for Approval' : 'Reason for Rejection';
        actionReasonText.value = '';
        actionFormMessage.textContent = '';
        actionFormMessage.className = '';
        actionReasonModal.classList.remove('hidden');
    }

    document.querySelectorAll('.btn-close-action-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            actionReasonModal.classList.add('hidden');
        });
    });

    document.querySelectorAll('.approve-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const id = btn.dataset.id;
            if (confirm('Approve this request with default grace periods (15 min early)?')) {
                try {
                    const res = await fetch('/api/request/warden-approve/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                        body: JSON.stringify({ request_id: id, reason: 'Approved', early_grace: 0, late_grace: 0 })
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) window.location.reload();
                } catch (err) { alert('Network error.'); }
            }
        });
    });

    const configureModal = document.getElementById('configure-time-modal');
    const configureForm = document.getElementById('configure-time-form');
    const configureRequestId = document.getElementById('configure-request-id');
    const configureFormMessage = document.getElementById('configure-form-message');

    document.querySelectorAll('.configure-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            configureRequestId.value = btn.dataset.id;
            configureFormMessage.textContent = '';
            configureFormMessage.className = '';
            
            const btnSubmit = document.getElementById('btn-submit-configure');
            if (window.location.pathname.includes('/timeouts/')) {
                if (btnSubmit) btnSubmit.textContent = 'Confirm Recovery';
            } else {
                if (btnSubmit) btnSubmit.textContent = 'Save & Approve';
            }
            configureModal.classList.remove('hidden');
        });
    });

    document.querySelectorAll('#btn-close-configure-modal, #btn-cancel-configure-modal').forEach(btn => {
        if (btn) {
            btn.addEventListener('click', () => {
                configureModal.classList.add('hidden');
            });
        }
    });

    if (configureForm) {
        configureForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = configureRequestId.value;
            const earlyGrace = parseInt(document.getElementById('configure-early-grace').value) || 0;
            const lateGrace = parseInt(document.getElementById('configure-late-grace').value) || 0;

            const btnSubmit = document.getElementById('btn-submit-configure');
            btnSubmit.disabled = true;
            
            const isTimeoutRecovery = window.location.pathname.includes('/timeouts/');
            const defaultBtnText = isTimeoutRecovery ? 'Confirm Recovery' : 'Save & Approve';
            const apiUrl = isTimeoutRecovery ? '/api/request/reconfigure-grace/' : '/api/request/configure-approve/';

            btnSubmit.textContent = 'Saving...';
            configureFormMessage.textContent = '';

            try {
                const res = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                    body: JSON.stringify({
                        request_id: id,
                        early_grace: earlyGrace,
                        late_grace: lateGrace
                    })
                });
                const data = await res.json();
                if (data.success) {
                    configureFormMessage.className = 'message success';
                    configureFormMessage.textContent = data.message;
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    configureFormMessage.className = 'message error';
                    configureFormMessage.textContent = data.message;
                    btnSubmit.disabled = false;
                    btnSubmit.textContent = defaultBtnText;
                }
            } catch (err) {
                configureFormMessage.className = 'message error';
                configureFormMessage.textContent = 'Network error occurred.';
                btnSubmit.disabled = false;
                btnSubmit.textContent = defaultBtnText;
            }
        });
    }

    document.querySelectorAll('.reject-btn').forEach(btn => {
        btn.addEventListener('click', () => openActionModal(btn.dataset.id, 'Rejected'));
    });

    // Gatekeeper Manual Flow
    document.querySelectorAll('.gatekeeper-mark-out-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            if (confirm('Mark this student as OUT? Data will be sent to biometric again.')) {
                try {
                    const res = await fetch('/api/request/gatekeeper-mark-out/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                        body: JSON.stringify({ request_id: btn.dataset.id })
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) window.location.reload();
                } catch (err) { alert('Network error.'); }
            }
        });
    });

    document.querySelectorAll('.gatekeeper-mark-in-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            if (confirm('Mark this student as IN?')) {
                try {
                    const res = await fetch('/api/request/gatekeeper-mark-in/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.CSRF_TOKEN },
                        body: JSON.stringify({ request_id: btn.dataset.id })
                    });
                    const data = await res.json();
                    alert(data.message);
                    if (data.success) window.location.reload();
                } catch (err) { alert('Network error.'); }
            }
        });
    });

    document.querySelectorAll('.send-biometric-btn').forEach(btn => {
        btn.addEventListener('click', () => openActionModal(btn.dataset.id, 'Sent to Biometric'));
    });

    if (actionReasonForm) {
        actionReasonForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = actionRequestIdInput.value;
            const status = actionStatusInput.value;
            const reason = actionReasonText.value.trim();

            const earlyGrace = document.getElementById('action-early-grace') ? parseInt(document.getElementById('action-early-grace').value) || 0 : 0;
            const lateGrace = document.getElementById('action-late-grace') ? parseInt(document.getElementById('action-late-grace').value) || 0 : 0;

            if (!reason) {
                actionFormMessage.textContent = 'Reason is required.';
                actionFormMessage.className = 'message error';
                return;
            }

            const btnSubmit = document.getElementById('btn-submit-action');
            btnSubmit.disabled = true;
            btnSubmit.textContent = 'Saving...';

            try {
                let url;
                if (status === 'Sent to Biometric') {
                    url = '/api/outpass/send-to-biometric/';
                } else {
                    url = '/api/request/registrar-decline/';
                }

                const payload = {
                    request_id: id,
                    reason: reason,
                    early_grace: 0,
                    late_grace: 0
                };

                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.CSRF_TOKEN
                    },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.success) {
                    window.location.reload();
                } else {
                    actionFormMessage.textContent = data.message || 'Error saving reason.';
                    actionFormMessage.className = 'message error';
                    btnSubmit.disabled = false;
                    btnSubmit.textContent = 'Submit';
                }
            } catch (err) {
                actionFormMessage.textContent = 'Network error occurred.';
                actionFormMessage.className = 'message error';
                btnSubmit.disabled = false;
                btnSubmit.textContent = 'Submit';
            }
        });
    }

    // Animated Counters
    const counters = document.querySelectorAll('.counter');
    const speed = 200; // lower is faster

    counters.forEach(counter => {
        const target = +counter.getAttribute('data-target');
        if (target === 0) return;

        const updateCount = () => {
            const current = +counter.innerText;
            const inc = target / speed;

            if (current < target) {
                counter.innerText = Math.ceil(current + inc);
                setTimeout(updateCount, 10);
            } else {
                counter.innerText = target;
            }
        };
        updateCount();
    });

    // ==========================================
    // STUDENT MANAGEMENT LOGIC
    // ==========================================
    // ==========================================
    // STUDENT MANAGEMENT LOGIC
    // ==========================================
    const studentForm = document.getElementById('student-form');
    if (studentForm) {
        const formMode = document.getElementById('form-mode');
        const scholarInput = document.getElementById('reg-scholar-id');
        const btnCancelEdit = document.getElementById('btn-cancel-edit');
        const formTitle = document.getElementById('form-title');
        const msgDiv = document.getElementById('student-form-message');

        // Profile Image Preview Logic
        const profileInput = document.getElementById('student-profile-image-input');
        const previewImg = document.getElementById('profile-preview-img');
        const previewPlaceholder = document.getElementById('profile-preview-placeholder');

        const DEPARTMENT_COURSES = {
            'Computer Science Department': [
                'Bachelor of Computer Application (B.C.A.) (Honors)',
                'B.Sc. Information Technology (BSc.IT) (Honors)',
                'M.C.A. Master of Computer Applications (Data Science)',
                'BCA',
                'BSc IT',
                'MCA'
            ],
            'Mechanical Department': [
                'BTech Mechanical'
            ],
            'Management Department': [
                'BBA',
                'MBA'
            ],
            'Animation Department': [
                'B.Sc. Animation & Visual Effects',
                'M.Sc. Animation & Visual Effects'
            ],
            'Journalism Department': [
                'B.A. Music Instrumental Mridang/Tabla (Honors)',
                'B.A. Music-Vocal (Honors)',
                'M.A. Music (Tabla and Pakhawaj)',
                'M.A. Music (Vocal)'
            ],
            'Hindi Department': [
                'B.A. Hindi (Honors)',
                'M.A. Hindi'
            ],
            'Music Department': [
                'B.A. Music Instrumental Mridang/Tabla (Honors)',
                'B.A. Music-Vocal (Honors)',
                'M.A. Music (Tabla and Pakhawaj)',
                'M.A. Music (Vocal)'
            ],
            'English Department': [
                'B.A. English (Honors)',
                'M.A. English'
            ],
            'Tourism Department': [
                'B.B.A. Tourism & Travel Management (Honors)',
                'M.B.A. Tourism & Travel Management'
            ]
        };

        const deptSelect = document.getElementById('reg-department');
        const courseSelect = document.getElementById('reg-course');
        const nameInput = document.getElementById('reg-name');
        const mobileInput = document.getElementById('reg-mobile');
        const emailInput = document.getElementById('reg-email');
        const semesterInput = document.getElementById('reg-semester');
        const hostelInput = document.getElementById('reg-hostel');

        // Helper functions for custom error handling
        const clearErrors = () => {
            document.querySelectorAll('.field-error-message').forEach(el => {
                el.innerText = '';
                el.style.display = 'none';
            });
            msgDiv.className = '';
            msgDiv.textContent = '';
        };

        const showError = (fieldId, message) => {
            const errorEl = document.getElementById(`error-${fieldId}`);
            if (errorEl) {
                errorEl.innerText = message;
                errorEl.style.display = 'block';
            }
        };

        // Input change error clearing
        const formFields = ['reg-scholar-id', 'reg-name', 'reg-email', 'reg-mobile', 'reg-department', 'reg-course', 'reg-semester', 'reg-hostel'];
        formFields.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const eventName = el.tagName === 'SELECT' ? 'change' : 'input';
                el.addEventListener(eventName, () => {
                    const errorEl = document.getElementById(`error-${id}`);
                    if (errorEl) {
                        errorEl.innerText = '';
                        errorEl.style.display = 'none';
                    }
                });
            }
        });

        if (mobileInput) {
            mobileInput.addEventListener('input', (e) => {
                let val = e.target.value.replace(/\D/g, '');
                if (val.length > 10) {
                    val = val.substring(0, 10);
                }
                e.target.value = val;
            });
        }

        if (deptSelect && courseSelect) {
            deptSelect.addEventListener('change', () => {
                const selectedDept = deptSelect.value;
                courseSelect.innerHTML = '<option value="" disabled selected>Select Course</option>';
                if (selectedDept && DEPARTMENT_COURSES[selectedDept]) {
                    DEPARTMENT_COURSES[selectedDept].forEach(course => {
                        const opt = document.createElement('option');
                        opt.value = course;
                        opt.textContent = course;
                        courseSelect.appendChild(opt);
                    });
                }
            });
        }

        if (profileInput) {
            profileInput.addEventListener('change', () => {
                const file = profileInput.files[0];
                if (file) {
                    const ext = file.name.split('.').pop().toLowerCase();
                    if (!['jpg', 'jpeg', 'png', 'webp'].includes(ext)) {
                        msgDiv.className = 'message error';
                        msgDiv.textContent = 'Invalid image format. Allowed: JPG, JPEG, PNG, WEBP.';
                        profileInput.value = '';
                        previewImg.src = '';
                        previewImg.style.display = 'none';
                        previewPlaceholder.style.display = 'block';
                        return;
                    }
                    msgDiv.className = '';
                    msgDiv.textContent = '';

                    const reader = new FileReader();
                    reader.onload = (e) => {
                        previewImg.src = e.target.result;
                        previewImg.style.display = 'block';
                        previewPlaceholder.style.display = 'none';
                    };
                    reader.readAsDataURL(file);
                } else {
                    previewImg.src = '';
                    previewImg.style.display = 'none';
                    previewPlaceholder.style.display = 'block';
                }
            });
        }

        // Form Submit (Create / Update via FormData)
        studentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btnSubmit = document.getElementById('btn-save-student');
            const btnText = btnSubmit.querySelector('.btn-text');
            const spinner = btnSubmit.querySelector('.spinner');

            // Client-side validations
            clearErrors();
            let isValid = true;
            let firstInvalidField = null;

            if (!scholarInput.value.trim()) {
                showError('reg-scholar-id', 'Scholar ID is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = scholarInput;
            }

            if (!nameInput.value.trim()) {
                showError('reg-name', 'Student Name is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = nameInput;
            }

            const emailVal = emailInput.value.trim();
            if (!emailVal) {
                showError('reg-email', 'Email Address is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = emailInput;
            } else {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(emailVal)) {
                    showError('reg-email', 'Please enter a valid email address.');
                    isValid = false;
                    if (!firstInvalidField) firstInvalidField = emailInput;
                }
            }

            const mobileVal = mobileInput.value.trim();
            if (!mobileVal) {
                showError('reg-mobile', 'Mobile Number is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = mobileInput;
            } else if (mobileVal.length !== 10) {
                showError('reg-mobile', 'Mobile number must contain exactly 10 digits.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = mobileInput;
            }

            if (!deptSelect.value) {
                showError('reg-department', 'Department is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = deptSelect;
            }

            if (!courseSelect.value) {
                showError('reg-course', 'Course is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = courseSelect;
            }

            if (!semesterInput.value) {
                showError('reg-semester', 'Semester is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = semesterInput;
            } else {
                const semNum = parseInt(semesterInput.value, 10);
                if (isNaN(semNum) || semNum < 1 || semNum > 10) {
                    showError('reg-semester', 'Semester must be between 1 and 10.');
                    isValid = false;
                    if (!firstInvalidField) firstInvalidField = semesterInput;
                }
            }

            if (!hostelInput.value.trim()) {
                showError('reg-hostel', 'Hostel Name is required.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = hostelInput;
            }

            // Client-side file extension check
            if (profileInput && profileInput.files[0]) {
                const file = profileInput.files[0];
                const ext = file.name.split('.').pop().toLowerCase();
                if (!['jpg', 'jpeg', 'png', 'webp'].includes(ext)) {
                    msgDiv.className = 'message error';
                    msgDiv.textContent = 'Invalid image format. Allowed: JPG, JPEG, PNG, WEBP.';
                    isValid = false;
                }
            }

            if (!isValid) {
                if (firstInvalidField) firstInvalidField.focus();
                return;
            }

            const formData = new FormData();
            formData.append('scholar_id', scholarInput.value.trim());
            formData.append('student_name', nameInput.value.trim());
            formData.append('mobile_number', mobileInput.value.trim());
            formData.append('department', deptSelect.value);
            formData.append('course', courseSelect.value);
            formData.append('semester', semesterInput.value);
            formData.append('hostel_name', hostelInput.value.trim());
            formData.append('email', emailInput.value.trim());
            if (profileInput && profileInput.files[0]) {
                formData.append('profile_image', profileInput.files[0]);
            }

            const endpoint = formMode.value === 'create' ? '/api/student/create/' : '/api/student/update/';

            btnText.classList.add('hidden');
            spinner.classList.remove('hidden');
            btnSubmit.disabled = true;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': window.CSRF_TOKEN
                    },
                    body: formData
                });

                const data = await response.json();
                if (data.success) {
                    msgDiv.className = 'message success';
                    msgDiv.textContent = data.message;
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    msgDiv.className = 'message error';
                    msgDiv.textContent = data.message;
                }
            } catch (err) {
                msgDiv.className = 'message error';
                msgDiv.textContent = 'Network error occurred.';
            } finally {
                btnText.classList.remove('hidden');
                spinner.classList.add('hidden');
                btnSubmit.disabled = false;
            }
        });

        // Edit Button Click
        document.querySelectorAll('.edit-student-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                clearErrors();
                scholarInput.value = btn.dataset.id;
                scholarInput.readOnly = true; // Cannot change PK
                nameInput.value = btn.dataset.name;
                mobileInput.value = btn.dataset.mobile;

                if (deptSelect) {
                    deptSelect.value = btn.dataset.department || '';
                    deptSelect.dispatchEvent(new Event('change'));
                }
                if (courseSelect) {
                    courseSelect.value = btn.dataset.course || '';
                }

                semesterInput.value = btn.dataset.semester;
                hostelInput.value = btn.dataset.hostel;
                emailInput.value = btn.dataset.email || '';

                // Show current profile image if available
                const profileUrl = btn.dataset.profile;
                if (profileUrl) {
                    previewImg.src = profileUrl;
                    previewImg.style.display = 'block';
                    previewPlaceholder.style.display = 'none';
                } else {
                    previewImg.src = '';
                    previewImg.style.display = 'none';
                    previewPlaceholder.style.display = 'block';
                }

                if (profileInput) profileInput.value = ''; // Reset file input

                formMode.value = 'update';
                formTitle.innerHTML = '<i class="fas fa-user-edit"></i> Edit Student';
                btnCancelEdit.classList.remove('hidden');
                document.getElementById('btn-save-student').querySelector('.btn-text').textContent = 'Update Student';

                // Scroll to top
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        });

        // Cancel Edit
        btnCancelEdit.addEventListener('click', () => {
            clearErrors();
            studentForm.reset();
            scholarInput.readOnly = false;
            if (courseSelect) {
                courseSelect.innerHTML = '<option value="" disabled selected>Select Course</option>';
            }
            formMode.value = 'create';
            formTitle.innerHTML = '<i class="fas fa-user-plus"></i> Register New Student';
            btnCancelEdit.classList.add('hidden');
            document.getElementById('btn-save-student').querySelector('.btn-text').textContent = 'Save Student';

            // Reset preview
            previewImg.src = '';
            previewImg.style.display = 'none';
            previewPlaceholder.style.display = 'block';
            if (profileInput) profileInput.value = '';
        });

        // Delete Button Click
        document.querySelectorAll('.delete-student-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                if (!confirm(`Are you sure you want to delete student ${id}? This will also delete all their outpass requests.`)) return;

                try {
                    const response = await fetch('/api/student/delete/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.CSRF_TOKEN
                        },
                        body: JSON.stringify({ scholar_id: id })
                    });
                    const data = await response.json();
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(data.message);
                    }
                } catch (err) {
                    alert('Error deleting student.');
                }
            });
        });

        // Student Table Filtering
        const stuSearchInput = document.getElementById('student-search');
        const stuTableBody = document.querySelector('#students-table tbody');

        if (stuSearchInput && stuTableBody) {
            stuSearchInput.addEventListener('input', () => {
                const searchTerm = stuSearchInput.value.toLowerCase();
                const rows = stuTableBody.querySelectorAll('tr');

                rows.forEach(row => {
                    if (row.children.length === 1) return; // Skip empty message

                    const scholarId = row.children[1].textContent.toLowerCase();
                    const name = row.children[3].textContent.toLowerCase();
                    const email = row.children[4] ? row.children[4].textContent.toLowerCase() : '';
                    const course = row.children[6] ? row.children[6].textContent.toLowerCase() : '';

                    if (scholarId.includes(searchTerm) || name.includes(searchTerm) || email.includes(searchTerm) || course.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
        }

        // Checkbox Selection Logic for Registered Students Table
        const studentMasterCheckbox = document.getElementById('student-master-checkbox');
        const studentTableBody = document.querySelector('#students-table tbody');

        if (studentMasterCheckbox && studentTableBody) {
            studentMasterCheckbox.addEventListener('change', () => {
                const isChecked = studentMasterCheckbox.checked;
                const rowCheckboxes = studentTableBody.querySelectorAll('.student-row-checkbox');
                rowCheckboxes.forEach(cb => {
                    cb.checked = isChecked;
                });
            });

            studentTableBody.addEventListener('change', (e) => {
                if (e.target && e.target.classList.contains('student-row-checkbox')) {
                    const rowCheckboxes = studentTableBody.querySelectorAll('.student-row-checkbox');
                    const checkedCheckboxes = studentTableBody.querySelectorAll('.student-row-checkbox:checked');
                    studentMasterCheckbox.checked = (rowCheckboxes.length > 0 && rowCheckboxes.length === checkedCheckboxes.length);
                }
            });
        }
    }



    // Column selector logic
    const columnBtn = document.getElementById('columnDropdownBtn');
    const columnMenu = document.getElementById('columnDropdownMenu');
    const columnCheckboxes = columnMenu ? columnMenu.querySelectorAll('input[type="checkbox"]') : [];
    const reqTable = document.getElementById('requests-table');

    if (columnBtn && columnMenu) {
        columnBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            columnMenu.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!columnBtn.contains(e.target) && !columnMenu.contains(e.target)) {
                columnMenu.classList.add('hidden');
            }
        });

        const savedColumns = JSON.parse(localStorage.getItem('outpass_column_prefs') || '[]');

        function updateColumnVisibility() {
            if (!reqTable) return;
            const rows = reqTable.querySelectorAll('tr');
            const prefs = [];

            columnCheckboxes.forEach((checkbox) => {
                const colIndex = parseInt(checkbox.value);
                const isVisible = checkbox.checked;
                prefs.push(isVisible);

                rows.forEach(row => {
                    const cells = row.children;
                    if (cells[colIndex] && !cells[colIndex].hasAttribute('colspan')) {
                        cells[colIndex].style.display = isVisible ? '' : 'none';
                    }
                });
            });

            localStorage.setItem('outpass_column_prefs', JSON.stringify(prefs));

            const emptyRow = reqTable.querySelector('.text-center');
            if (emptyRow && emptyRow.hasAttribute('colspan')) {
                const visibleCount = prefs.filter(Boolean).length;
                emptyRow.setAttribute('colspan', visibleCount);
            }
        }

        columnCheckboxes.forEach((checkbox, index) => {
            if (savedColumns.length > 0 && savedColumns[index] !== undefined) {
                checkbox.checked = savedColumns[index];
            }
            checkbox.addEventListener('change', updateColumnVisibility);
        });

        updateColumnVisibility();
    }

    // History Modal Logic
    const historyModal = document.getElementById('history-modal');
    if (historyModal) {
        const closeHistoryBtns = document.querySelectorAll('.btn-close-history-modal');
        const historyTableBody = document.getElementById('history-table-body');
        const histTotal = document.getElementById('hist-total');
        const histApproved = document.getElementById('hist-approved');
        const histPending = document.getElementById('hist-pending');
        const histRejected = document.getElementById('hist-rejected');
        const histTitle = document.getElementById('history-modal-title');

        function closeHistoryModal() {
            historyModal.classList.add('hidden');
        }

        closeHistoryBtns.forEach(btn => {
            btn.addEventListener('click', closeHistoryModal);
        });

        document.querySelectorAll('.view-history-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const scholarId = e.currentTarget.getAttribute('data-scholar-id');
                if (histTitle) histTitle.textContent = 'Loading...';
                historyModal.classList.remove('hidden');
                if (historyTableBody) historyTableBody.innerHTML = '<tr><td colspan="6" class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>';

                if (histTotal) histTotal.textContent = '0';
                if (histApproved) histApproved.textContent = '0';
                if (histPending) histPending.textContent = '0';
                if (histRejected) histRejected.textContent = '0';

                try {
                    const response = await fetch(`/api/student/${scholarId}/history/`);
                    const data = await response.json();

                    if (data.success) {
                        if (histTitle) histTitle.textContent = `Outing History - ${data.student_name} (${scholarId})`;
                        if (histTotal) histTotal.textContent = data.stats.total;
                        if (histApproved) histApproved.textContent = data.stats.approved;
                        if (histPending) histPending.textContent = data.stats.pending;
                        if (histRejected) histRejected.textContent = data.stats.rejected;

                        if (historyTableBody) {
                            historyTableBody.innerHTML = '';
                            if (data.history.length === 0) {
                                historyTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No history found.</td></tr>';
                            } else {
                                data.history.forEach(req => {
                                    const row = document.createElement('tr');
                                    row.innerHTML = `
                                        <td>${convertUTCToIST(req.requested_exit_datetime)}</td>
                                        <td>${req.outing_reason}</td>
                                        <td>${req.destination}</td>
                                        <td><span class="status-badge ${req.request_status.toLowerCase().replace(/\s+/g, '-')}">${req.request_status}</span></td>
                                        <td>${req.warden_remarks || '-'}</td>
                                    `;
                                    historyTableBody.appendChild(row);
                                });
                            }
                        }
                    } else {
                        if (histTitle) histTitle.textContent = 'Error';
                        if (historyTableBody) historyTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${data.message || 'Failed to fetch history'}</td></tr>`;
                    }
                } catch (error) {
                    if (histTitle) histTitle.textContent = 'Error';
                    if (historyTableBody) historyTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Network error occurred</td></tr>';
                }
            });
        });
    }

    // Column Visibility Toggle Logic
    const colToggles = document.querySelectorAll('.col-toggle');
    const table = document.getElementById('requests-table');

    if (table && colToggles.length > 0) {
        // Load preferences from localStorage
        const savedCols = JSON.parse(localStorage.getItem('outpass_column_prefs')) || {};

        colToggles.forEach(toggle => {
            const colIdx = toggle.getAttribute('data-col');

            // Apply saved preference if it exists
            if (savedCols[colIdx] !== undefined) {
                toggle.checked = savedCols[colIdx];
            }

            // Function to apply visibility to the column
            const applyVisibility = (idx, isVisible) => {
                const displayStyle = isVisible ? '' : 'none';

                // Toggle th
                const ths = table.querySelectorAll(`thead tr th:nth-child(${parseInt(idx) + 1})`);
                ths.forEach(th => th.style.display = displayStyle);

                // Toggle td
                const trs = table.querySelectorAll('tbody tr');
                trs.forEach(tr => {
                    const td = tr.querySelector(`td:nth-child(${parseInt(idx) + 1})`);
                    if (td) td.style.display = displayStyle;
                });
            };

            // Apply initially
            applyVisibility(colIdx, toggle.checked);

            // Listen for changes
            toggle.addEventListener('change', (e) => {
                const isVisible = e.target.checked;
                applyVisibility(colIdx, isVisible);

                // Save to localStorage
                savedCols[colIdx] = isVisible;
                localStorage.setItem('outpass_column_prefs', JSON.stringify(savedCols));
            });
        });
    }

    // Request Detail Modal Logic
    const reqDetailModal = document.getElementById('request-detail-modal');
    if (reqDetailModal) {
        document.querySelectorAll('.view-req-detail-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                reqDetailModal.setAttribute('data-current-scholar-id', btn.getAttribute('data-scholar-id') || '');
                
                const profileUrl = btn.getAttribute('data-profile');
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
                
                const studentName = btn.getAttribute('data-student-name') || 'N/A';
                const reqModalTitleStudentName = document.getElementById('req-modal-title-student-name');
                if (reqModalTitleStudentName) reqModalTitleStudentName.textContent = (studentName !== 'N/A' ? studentName + "'s" : '');
                
                document.getElementById('req-modal-name').textContent = studentName;
                document.getElementById('req-modal-mobile').textContent = btn.getAttribute('data-student-mobile') || 'N/A';
                document.getElementById('req-modal-course').textContent = btn.getAttribute('data-course') || 'N/A';
                document.getElementById('req-modal-semester').textContent = btn.getAttribute('data-semester') || 'N/A';
                document.getElementById('req-modal-hostel').textContent = btn.getAttribute('data-hostel') || 'N/A';

                document.getElementById('req-modal-purpose').textContent = btn.getAttribute('data-purpose') || 'N/A';
                document.getElementById('req-modal-destination').textContent = btn.getAttribute('data-destination') || 'N/A';
                document.getElementById('req-modal-reason').textContent = btn.getAttribute('data-reason') || 'N/A';
                document.getElementById('req-modal-exit').textContent = convertUTCToIST(btn.getAttribute('data-exit')) || 'N/A';
                document.getElementById('req-modal-entry').textContent = convertUTCToIST(btn.getAttribute('data-entry')) || 'N/A';

                document.getElementById('req-modal-warden').textContent = btn.getAttribute('data-warden') || 'Pending';
                document.getElementById('req-modal-warden-contact').textContent = btn.getAttribute('data-warden-contact') || 'N/A';
                document.getElementById('req-modal-requested-by').textContent = btn.getAttribute('data-requested-by') || 'N/A';

                // Copy/inject action buttons into modal footer
                const tr = btn.closest('tr');
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
            });
        });

        document.querySelectorAll('.btn-close-req-detail').forEach(btn => {
            btn.addEventListener('click', () => {
                reqDetailModal.classList.add('hidden');
            });
        });
    }

    // Modal Tabs & History Caching Logic
    function setupModalTabs(modalId, scholarIdGetter, prefix) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const tabs = modal.querySelectorAll('.modal-tab');
        const slideContainer = modal.querySelector('.modal-tab-slides');
        const tbody = document.getElementById(`${prefix}-history-tbody`);
        if (!tabs.length || !slideContainer || !tbody) return;

        let historyCache = null;

        // Add single initialization of click listeners on tabs
        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => {
                // Update active tab styling
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Perform hardware-accelerated slide animation
                slideContainer.style.transform = `translateX(-${index * 50}%)`;

                // If history tab clicked and no cache exists, fetch data
                if (tab.getAttribute('data-tab') === 'history' && !historyCache) {
                    const scholarId = scholarIdGetter();
                    if (!scholarId) {
                        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Student ID not found.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = `<tr><td colspan="7" class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>`;

                    fetch(`/api/student/${scholarId}/history/`)
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                historyCache = data; // Cache data
                                renderHistoryTable(data, prefix);
                            } else {
                                tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error: ${data.message || 'Could not retrieve history data.'}</td></tr>`;
                            }
                        })
                        .catch(err => {
                            console.error('Error fetching history:', err);
                            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Failed to load history.</td></tr>`;
                        });
                }
            });
        });

        // Function to reset tabs/cache when modal closes
        const closeBtns = modal.querySelectorAll('.btn-close-modal, .btn-close-req-detail, .btn-primary.btn-close-modal');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Reset slide position
                slideContainer.style.transform = `translateX(0%)`;
                // Reset active tab
                tabs.forEach(t => t.classList.remove('active'));
                if(tabs.length > 0) tabs[0].classList.add('active');
                // Evict cache
                historyCache = null;
                // Clear table
                tbody.innerHTML = `<tr><td colspan="7" class="text-center">Loading...</td></tr>`;
            });
        });
    }

    // Helper to render the history table identical to existing layout
    function renderHistoryTable(data, prefix) {
        // Render stats
        document.getElementById(`${prefix}-total-requests`).textContent = data.stats.total;
        document.getElementById(`${prefix}-approved-requests`).textContent = data.stats.approved;
        document.getElementById(`${prefix}-rejected-requests`).textContent = data.stats.rejected;
        document.getElementById(`${prefix}-pending-requests`).textContent = data.stats.pending;

        const tbody = document.getElementById(`${prefix}-history-tbody`);
        tbody.innerHTML = '';

        if (!data.history || data.history.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="padding: 25px; color: var(--text-muted);">No Outpass History Available</td></tr>`;
            return;
        }

        data.history.forEach(item => {
            const displayExit = window.convertUTCToIST ? window.convertUTCToIST(item.requested_exit_datetime) : item.requested_exit_datetime;
            const displayEntry = window.convertUTCToIST ? window.convertUTCToIST(item.requested_entry_datetime) : item.requested_entry_datetime;
            const displayActualExit = window.convertUTCToIST ? window.convertUTCToIST(item.actual_exit_datetime) : item.actual_exit_datetime;
            const displayActualEntry = window.convertUTCToIST ? window.convertUTCToIST(item.actual_entry_datetime) : item.actual_entry_datetime;
            
            const datePart = displayExit ? displayExit.split(' ')[0] : '-';
            const schOutTime = displayExit ? displayExit.split(' ').slice(1).join(' ') : '-';
            const schInTime = displayEntry ? displayEntry.split(' ').slice(1).join(' ') : '-';

            const statusClass = item.request_status.toLowerCase().replace(/\s+/g, '-');

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${datePart}</td>
                <td>
                    OUT: ${schOutTime}<br>
                    IN: ${schInTime}
                </td>
                <td>
                    OUT: ${displayActualExit || '-'}<br>
                    IN: ${displayActualEntry || '-'}
                </td>
                <td>${item.outing_reason || '-'}</td>
                <td>${item.destination || '-'}</td>
                <td><span class="status-badge ${statusClass}">${item.request_status}</span></td>
                <td>${item.warden_remarks || '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Initialize tabs for Student Details Modal
    setupModalTabs('student-modal', () => {
        return document.getElementById('scholar-id') ? document.getElementById('scholar-id').value : null;
    }, 'student');

    // Initialize tabs for Request Details Modal
    setupModalTabs('request-detail-modal', () => {
        const modal = document.getElementById('request-detail-modal');
        return modal ? modal.getAttribute('data-current-scholar-id') : null;
    }, 'req');

});
